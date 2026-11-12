/* Antivenom Within Reach - front end. Talks to app.py (JSON API). */
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const S = { s: "sanghar", k: 3, lam: 1, mu: 0, mixer: "xy", reps: 2, plan: "optimal", data: null, qaoa: {}, polling: null };
const C = { ok: "#34d399", bad: "#fb923c", indigo: "#818cf8", teal: "#2dd4bf", muted: "#8d98b6", grid: "rgba(148,163,205,.12)" };

Chart.defaults.color = C.muted;
Chart.defaults.font.family = "Inter, system-ui, sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.labels.boxWidth = 10;
Chart.defaults.plugins.legend.labels.boxHeight = 10;

const pct = (x, d = 1) => (100 * x).toFixed(d) + "%";
const qkey = () => [S.s, S.k, S.lam, S.mu, S.mixer, S.reps].join("|");
const toast = (msg) => { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2600); };

/* ---------------- animated numbers ---------------- */
function countTo(el, to, fmt, ms = 900) {
  const from = el._v ?? 0; const t0 = performance.now(); el._v = to;
  const step = (t) => { const p = Math.min(1, (t - t0) / ms); const e = 1 - Math.pow(1 - p, 3);
    el.textContent = fmt(from + (to - from) * e); if (p < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}

/* ---------------- segmented controls + ink ---------------- */
function moveInk(container, ink) {
  const a = container.querySelector("button.active"); if (!a || !ink) return;
  ink.style.left = a.offsetLeft + "px"; ink.style.width = a.offsetWidth + "px";
}
function fillRange(el) { const p = (el.value - el.min) / (el.max - el.min) * 100; el.style.setProperty("--fill", p + "%"); }

/* ---------------- map ---------------- */
let map, tiles, layer;
function buildMap(geo) {
  if (map) map.remove();
  map = L.map("map", { zoomControl: false, attributionControl: true, crs: geo ? L.CRS.EPSG3857 : L.CRS.Simple,
                       zoomSnap: 0.25, preferCanvas: false, fadeAnimation: true, zoomAnimation: true });
  if (geo) {
    tiles = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 16, attribution: 'Basemap &copy; Esri · Facilities &amp; settlements &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(map);
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}", { maxZoom: 16, opacity: .75 }).addTo(map);
  } else {
    map.attributionControl.addAttribution("Synthetic district · km grid");
  }
  L.control.zoom({ position: "topright" }).addTo(map);
  document.getElementById("map").classList.toggle("grid", !geo);
  layer = L.layerGroup().addTo(map);
}

function drawDistrict(fit) {
  const d = S.data; if (!d) return;
  const plan = currentPlan();
  const covered = plan.covered;
  layer.clearLayers();
  const maxB = Math.max(...d.villages.map((v) => v.bites));
  // links first (under markers)
  plan.plan.forEach((on, i) => {
    if (!on) return;
    const c = d.clinics[i];
    c.reach.forEach((v) => L.polyline([c.pos, d.villages[v].pos], { color: C.indigo, weight: 1.6, opacity: .55, className: "link", interactive: false }).addTo(layer));
  });
  d.villages.forEach((v, i) => {
    const ok = covered[i] === 1;
    const m = L.circleMarker(v.pos, { radius: 4 + 13 * Math.sqrt(v.bites / maxB), color: ok ? "#a7f3d0" : "#fed7aa", weight: 1,
      fillColor: ok ? C.ok : C.bad, fillOpacity: .78, className: "village" }).addTo(layer);
    m.bindTooltip(`<b>${v.name}</b><br>${v.pop.toLocaleString()} people · ${v.bites.toFixed(1)} bites/yr<br>` +
      (v.hospital ? "within reach of the hospital" : ok ? "antivenom within reach" : "<span style='color:#fb923c'>no antivenom within reach</span>"), { direction: "top" });
  });
  d.clinics.forEach((c, i) => {
    const on = plan.plan[i] === 1;
    const icon = L.divIcon({ className: "", html: `<div class="clinic-icon ${on ? "on" : ""}"></div>`, iconSize: [18, 18], iconAnchor: [9, 9] });
    L.marker(c.pos, { icon, zIndexOffset: on ? 900 : 500 }).addTo(layer)
      .bindTooltip(`<b>${c.name}</b>${c.members.length > 1 ? "<br><span style='color:#8d98b6'>" + c.members.join(", ") + "</span>" : ""}<br>${on ? "stocks antivenom" : "candidate clinic"} · ${c.fridge ? "has a fridge" : "needs a solar fridge"}<br>reaches ${c.reach.length} settlements beyond the hospital`, { direction: "top", offset: [0, -8] });
  });
  const hi = L.divIcon({ className: "", html: '<div class="hosp-icon"></div>', iconSize: [26, 26], iconAnchor: [13, 13] });
  L.marker(d.hospital.pos, { icon: hi, zIndexOffset: 1000 }).addTo(layer).bindTooltip(`<b>${d.hospital.name}</b><br>always stocked`, { direction: "top" });
  if (fit) {
    const pts = d.villages.map((v) => v.pos).concat(d.clinics.map((c) => c.pos));
    map.fitBounds(L.latLngBounds(pts).pad(0.08), { animate: false });
  }
  const title = { none: "Hospital only", greedy: "Greedy plan", optimal: "Optimal plan (exact)", qaoa: "QAOA plan" }[S.plan];
  $("#mapTitle").innerHTML = `<b>${title}${plan.names.length ? ": " + plan.names.join(", ") : ""}</b><span>${d.scenario.title} · antivenom within ${d.scenario.window}</span>`;
}

function currentPlan() {
  const d = S.data;
  if (S.plan === "none") return { plan: d.clinics.map(() => 0), names: [], covered: d.villages.map((v) => (v.hospital ? 1 : 0)),
    share_bites_covered: d.hospital_only.share_bites_covered, share_child_bites_covered: d.hospital_only.share_child_bites_covered,
    bites_covered_per_year: d.hospital_only.share_bites_covered * d.totals.bites, score: null, new_fridges_needed: 0 };
  if (S.plan === "qaoa" && S.qaoa[qkey()]) return S.qaoa[qkey()].best_plan;
  return d[S.plan === "qaoa" ? "optimal" : S.plan];
}

function renderPlanPanel() {
  const d = S.data, p = currentPlan();
  const ul = $("#planList"); ul.innerHTML = "";
  if (!p.names.length) ul.innerHTML = '<li class="empty">Only the district hospital stocks antivenom</li>';
  p.names.forEach((n, j) => {
    const i = d.clinics.findIndex((c) => c.name === n);
    const li = document.createElement("li"); li.style.animationDelay = j * 70 + "ms";
    li.innerHTML = `<span class="sq"></span>${n}${d.clinics[i] && !d.clinics[i].fridge ? '<span class="fr">needs fridge</span>' : ""}`;
    ul.appendChild(li);
  });
  const h = d.hospital_only;
  countTo($("#kpiBites"), p.share_bites_covered * 100, (v) => v.toFixed(1) + "%");
  countTo($("#kpiChild"), p.share_child_bites_covered * 100, (v) => v.toFixed(1) + "%");
  const extra = (p.share_bites_covered - h.share_bites_covered) * d.totals.bites;
  countTo($("#kpiExtra"), extra, (v) => "+" + v.toFixed(0));
  $("#kpiBitesD").textContent = S.plan === "none" ? "baseline" : `+${(100 * (p.share_bites_covered - h.share_bites_covered)).toFixed(1)} pts vs hospital only`;
  $("#kpiChildD").textContent = S.plan === "none" ? "baseline" : `+${(100 * (p.share_child_bites_covered - h.share_child_bites_covered)).toFixed(1)} pts`;
  $("#kpiWindow").textContent = `of ${d.totals.bites.toFixed(0)} expected bites/yr`;
  if (p.score == null) { $("#kpiScore").textContent = "–"; $("#kpiScore")._v = 0; }
  else countTo($("#kpiScore"), p.score, (v) => v.toFixed(3));
  $("#kpiRandom").textContent = `random plan: ${d.random_score.toFixed(2)}`;
}

/* ---------------- data loading ---------------- */
let loadTimer;
function load(fit = false) {
  clearTimeout(loadTimer);
  loadTimer = setTimeout(async () => {
    const r = await fetch(`/api/state?s=${S.s}&k=${S.k}&lam=${S.lam}&mu=${S.mu}`);
    const d = await r.json();
    if (d.error) { toast(d.error); return; }
    const newScenario = !S.data || S.data.scenario.id !== d.scenario.id;
    S.data = d;
    if (newScenario) buildMap(d.scenario.geo);
    $("#scenarioNote").textContent = d.scenario.note;
    $("#qubitChip").textContent = `${d.n_qubits} qubits · ${d.n_valid_plans} valid plans`;
    $("#methodNote").textContent = `This scenario: ${d.villages.length} settlements, ${d.totals.people.toLocaleString()} people, ${d.clinics.length} candidate clinics, antivenom window ${d.scenario.window}.`;
    const qb = $('#planSeg [data-p="qaoa"]'); const has = !!S.qaoa[qkey()];
    qb.disabled = !has; if (!has && S.plan === "qaoa") setPlan("optimal", false);
    drawDistrict(newScenario || fit);
    renderPlanPanel();
    supplyChart();
    if (S.qaoa[qkey()]) showQaoa(S.qaoa[qkey()], false); else resetQaoaView();
  }, 120);
}

function setPlan(p, redraw = true) {
  S.plan = p;
  $$("#planSeg button").forEach((b) => b.classList.toggle("active", b.dataset.p === p));
  if (redraw) { drawDistrict(false); renderPlanPanel(); }
}

/* ---------------- charts ---------------- */
let conv, sup, hw;
function convChart() {
  if (conv) conv.destroy();
  conv = new Chart($("#convChart"), {
    type: "line",
    data: { datasets: [] },
    options: { animation: false, responsive: true, maintainAspectRatio: false, parsing: false,
      scales: { x: { type: "linear", title: { display: true, text: "cost evaluations" }, grid: { color: C.grid } },
                y: { title: { display: true, text: "energy (lower = better)" }, grid: { color: C.grid } } },
      plugins: { legend: { display: true, position: "top", align: "end" } }, elements: { point: { radius: 0 } } } });
}
const RESTART_COLORS = ["#818cf8", "#2dd4bf", "#f472b6", "#fbbf24"];
function addProgress(points) {
  points.forEach(([r, n, v]) => {
    while (conv.data.datasets.length <= r) {
      const i = conv.data.datasets.length;
      conv.data.datasets.push({ label: i === 0 ? "start 1 (ramp)" : `start ${i + 1}`, data: [], borderColor: RESTART_COLORS[i % 4], borderWidth: 1.8, tension: .25 });
    }
    conv.data.datasets[r].data.push({ x: n, y: v });
  });
  conv.update("none");
}

function supplyChart() {
  const d = S.data; if (sup) sup.destroy();
  sup = new Chart($("#supplyChart"), { type: "line",
    data: { labels: d.supply.map((s) => s.k), datasets: [
      { label: "optimal", data: d.supply.map((s) => 100 * s.optimal), borderColor: C.indigo, backgroundColor: "rgba(129,140,248,.15)", fill: true, tension: .3, pointRadius: 4 },
      { label: "greedy", data: d.supply.map((s) => 100 * s.greedy), borderColor: C.teal, borderDash: [5, 4], tension: .3, pointRadius: 3 }] },
    options: { responsive: true, maintainAspectRatio: false, animation: { duration: 900, easing: "easeOutQuart" },
      scales: { x: { title: { display: true, text: "clinics stocked (k)" }, grid: { color: C.grid } },
                y: { title: { display: true, text: "% bites within reach" }, grid: { color: C.grid } } } } });
}

/* ---------------- QAOA ---------------- */
function replay(points, total) {
  return new Promise((done) => {
    const dur = 2600, t0 = performance.now(); let i = 0;
    const step = (t) => {
      const upto = Math.floor(points.length * Math.min(1, (t - t0) / dur));
      if (upto > i) { addProgress(points.slice(i, upto)); i = upto; $("#progBar").style.width = Math.min(98, 100 * i / total) + "%"; }
      if (i < points.length) requestAnimationFrame(step); else done();
    };
    requestAnimationFrame(step);
  });
}
function resetQaoaView() {
  convChart(); $("#progBar").style.width = "0";
  ["#mPopt", "#mValid", "#mAR"].forEach((s) => { $(s).textContent = "–"; $(s)._v = 0; });
  ["#mBoost", "#mRand"].forEach((s) => ($(s).textContent = ""));
  $("#topPlans").innerHTML = "";
  $("#runStatus").textContent = "Trains on the Qiskit Aer simulator; every number is checked against the exact optimum.";
}

async function runQaoa() {
  const key = qkey();
  if (S.qaoa[key]) { showQaoa(S.qaoa[key], true); return; }
  const btn = $("#runBtn"); btn.classList.add("busy"); btn.querySelector(".run-label").textContent = "Training on Qiskit Aer…";
  resetQaoaView();
  $("#runStatus").textContent = `${S.data.n_qubits} qubits · depth p=${S.reps} · ${S.mixer === "xy" ? "XY mixer" : "X mixer + penalty"}`;
  const r = await fetch("/api/qaoa", { method: "POST", body: JSON.stringify({ s: S.s, k: S.k, lam: S.lam, mu: S.mu, mixer: S.mixer, reps: S.reps }) });
  const { id } = await r.json();
  let since = 0; const total = 3 * 160;
  clearInterval(S.polling);
  S.polling = setInterval(async () => {
    const j = await (await fetch(`/api/job?id=${id}&since=${since}`)).json();
    if (j.cached && j.status === "done") {           // replay a pre-trained run as an animation
      clearInterval(S.polling); since = j.n;
      await replay(j.progress, total);
    } else if (j.progress.length) { addProgress(j.progress); since = j.n; $("#progBar").style.width = Math.min(98, 100 * j.n / total) + "%"; }
    if (j.status !== "running") {
      clearInterval(S.polling); btn.classList.remove("busy"); btn.querySelector(".run-label").textContent = "Run QAOA";
      if (j.status === "error") { toast("QAOA failed: " + j.error); return; }
      $("#progBar").style.width = "100%";
      S.qaoa[key] = j.result; showQaoa(j.result, true);
    }
  }, 220);
}

function showQaoa(res, announce) {
  const m = res.metrics;
  countTo($("#mPopt"), m.p_optimal, (v) => v.toFixed(3));
  $("#mBoost").textContent = `${m.boost_vs_random.toFixed(1)}× a random plan`;
  countTo($("#mValid"), m.valid_rate * 100, (v) => v.toFixed(0) + "%");
  countTo($("#mAR"), m.approx_ratio_valid, (v) => v.toFixed(3));
  $("#mRand").textContent = `random: ${S.data.random_score.toFixed(2)}`;
  const max = Math.max(...res.top_plans.map((p) => p.prob));
  $("#topPlans").innerHTML = res.top_plans.slice(0, 7).map((p, i) => `
    <div class="tp ${p.optimal ? "optimal" : p.valid ? "" : "invalid"}" style="animation-delay:${i * 60}ms">
      <div><div class="lbl"><span>${p.names.join(" + ") || "(none)"}</span>${p.optimal ? '<span class="tag opt">optimal</span>' : p.valid ? "" : '<span class="tag inv">breaks budget</span>'}</div>
      <div class="track"><div class="fill" data-w="${(100 * p.prob / max).toFixed(1)}"></div></div></div>
      <div class="p">${pct(p.prob, 1)}</div></div>`).join("");
  requestAnimationFrame(() => $$("#topPlans .fill").forEach((f) => (f.style.width = f.dataset.w + "%")));
  $("#runStatus").textContent = `Done in ${res.seconds.toFixed(1)} s · ${res.evals} circuit evaluations · ${res.terms} Hamiltonian terms (up to ${res.max_order}-body).`;
  const qb = $('#planSeg [data-p="qaoa"]'); qb.disabled = false;
  if (announce) { setPlan("qaoa"); toast(res.best_plan.score >= 0.9999 ? "QAOA found the optimal plan ✓" : `QAOA's best plan scores ${res.best_plan.score.toFixed(3)} of the optimum`); }
}

/* ---------------- hardware tab ---------------- */
async function loadHardware() {
  const h = await (await fetch("/api/hardware")).json();
  if (!h.available) { $("#hwNote").textContent = "No hardware run found. Run: python run_hardware.py"; return; }
  const when = new Date(h.hardware.sent_utc);
  $("#hwMeta").innerHTML = `
    <div><span>Backend</span><b>${h.hardware.backend} (IBM Heron, 156 qubits)</b></div>
    <div><span>Job ID</span><b class="mono">${h.hardware.job_id}</b></div>
    <div><span>Sent</span><b>${when.toUTCString().replace(" GMT", " UTC")}</b></div>
    <div><span>Quantum time · shots</span><b>${h.hardware.usage_quantum_seconds ?? "–"} s · ${h.shots} per circuit</b></div>`;
  const keys = [["ideal", "ideal simulator", "rgba(129,140,248,.9)"], ["noisy_simulation", "noise model", "rgba(141,152,182,.75)"], ["real_hardware", "real QPU", "rgba(45,212,191,.95)"]];
  const lab = h.circuits.map((c) => (c.mixer === "x" ? ["standard QAOA", "valid shots"] : ["ring-XY QAOA", "valid shots"]))
    .concat(h.circuits.map((c) => (c.mixer === "x" ? ["standard QAOA", "score / optimum"] : ["ring-XY QAOA", "score / optimum"])));
  if (hw) hw.destroy();
  hw = new Chart($("#hwChart"), { type: "bar",
    data: { labels: lab, datasets: keys.map(([k, name, col]) => ({ label: name, backgroundColor: col, borderRadius: 5,
      data: h.circuits.map((c) => 100 * c[k].valid_rate).concat(h.circuits.map((c) => 100 * c[k].approx_ratio_valid)) })) },
    options: { responsive: true, maintainAspectRatio: false, animation: { duration: 1100, easing: "easeOutQuart" },
      scales: { y: { min: 0, max: 100, grid: { color: C.grid }, title: { display: true, text: "%" } }, x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 0, autoSkip: false } } },
      plugins: { tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}%` } } } } });
  const xr = h.circuits.find((c) => c.mixer === "xyring"), xs = h.circuits.find((c) => c.mixer === "x");
  $("#hwNote").innerHTML = `On the real QPU, our ring-XY circuit kept <b>${pct(xr.real_hardware.valid_rate, 0)}</b> of shots inside the budget versus <b>${pct(xs.real_hardware.valid_rate, 0)}</b> for standard QAOA, with half the two-qubit gates (${xr.two_qubit_gates} vs ${xs.two_qubit_gates}). Its valid plans score <b>${xr.real_hardware.approx_ratio_valid.toFixed(2)}</b> of the optimum on average (a random plan: ${h.random_score.toFixed(2)}). Benchmark district, 9 qubits, p = 1. The job can be looked up on the IBM Quantum Platform Workloads page.`;
}

/* ---------------- wiring ---------------- */
function init() {
  const sc = $("#scenarios"), pill = sc.querySelector(".slider-pill");
  $$("#scenarios button").forEach((b) => b.addEventListener("click", () => {
    $$("#scenarios button").forEach((x) => x.classList.toggle("active", x === b)); moveInk(sc, pill);
    S.s = b.dataset.s; load(true);
  }));
  const tabs = $("#tabs"), ink = tabs.querySelector(".tab-ink");
  $$("#tabs button").forEach((b) => b.addEventListener("click", () => {
    $$("#tabs button").forEach((x) => x.classList.toggle("active", x === b)); moveInk(tabs, ink);
    $$(".tabpane").forEach((p) => p.classList.toggle("active", p.dataset.pane === b.dataset.t));
    if (b.dataset.t === "hardware") loadHardware();
    if (b.dataset.t === "method") supplyChart();
  }));
  [["k", "kVal", (v) => v], ["lam", "lamVal", (v) => (+v).toFixed(1)], ["mu", "muVal", (v) => v], ["reps", "repsVal", (v) => v]].forEach(([id, out, f]) => {
    const el = $("#" + id); fillRange(el);
    el.addEventListener("input", () => { $("#" + out).textContent = f(el.value); fillRange(el);
      S[id] = +el.value; if (id === "reps") { if (S.qaoa[qkey()]) showQaoa(S.qaoa[qkey()], false); else resetQaoaView(); } else load(); });
  });
  $$("#planSeg button").forEach((b) => b.addEventListener("click", () => !b.disabled && setPlan(b.dataset.p)));
  $$("#mixerSeg button").forEach((b) => b.addEventListener("click", () => {
    $$("#mixerSeg button").forEach((x) => x.classList.toggle("active", x === b)); S.mixer = b.dataset.m;
    if (S.qaoa[qkey()]) showQaoa(S.qaoa[qkey()], false); else resetQaoaView();
  }));
  $("#runBtn").addEventListener("click", runQaoa);
  window.addEventListener("resize", () => { moveInk(sc, pill); moveInk(tabs, ink); });
  requestAnimationFrame(() => { moveInk(sc, pill); moveInk(tabs, ink); });
  convChart(); load(true);
  // deep links, e.g. #s=hard&tab=hardware&plan=greedy&run=1
  const h = new URLSearchParams(location.hash.slice(1));
  if (h.get("s")) document.querySelector(`#scenarios [data-s="${h.get("s")}"]`)?.click();
  if (h.get("tab")) document.querySelector(`#tabs [data-t="${h.get("tab")}"]`)?.click();
  if (h.get("plan")) setTimeout(() => document.querySelector(`#planSeg [data-p="${h.get("plan")}"]`)?.click(), 600);
  if (h.get("run")) setTimeout(runQaoa, 800);
}
document.addEventListener("DOMContentLoaded", init);
