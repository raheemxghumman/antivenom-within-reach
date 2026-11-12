# 3-minute video script (hard limit 3:00 — aim for 2:50)

**Setup before recording**
1. `python app.py` → the app opens at http://127.0.0.1:8765. Wait ~3 minutes once so the
   default QAOA runs are pre-trained (then "Run QAOA" replays instantly). Full-screen the browser.
2. Have a second tab open on the IBM Quantum Platform → **Workloads**, showing job
   `dbqtg71abdes73fot410` on ibm_marrakesh (proof of the real run).
3. Record screen + voice (OBS, Xbox Game Bar `Win+Alt+R`, or Loom). Speak at ~150 words/min.

| Time | On screen | Say |
|---|---|---|
| 0:00–0:18 | App opens on **Sanghar, Sindh**, click **Hospital only** — map turns mostly orange. | "Every year snakebites kill between eighty and a hundred and forty thousand people — mostly farmers and children. Antivenom saves them only if it arrives in time. This is Sanghar district in Sindh: real health units and villages from OpenStreetMap. With antivenom only at the Civil Hospital, just fifty-two percent of bites reach it within an hour." |
| 0:18–0:40 | Click **Optimal** — villages turn green, links animate, KPIs count up to 86.7% / +214. | "A district can stock only a few Basic Health Units. Which three? Choose well, and coverage jumps to eighty-seven percent — about two hundred more people a year treated in time. Each health unit is one qubit: stock it or not." |
| 0:40–1:05 | **Method** tab: point at step 3 (overlap) and step 4 (exact Hamiltonian). | "The hard part is overlap. A village two clinics can reach must count once, not twice. That makes the problem a polynomial — and it is why simply picking the best clinics one by one can fail. We turn it into an exact quantum Hamiltonian, with three-body and higher terms and no extra qubits, verified equal to brute force on every plan." |
| 1:05–1:35 | Switch to **Benchmark**. **Quantum solver** tab, XY mixer, p = 2, click **Run QAOA**: training curve animates, top-plans bars grow, "QAOA found the optimal plan" toast. Point at "100% valid shots" and "× a random plan". | "We solve it with QAOA in Qiskit. Standard QAOA needs a penalty for the budget, and wastes most shots on illegal plans. Our version uses an XY mixer that keeps exactly three clinics on — every shot is a valid plan — and makes the optimal plan several times more likely than chance — up to ten times with CVaR. On the real Sanghar map, it raises the average plan quality from 0.65 to about 0.73 of the optimum." |
| 1:35–1:55 | Switch to **Hard case**, show **Greedy** then **QAOA** plan. | "Is it even hard? On a hundred districts, the greedy method misses the best plan nine times, by up to eleven percent. Here greedy covers eighty-one percent; QAOA finds the optimal plan at eighty-five." |
| 1:55–2:25 | **Real QPU** tab: job ID, bar chart. Then cut to the IBM Workloads tab showing the job. | "And we ran it on a real IBM quantum computer — ibm_marrakesh, a 156-qubit Heron processor. This is the job. Our hardware-friendly ring-XY circuit used half the two-qubit gates of standard QAOA and kept seventy-one percent of shots inside the budget, versus thirty-one percent — matching our noise-model prediction." |
| 2:25–2:45 | README "Honest limitations" section or report page. | "We're honest about the limits: nine qubits are easy for a laptop, so we claim no speed-up; populations and bite rates are modelled, because no one publishes snakebites per village; and noise still erodes deep circuits. Next: real district health data and error mitigation." |
| 2:45–2:55 | GitHub repo page. | "Everything is reproducible from our repository. Antivenom Within Reach — putting scarce medicine where it saves the most lives." |

**Before uploading:** length ≤ 3:00 · audio clear · upload to Google Drive · Share → "Anyone with
the link" → Viewer · paste the link into the README (Demo video section), the report title page
and the submission form · open the link in an incognito window to check it plays.
