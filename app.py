"""Antivenom Within Reach - interactive demo.

    python app.py            # opens the app in your browser (http://127.0.0.1:8765)
    python app.py --window   # opens it in a desktop window instead (needs: pip install pywebview)

A small JSON API (Python standard library only) in front of the same solvers that produce the
report: exact brute force, greedy and QAOA on the Qiskit Aer simulator. QAOA runs in a
background thread and streams its training progress, so the UI can show it converging live.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
import webbrowser
from functools import lru_cache
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

from avr.classical import brute_force, greedy, random_baseline
from avr.instance import make_district
from avr.model import all_bitstrings, plan_report, plan_values
from avr.quantum import run_qaoa, summarize
from avr.sanghar import make_sanghar

ROOT = Path(__file__).resolve().parent
UI = ROOT / "ui"
RESULTS = ROOT / "results"

SCENARIOS = {
    "sanghar": {"title": "Sanghar, Sindh (real map)", "geo": True, "window": "1 hour",
                "note": "Real BHU, hospital and settlement locations from OpenStreetMap; populations and bite rates modelled."},
    "benchmark": {"title": "Benchmark district", "geo": False, "window": "6 hours",
                  "note": "Synthetic district (seed 2026) used for the main benchmark and the real-QPU run."},
    "hard": {"title": "Hard case: greedy fails", "geo": False, "window": "6 hours",
             "note": "Synthetic district (seed 82), one of 9 in 100 where greedy misses the optimum."},
}


@lru_cache(maxsize=None)
def district(sid: str):
    if sid == "sanghar":
        return make_sanghar()
    return make_district(2026 if sid == "benchmark" else 82)


def labels(d, sid):
    if sid == "sanghar":
        return d.clinic_labels, d.village_labels
    return d.clinic_names, [f"Village {i + 1}" for i in range(d.n_villages)]


def positions(d, sid):
    if sid == "sanghar":
        return d.clinic_latlon.tolist(), d.village_latlon.tolist(), d.hospital_latlon.tolist()
    # synthetic districts are drawn on a plain km grid: [y, x]
    return (d.clinic_xy[:, ::-1].tolist(), d.village_xy[:, ::-1].tolist(), d.hospital_xy[::-1].tolist())


def plan_payload(d, plan, lam, mu, opt_value, cnames):
    rep = plan_report(d, plan)
    x = np.asarray(plan, bool)
    covered = d.hospital_covers | d.reach[:, x].any(axis=1)
    return {"plan": [int(v) for v in np.asarray(plan).astype(int)], "names": [cnames[i] for i in np.where(x)[0]],
            "score": float(plan_values(d, plan, lam, mu)[0] / opt_value), "covered": covered.astype(int).tolist(),
            **{k: rep[k] for k in ("share_bites_covered", "share_child_bites_covered", "bites_covered_per_year",
                                   "child_bites_covered_per_year", "villages_covered", "new_fridges_needed")}}


@lru_cache(maxsize=256)
def state(sid: str, k: int, lam: float, mu: float) -> dict:
    d = district(sid)
    cnames, vnames = labels(d, sid)
    cpos, vpos, hpos = positions(d, sid)
    bf, gr, rb = brute_force(d, k, lam, mu), greedy(d, k, lam, mu), random_baseline(d, k, lam, mu)
    none = plan_report(d, np.zeros(d.n_clinics, int))
    sweep = []
    for kk in range(1, min(6, d.n_clinics) + 1):
        b = brute_force(d, kk, lam, mu)
        g = greedy(d, kk, lam, mu)
        sweep.append({"k": kk, "optimal": plan_report(d, b["plan"])["share_bites_covered"],
                      "greedy": plan_report(d, g["plan"])["share_bites_covered"]})
    return {
        "scenario": {"id": sid, **SCENARIOS[sid]},
        "k": k, "lam": lam, "mu": mu, "n_qubits": d.n_clinics, "n_valid_plans": bf["n_plans"],
        "clinics": [{"name": cnames[i], "pos": cpos[i], "fridge": bool(d.clinic_fridge[i]),
                     "members": (getattr(d, "clinic_members", None) or [[nm] for nm in cnames])[i],
                     "reach": np.where(d.reach[:, i] & ~d.hospital_covers)[0].tolist()} for i in range(d.n_clinics)],
        "villages": [{"name": vnames[v], "pos": vpos[v], "pop": int(d.village_pop[v]),
                      "bites": float(d.envenomings[v]), "child_bites": float(d.child_envenomings[v]),
                      "hospital": bool(d.hospital_covers[v])} for v in range(d.n_villages)],
        "hospital": {"name": getattr(d, "hospital_label", "District hospital"), "pos": hpos},
        "totals": {"people": int(d.village_pop.sum()), "bites": float(d.envenomings.sum())},
        "hospital_only": {"share_bites_covered": none["share_bites_covered"],
                          "share_child_bites_covered": none["share_child_bites_covered"],
                          "villages_covered": none["villages_covered"]},
        "optimal": plan_payload(d, bf["plan"], lam, mu, bf["value"], cnames),
        "greedy": plan_payload(d, gr["plan"], lam, mu, bf["value"], cnames),
        "random_score": rb["mean"] / bf["value"],
        "supply": sweep,
    }


JOBS: dict[str, dict] = {}
RESTARTS, MAXITER = 3, 160
QCACHE: dict[tuple, dict] = {}


def qaoa_job(jid, sid, k, lam, mu, mixer, reps):
    job = JOBS[jid]
    key = (sid, k, lam, mu, mixer, reps)
    try:
        if key in QCACHE:
            job["progress"] = list(QCACHE[key]["progress"])
            job.update(status="done", result=QCACHE[key]["result"], cached=True)
            return
        d = district(sid)
        cnames, _ = labels(d, sid)
        n = d.n_clinics
        vals = plan_values(d, all_bitstrings(n), lam, mu)
        bf, rb = brute_force(d, k, lam, mu), random_baseline(d, k, lam, mu)

        def cb(restart, n_evals, value):
            job["progress"].append([restart, n_evals, round(float(value), 5)])

        pen = float(d.weights(lam).max()) if mixer == "x" else 0.0
        t0 = time.time()
        r = run_qaoa(d, k, lam, mu, reps=reps, mixer=mixer, penalty=pen, restarts=RESTARTS, maxiter=MAXITER, callback=cb)
        s = summarize(r["probs"], vals, k, bf["value"], rb["mean"], n)
        weight = all_bitstrings(n).sum(axis=1)
        top = np.argsort(-r["probs"])[:10]
        plans = [{"names": [cnames[j] for j in range(n) if (int(i) >> j) & 1], "prob": float(r["probs"][i]),
                  "valid": bool(weight[i] == k), "score": float(vals[i] / bf["value"]) if weight[i] == k else None,
                  "optimal": bool(weight[i] == k and np.isclose(vals[i], bf["value"]))} for i in top]
        # best plan among those the circuit actually outputs (probability > 0.1%)
        seen = (weight == k) & (r["probs"] > 1e-3)
        best = int(np.argmax(np.where(seen, vals, -np.inf)))
        result = {"metrics": s, "top_plans": plans, "seconds": time.time() - t0, "evals": r["n_cost_evals"],
                  "terms": r["n_terms"], "max_order": r["max_term_order"], "qubits": n, "reps": reps, "mixer": mixer,
                  "best_plan": plan_payload(d, all_bitstrings(n)[best], lam, mu, bf["value"], cnames)}
        QCACHE[key] = {"result": result, "progress": list(job["progress"])}
        job.update(status="done", result=result)
    except Exception as ex:  # noqa: BLE001
        job.update(status="error", error=str(ex))


def hardware_payload():
    f = RESULTS / "hardware_run.json"
    if not f.exists():
        return {"available": False}
    data = json.loads(f.read_text())
    data["random_score"] = state("benchmark", 3, 1.0, 0.0)["random_score"]
    return {"available": True, **data}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(UI), **kw)

    def log_message(self, *_):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, default=float).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/state":
                return self._json(state(q.get("s", "sanghar"), int(q.get("k", 3)),
                                        float(q.get("lam", 1.0)), float(q.get("mu", 0.0))))
            if u.path == "/api/job":
                job = JOBS.get(q.get("id", ""))
                if not job:
                    return self._json({"error": "unknown job"}, 404)
                since = int(q.get("since", 0))
                return self._json({"status": job["status"], "progress": job["progress"][since:],
                                   "n": len(job["progress"]), "result": job.get("result"),
                                   "error": job.get("error"), "cached": job.get("cached", False)})
            if u.path == "/api/hardware":
                return self._json(hardware_payload())
        except Exception as ex:  # noqa: BLE001
            return self._json({"error": str(ex)}, 500)
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        u = urlparse(self.path)
        if u.path != "/api/qaoa":
            return self._json({"error": "not found"}, 404)
        n = int(self.headers.get("Content-Length", 0))
        p = json.loads(self.rfile.read(n) or b"{}")
        jid = uuid.uuid4().hex[:10]
        JOBS[jid] = {"status": "running", "progress": []}
        args = (jid, p.get("s", "sanghar"), int(p.get("k", 3)), float(p.get("lam", 1.0)), float(p.get("mu", 0.0)),
                p.get("mixer", "xy"), int(p.get("reps", 2)))
        threading.Thread(target=qaoa_job, args=args, daemon=True).start()
        return self._json({"id": jid})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--window", action="store_true", help="open in a desktop window (pywebview)")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}/"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    state("sanghar", 3, 1.0, 0.0)          # warm the default view

    def warm():                            # pre-train the default QAOA settings so the demo is instant
        for sid in ("benchmark", "hard", "sanghar"):
            for mixer, reps in (("xy", 2), ("xy", 1), ("x", 1), ("xy", 3)):
                jid = f"warm-{sid}-{mixer}-{reps}"
                JOBS[jid] = {"status": "running", "progress": []}
                qaoa_job(jid, sid, 3, 1.0, 0.0, mixer, reps)
    threading.Thread(target=warm, daemon=True).start()
    print(f"Antivenom Within Reach running at {url}  (Ctrl+C to stop)")
    if a.window:
        try:
            import webview
            webview.create_window("Antivenom Within Reach", url, width=1440, height=900, min_size=(1100, 720))
            webview.start()
            return
        except ImportError:
            print("pywebview not installed; opening in the browser instead (pip install pywebview)")
    if not a.no_open:
        webbrowser.open(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
