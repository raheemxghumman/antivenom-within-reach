# 3-minute video script (hard limit 3:00 — aim for 2:45)

Record the screen with the voice-over. Show the app (`streamlit run app.py`) and the figures in
`results/`. Speak slowly; the word counts below fit the timings at ~150 words/minute.

| Time | On screen | Say |
|---|---|---|
| 0:00–0:20 | Title card: "Antivenom Within Reach". Then the app's map, hospital only (orange villages). | "Every year snakebites kill between eighty and a hundred and forty thousand people, most of them rural farmers and children. Antivenom saves lives only if it arrives within hours. But a rural district can only afford to stock a few clinics. Which ones?" |
| 0:20–0:45 | App sidebar: k slider, child weight λ, fridge cost μ. | "We model one district: thirty villages, nine candidate clinics, one hospital. Each clinic is a yes-or-no choice: one qubit. We maximise the bites that reach antivenom within six hours, a child's bite counts double, a new solar fridge has a cost, and exactly k clinics can be stocked. The data are synthetic, drawn from published WHO and field-study ranges." |
| 0:45–1:10 | README formula block, or a slide: covered = 1 − Π(1 − x). | "The hard part is overlap. A village two clinics can reach must count once, not twice. That makes the objective quadratic, even cubic, and it is why a greedy choice can fail. We turn it into an exact quantum Hamiltonian, with three-body terms and no extra qubits, and we verify it matches the classical objective for all 512 plans." |
| 1:10–1:40 | `results/qaoa_depth.png` | "We solve it with QAOA in Qiskit. Standard QAOA with a penalty for the budget did no better than random: many shots broke the budget. So we used a constraint-preserving version: start in a superposition of only valid plans and mix with XY gates. Every shot is a valid plan, and the optimal plan becomes six times more likely than random, ten times with CVaR." |
| 1:40–2:10 | App: select "Hard case: greedy fails", show greedy plan, then optimal, then press Run QAOA. | "Is this problem even hard? On a hundred random districts, greedy missed the best plan nine times, by up to eleven percent. Here is one. Greedy covers eighty-one percent of bites; the optimum covers eighty-five. QAOA finds the optimal plan and samples it." |
| 2:10–2:30 | Main district map, optimal plan (green villages). | "In our main district, stocking three well-chosen clinics raises the share of bites within six hours of antivenom from forty-nine to eighty-three percent: about thirty more people a year treated in time." |
| 2:30–2:50 | Noise table from the report. Then limitations bullets. | "We are honest about the limits. Nine qubits are easy for a laptop, so we claim no speed-up. Under a real IBM Heron noise model, our best circuit is too deep, and its advantage disappears. The data are synthetic. Next: real road data and hardware-efficient mixers." |
| 2:50–3:00 | GitHub repo page. | "Everything is reproducible from our GitHub repo. Antivenom Within Reach: putting scarce medicine where it saves the most lives." |

Checklist before uploading: under 3:00, audio clear, Google Drive sharing set to
"Anyone with the link", link pasted into the report and the submission form.
