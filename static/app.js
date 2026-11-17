// Fantasy Trail frontend. A journey keeps its real story length and is
// walked over many outings: each walk covers the next stretch, its stops
// land on matching real places, and "I walked it" saves the progress in
// this browser.

const KM_PER_MI = 1.609344;
const PRESETS_KM = [3, 5, 8, 10];
const MADISON = [43.06, -89.40];

const state = {
  region: { id: "madison", name: "Madison, WI", lat: 43.0731, lon: -89.4012, radius_m: 80467, max_target_m: null },
  journeys: [],
  journey: null,
  unit: "km",
  loop: true,
  start: null,
  end: null,
};

const layers = { start: null, end: null, route: null, landmarks: null, region: null };

// What each terrain is called when telling someone where a stop landed
const TERRAIN_WORDS = {
  forest: "woods", water: "water", marsh: "wetland", meadow: "meadow", park: "a park",
  town: "the shops", hill: "a hilltop", tower: "a tower", bridge: "a bridge", tunnel: "a tunnel",
};

// ---------- Saved progress (this browser only) ----------
// { journeyId: { walked_km, log: [{ date, km, stops: [names] }] } }

function load(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function save(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Private mode or storage blocked: progress just won't persist
  }
}

function progressFor(id) {
  const all = load("progress", {});
  return all[id] || { walked_km: 0, log: [] };
}

function setProgress(id, progress) {
  const all = load("progress", {});
  all[id] = progress;
  save("progress", all);
}
let lastResult = null; // last /route response, kept so a unit switch can re-label it

const $ = (id) => document.getElementById(id);
const journeysDiv = $("journeys");
const distanceInput = $("distance");
const presetsDiv = $("presets");
const hint = $("hint");
const findButton = $("find");
const resultSection = $("result");
const summary = $("summary");
const stopsList = $("stops");

const map = L.map("map").setView(MADISON, 13);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const css = getComputedStyle(document.documentElement);
const TRAIL_COLOR = css.getPropertyValue("--trail").trim();
const ROAD_COLOR = css.getPropertyValue("--road").trim();

// ---------- Units ----------

function kmToUnit(km) {
  return state.unit === "km" ? km : km / KM_PER_MI;
}

function unitToKm(value) {
  return state.unit === "km" ? value : value * KM_PER_MI;
}

function formatDistance(meters) {
  const value = kmToUnit(meters / 1000);
  return `${value.toFixed(value < 10 ? 1 : 0)} ${state.unit}`;
}

function setDistanceKm(km) {
  distanceInput.value = +kmToUnit(km).toFixed(1);
}

function renderPresets() {
  presetsDiv.innerHTML = "";
  for (const km of PRESETS_KM) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = `${+kmToUnit(km).toFixed(1)} ${state.unit}`;
    b.addEventListener("click", () => {
      setDistanceKm(km);
      save("walk_km", km);
    });
    presetsDiv.appendChild(b);
  }
}

document.querySelectorAll("[data-unit]").forEach((b) =>
  b.addEventListener("click", () => {
    if (b.dataset.unit === state.unit) return;
    const km = unitToKm(parseFloat(distanceInput.value) || 0);
    state.unit = b.dataset.unit;
    document.querySelectorAll("[data-unit]").forEach((x) => x.classList.toggle("active", x === b));
    setDistanceKm(km);
    renderPresets();
    if (lastResult) showResult(lastResult); // re-label distances
    renderProgress();
  })
);

// ---------- Journeys ----------

function selectJourney(j) {
  state.journey = j;
  save("journey", j.id);
  for (const card of journeysDiv.children) {
    card.setAttribute("aria-checked", card.dataset.id === j.id ? "true" : "false");
  }
  clearRoute();
  renderProgress();
}

function renderProgress() {
  const j = state.journey;
  const panel = $("progress");
  if (!j) return (panel.hidden = true);
  panel.hidden = false;
  const p = progressFor(j.id);
  const pct = Math.min(100, (p.walked_km / j.total_km) * 100);
  panel.querySelector(".fill").style.width = `${pct}%`;
  panel.querySelector(".bar").setAttribute("aria-valuenow", pct.toFixed(1));
  $("progress-text").textContent =
    `${formatDistance(p.walked_km * 1000)} of ${formatDistance(j.total_km * 1000)} walked`;

  const next = j.stops.find((s) => s.km > p.walked_km + 1e-9);
  const finished = !next;
  $("next-stop").textContent = finished
    ? `You've reached ${j.stops[j.stops.length - 1].name}. Journey complete!`
    : `Next: ${next.name} in ${formatDistance((next.km - p.walked_km) * 1000)}`;
  findButton.disabled = finished;

  const stamps = $("stamps");
  stamps.innerHTML = "";
  const reached = [];
  for (const walk of p.log) for (const name of walk.stops) reached.push({ name, date: walk.date });
  for (const r of reached) {
    const li = document.createElement("li");
    li.textContent = r.name + " ";
    const when = document.createElement("span");
    when.className = "when";
    when.textContent = new Date(r.date).toLocaleDateString();
    li.appendChild(when);
    stamps.appendChild(li);
  }
  $("undo").hidden = p.log.length === 0;
  $("restart").hidden = p.log.length === 0;
}

