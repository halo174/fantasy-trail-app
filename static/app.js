// Fantasy Trail frontend: pick a journey, set a distance and start point,
// and draw the route with the journey's stops placed along it.

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
    b.addEventListener("click", () => setDistanceKm(km));
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
  })
);

// ---------- Journeys ----------

function selectJourney(j) {
  state.journey = j;
  for (const card of journeysDiv.children) {
    card.setAttribute("aria-checked", card.dataset.id === j.id ? "true" : "false");
  }
  setDistanceKm(j.suggested_km);
  setMode(j.loop);
}

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
    card.querySelector(".meta").textContent =
      `${j.stops.length} stops · ${j.loop ? "loop" : "one way"} · ${j.source}`;
    card.addEventListener("click", () => selectJourney(j));
    journeysDiv.appendChild(card);
  }
}

fetch("journeys")
  .then((r) => r.json())
  .then((list) => {
    state.journeys = list;
    renderJourneys();
    if (list.length) selectJourney(list[0]);
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
    state.start = e.latlng;
    layers.start = L.marker(e.latlng, { icon: pinIcon("S", "endpoint"), title: "Start" }).addTo(map);
  } else if (!state.loop && !state.end) {
    state.end = e.latlng;
    layers.end = L.marker(e.latlng, { icon: pinIcon("F", "endpoint"), title: "Finish" }).addTo(map);
  }
  updateHint();
});

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

$("reset").addEventListener("click", resetPoints);

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

function showResult(data) {
  lastResult = data;
  resultSection.hidden = false;
  summary.className = "summary";
  const head = data.within_tolerance
    ? `${formatDistance(data.distance_m)} ${data.loop ? "loop" : "route"}, ${Math.round(data.trail_pct)}% on trails.`
    : `<span class="warn">Couldn't fit ${formatDistance(data.target_m)} here; this is the closest route: ${formatDistance(data.distance_m)}, ${Math.round(data.trail_pct)}% on trails.</span>`;
  summary.innerHTML = `<strong>${escapeHtml(state.journey.title)}</strong><br>${head}`;

  stopsList.innerHTML = "";
  data.landmarks.forEach((lm, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="name"></span><span class="dist"></span>`;
    li.querySelector(".name").textContent = lm.name;
    li.querySelector(".dist").textContent = i === 0 ? "start" : formatDistance(lm.at_m);
    li.addEventListener("click", () => {
      map.setView([lm.lat, lm.lon], Math.max(map.getZoom(), 16));
      layers.landmarks.getLayers()[i].openPopup();
    });
    stopsList.appendChild(li);
  });
}

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
        .bindPopup(() => `<strong>${escapeHtml(lm.name)}</strong><br>${i === 0 ? "Start here" : formatDistance(lm.at_m) + " in"}`)
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
      findButton.disabled = false;
      findButton.textContent = "Find my route";
    });
});

renderPresets();
updateHint();
useRegion(state.region);