$("undo").addEventListener("click", () => {
  const p = progressFor(state.journey.id);
  const last = p.log.pop();
  if (!last) return;
  p.walked_km = Math.max(0, p.walked_km - last.km);
  setProgress(state.journey.id, p);
  clearRoute();
  renderProgress();
});

$("restart").addEventListener("click", () => {
  if (!confirm(`Start ${state.journey.title} over from the beginning? Your progress will be cleared.`)) return;
  setProgress(state.journey.id, { walked_km: 0, log: [] });
  clearRoute();
  renderProgress();
});

function renderJourneys() {
  journeysDiv.innerHTML = "";
  for (const j of state.journeys) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "journey";
    card.dataset.id = j.id;
    card.setAttribute("role", "radio");
    card.setAttribute("aria-checked", "false");
    card.innerHTML = `
      <div class="title"></div>
      <div class="blurb"></div>
      <div class="meta"></div>`;
    card.querySelector(".title").textContent = j.title;
    card.querySelector(".blurb").textContent = j.blurb;
    const walks = Math.round(j.total_km / 5);
    card.querySelector(".meta").textContent =
      `${j.total_km.toLocaleString()} km · ${j.stops.length} stops · about ${walks} walks of 5 km · ${j.source}`;
    card.addEventListener("click", () => selectJourney(j));
    journeysDiv.appendChild(card);
  }
}

fetch("journeys")
  .then((r) => r.json())
  .then((list) => {
    state.journeys = list;
    renderJourneys();
    const saved = list.find((j) => j.id === load("journey", null));
    if (list.length) selectJourney(saved || list[0]);
  })
  .catch(() => {
    journeysDiv.textContent = "Couldn't load journeys. Is the server running?";
  });

// ---------- Start / end points ----------

function pinIcon(label, cls = "") {
  return L.divIcon({
    className: "",
    html: `<div class="pin ${cls}">${label}</div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

function updateHint() {
  if (!state.start) hint.textContent = "Click the map to set your start.";
  else if (!state.loop && !state.end) hint.textContent = "Now click the map to set where you'll finish.";
  else hint.textContent = "Ready. Click Find my route.";
}

function setMode(loop) {
  state.loop = loop;
  document.querySelectorAll("[data-mode]").forEach((b) =>
    b.classList.toggle("active", (b.dataset.mode === "loop") === loop)
  );
  // An end point means nothing for a loop, so drop it
  if (loop && layers.end) {
    map.removeLayer(layers.end);
    layers.end = null;
    state.end = null;
  }
  updateHint();
}

document.querySelectorAll("[data-mode]").forEach((b) =>
  b.addEventListener("click", () => setMode(b.dataset.mode === "loop"))
);

map.on("click", (e) => {
  if (!state.region) return;
  const inside = map.distance(e.latlng, [state.region.lat, state.region.lon]) <= state.region.radius_m;
  if (!inside) {
    hint.textContent = `That's outside the ${state.region.name} map area. Click inside the circle.`;
    return;
  }
  if (!state.start) {
    setStart(e.latlng);
    save("home", { lat: e.latlng.lat, lng: e.latlng.lng });
  } else if (!state.loop && !state.end) {
    state.end = e.latlng;
    layers.end = L.marker(e.latlng, { icon: pinIcon("F", "endpoint"), title: "Finish" }).addTo(map);
  }
  updateHint();
});

function setStart(latlng) {
  state.start = latlng;
  layers.start = L.marker(latlng, { icon: pinIcon("S", "endpoint"), title: "Start" }).addTo(map);
  // Start downloading nearby real places now, so stops can land on them
  // by the time a route is requested
  fetch("features", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat: latlng.lat, lon: latlng.lng }),
  }).catch(() => {});
}

function clearRoute() {
  for (const key of ["route", "landmarks"]) {
    if (layers[key]) map.removeLayer(layers[key]);
    layers[key] = null;
  }
  lastResult = null;
  resultSection.hidden = true;
}

function resetPoints() {
  for (const key of ["start", "end"]) {
    if (layers[key]) map.removeLayer(layers[key]);
    layers[key] = null;
  }
  state.start = state.end = null;
  clearRoute();
  updateHint();
}

$("reset").addEventListener("click", () => {
  resetPoints();
  save("home", null);
});

// ---------- Region (city) ----------

const regionStatus = $("region-status");
const cityResults = $("city-results");
let pollTimer = null;

function setRegionStatus(html, cls = "") {
  regionStatus.className = `region-status ${cls}`;
  regionStatus.innerHTML = html;
}

// place is what the user picked. It can differ from the region: Middleton
// is served by Madison's map, but the map should center on Middleton.
function useRegion(region, place = region) {
  state.region = region;
  resetPoints();
  if (layers.region) map.removeLayer(layers.region);
  layers.region = L.circle([region.lat, region.lon], {
    radius: region.radius_m, color: TRAIL_COLOR, weight: 1, fill: false, dashArray: "6 6", interactive: false,
  }).addTo(map);
  map.setView([place.lat, place.lon], 14);
  const cap = region.max_target_m ? ` · walks up to ${formatDistance(region.max_target_m)}` : "";
  setRegionStatus(`Walking in <strong>${escapeHtml(place.name)}</strong>${cap}`);

  // Put back the remembered start point if it's in this map area
  const home = load("home", null);
  if (home && map.distance([home.lat, home.lng], [region.lat, region.lon]) <= region.radius_m) {
    setStart(L.latLng(home.lat, home.lng));
    map.setView([home.lat, home.lng], 14);
    updateHint();
  }
}

function waitForRegion(region, place) {
  clearTimeout(pollTimer);
  if (region.status === "ready") return useRegion(region, place);
  if (region.status === "failed") {
    state.region = null;
    setRegionStatus(`${escapeHtml(region.error || "Couldn't load that city's map.")} <button type="button" id="retry">Try again</button>`, "error");
    $("retry").addEventListener("click", () => chooseCity(place));
    return;
  }
  state.region = null; // no clicks until the map is ready
  setRegionStatus(`Preparing the map for <strong>${escapeHtml(place.name)}</strong>. The first time can take a few minutes while OpenStreetMap sends the data...`, "preparing");
  map.setView([place.lat, place.lon], 13);
  pollTimer = setTimeout(() => {
    fetch(`regions/${encodeURIComponent(region.id)}`)
      .then((r) => r.json())
      .then((next) => waitForRegion(next, place))
      .catch(() => waitForRegion(region, place)); // network blip: keep polling
  }, 2000);
}

function chooseCity(place) {
  cityResults.innerHTML = "";
  setRegionStatus(`Preparing the map for <strong>${escapeHtml(place.name)}</strong>...`, "preparing");
  fetch("regions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat: place.lat, lon: place.lon, name: place.name }),
  })
    .then((r) => r.json())
    .then((region) => waitForRegion(region, place))
    .catch(() => setRegionStatus("Couldn't reach the server.", "error"));
}

$("city-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $("city").value.trim();
  if (!q) return;
  cityResults.innerHTML = `<li class="empty">Searching...</li>`;
  fetch(`geocode?q=${encodeURIComponent(q)}`)
    .then((r) => r.json().then((body) => {
      if (!r.ok) throw new Error(body.detail || "Search failed");
      return body;
    }))
    .then((places) => {
      cityResults.innerHTML = "";
      if (!places.length) {
        cityResults.innerHTML = `<li class="empty">No US places found. Try "City, State".</li>`;
        return;
      }
      for (const place of places) {
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = place.name;
        b.addEventListener("click", () => chooseCity(place));
        li.appendChild(b);
        cityResults.appendChild(li);
      }
    })
    .catch((err) => {
      cityResults.innerHTML = "";
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = err.message;
      cityResults.appendChild(li);
    });
});

// ---------- Finding and drawing a route ----------

function showError(message) {
  clearRoute();
  resultSection.hidden = false;
  summary.className = "summary error";
  summary.textContent = message;
  stopsList.innerHTML = "";
}

// Where a stop landed, in words: "in Lost City Forest", "at real woods
// (no hilltop nearby)", or "along your route" when nothing matched
function whereText(lm) {
  if (!lm.landed_on) return "along your route";
  const word = TERRAIN_WORDS[lm.landed_on];
  const at = lm.place_name ? `in ${lm.place_name}` : `at real ${word.replace(/^a /, "")}`;
  return lm.landed_on === lm.terrain ? at : `${at} (no ${TERRAIN_WORDS[lm.terrain].replace(/^a /, "")} nearby)`;
}

function showResult(data) {
  lastResult = data;
  resultSection.hidden = false;
  summary.className = "summary";
  const head = data.within_tolerance
    ? `${formatDistance(data.distance_m)} ${data.loop ? "loop" : "route"}, ${Math.round(data.trail_pct)}% on trails.`
    : `<span class="warn">Couldn't fit ${formatDistance(data.target_m)} here; this is the closest route: ${formatDistance(data.distance_m)}, ${Math.round(data.trail_pct)}% on trails.</span>`;
  const reach = data.landmarks.length
    ? `Today you reach ${data.landmarks.map((lm) => escapeHtml(lm.name)).join(" and ")}.`
    : "No stops on today's stretch, just the road.";
  // Real places near a new start take a few minutes to download the first
  // time; until then stops are placed along the route instead
  const pending = data.landmarks.length && !data.features_ready
    ? `<br><span class="warn">Still finding real woods, water and landmarks near you, so today's stops are placed along your route. Try again in a few minutes.</span>`
    : "";
  summary.innerHTML = `${head}<br>${reach}${pending}`;

  stopsList.innerHTML = "";
  data.landmarks.forEach((lm, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="name"><span class="title"></span><span class="where"></span></span><span class="dist"></span>`;
    li.querySelector(".title").textContent = lm.name;
    li.querySelector(".where").textContent = whereText(lm);
    li.querySelector(".dist").textContent = `${formatDistance(lm.at_m)} in`;
    li.addEventListener("click", () => {
      map.setView([lm.lat, lm.lon], Math.max(map.getZoom(), 16));
      layers.landmarks.getLayers()[i].openPopup();
    });
    stopsList.appendChild(li);
  });

  const j = data.journey;
  $("after").textContent = j.finished
    ? `This walk finishes ${state.journey.title}.`
    : `After this walk: ${j.next_stop.name} in ${formatDistance(j.next_stop.km_away * 1000)}.`;
  const walked = $("walked");
  walked.disabled = false;
  walked.textContent = "I walked it";
}

$("walked").addEventListener("click", () => {
  const data = lastResult;
  if (!data) return;
  const p = progressFor(state.journey.id);
  p.walked_km = data.journey.progress_after_km;
  p.log.push({ date: new Date().toISOString(), km: data.journey.credit_km, stops: data.landmarks.map((lm) => lm.name) });
  setProgress(state.journey.id, p);
  const walked = $("walked");
  walked.disabled = true;
  walked.textContent = "Added to your journey";
  renderProgress();
});

function drawRoute(data) {
  clearRoute();
  layers.route = L.featureGroup(
    data.segments.map((s) =>
      L.polyline(s.path, { color: s.trail ? TRAIL_COLOR : ROAD_COLOR, weight: 5, opacity: 0.85 })
    )
  ).addTo(map);

  layers.landmarks = L.featureGroup(
    data.landmarks.map((lm, i) =>
      L.marker([lm.lat, lm.lon], { icon: pinIcon(i + 1), title: lm.name })
        .bindPopup(() => `<strong>${escapeHtml(lm.name)}</strong><br>${escapeHtml(whereText(lm))}<br>${formatDistance(lm.at_m)} into today's walk`)
    )
  ).addTo(map);

  map.fitBounds(layers.route.getBounds(), { padding: [30, 30] });
  showResult(data);
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

findButton.addEventListener("click", () => {
  if (!state.journey) return showError("Pick a journey first.");
  if (!state.region) return showError("Wait for your city's map to finish preparing.");
  if (!state.start || (!state.loop && !state.end)) {
    return showError(state.loop
      ? "Click the map to set your start first."
      : "Click the map to set both a start and a finish first.");
  }
  const km = unitToKm(parseFloat(distanceInput.value));
  if (!(km > 0)) return showError("Enter a walk distance.");

  findButton.disabled = true;
  findButton.textContent = "Searching...";

  fetch("route", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start_lat: state.start.lat,
      start_lon: state.start.lng,
      // Omitted for loops; JSON.stringify drops undefined fields
      end_lat: state.loop ? undefined : state.end.lat,
      end_lon: state.loop ? undefined : state.end.lng,
      target_distance_m: km * 1000,
      journey_id: state.journey.id,
      progress_km: progressFor(state.journey.id).walked_km,
      region_id: state.region.id,
    }),
  })
    .then((r) => r.json().catch(() => ({})).then((body) => {
      if (!r.ok) throw new Error(body.detail || `Request failed (${r.status})`);
      return body;
    }))
    .then(drawRoute)
    .catch((err) => showError(err.message))
    .finally(() => {
      findButton.textContent = "Find my route";
      renderProgress(); // re-enables the button unless the journey is finished
    });
});

distanceInput.addEventListener("change", () => save("walk_km", unitToKm(parseFloat(distanceInput.value) || 5)));

renderPresets();
setDistanceKm(load("walk_km", 5));
updateHint();
useRegion(state.region);
