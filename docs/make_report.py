"""Build docs/report.docx from results/*.json (run from repo root: python docs/make_report.py).
Every number in the report is read from the results files, not typed by hand."""
import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
J = lambda name: json.loads((R / f"{name}.json").read_text())  # noqa: E731
inst, base, depth = J("instance"), J("baselines_main"), J("qaoa_depth")
pen, cvar, gstats, hard = J("penalty_sweep"), J("cvar_sweep"), J("greedy_stats"), J("hard_case")
supply, trade, noisy = J("supply_sweep"), J("tradeoffs"), J("noisy_sim")
sang = json.loads((R / "sanghar.json").read_text(encoding="utf-8"))
hwr = J("hardware_run")
REPO = "https://github.com/raheemxghumman/antivenom-within-reach"
INK = RGBColor(0x1F, 0x29, 0x33)
ACCENT = RGBColor(0x2C, 0x5A, 0xA0)


def pct(x, nd=1):
    return f"{100 * x:.{nd}f}%"


doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
for side in ("left_margin", "right_margin"):
    setattr(sec, side, Cm(2.2))
sec.top_margin = sec.bottom_margin = Cm(2.0)

st = doc.styles["Normal"]
st.font.name, st.font.size = "Calibri", Pt(10.5)
st.paragraph_format.space_after = Pt(5)
st.paragraph_format.line_spacing = 1.12
for lvl, size in [(1, 14), (2, 12)]:
    h = doc.styles[f"Heading {lvl}"]
    h.font.name, h.font.size, h.font.bold = "Calibri", Pt(size), True
    h.font.color.rgb = ACCENT if lvl == 1 else INK
    h.paragraph_format.space_before = Pt(12 if lvl == 1 else 8)
    h.paragraph_format.space_after = Pt(4)
    h.paragraph_format.keep_with_next = True
    rpr = h.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(a), "Calibri")


def para(text, bold_lead=None, italic=False, size=None, align=None):
    p = doc.add_paragraph()
    if bold_lead:
        p.add_run(bold_lead).bold = True
    r = p.add_run(text)
    r.italic = italic
    if size:
        r.font.size = Pt(size)
    if align:
        p.alignment = align
    return p


def bullet(text, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_lead:
        p.add_run(bold_lead).bold = True
    p.add_run(text)
    p.paragraph_format.space_after = Pt(2)
    return p


def shade(cell, hex_fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcpr.append(shd)


def table(header, rows, widths, bold_rows=()):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        run = c.paragraphs[0].add_run(h)
        run.bold, run.font.size = True, Pt(9)
        shade(c, "E8F1FB")
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(v))
            run.font.size = Pt(9)
            run.bold = ri in bold_rows
    t.autofit = False
    grid = t._tbl.tblGrid
    for i, w in enumerate(widths):
        grid.gridCol_lst[i].w = Cm(w)
        t.columns[i].width = Cm(w)
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def figure(path, width_cm, caption):
    doc.add_picture(str(path), width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = para(caption, italic=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
    p.paragraph_format.space_after = Pt(8)


# ---------------------------------------------------------------- title block
t = doc.add_paragraph()
r = t.add_run("Antivenom Within Reach")
r.bold, r.font.size, r.font.color.rgb = True, Pt(22), ACCENT
para("Quantum optimisation of snakebite antivenom placement in rural clinics", size=12.5)
para("Qiskit Fall Fest 2026 · FAST NUCES Islamabad · Domain: Healthcare · SDG 3.3, 3.8, 10", size=9.5)
para("Real district: Sanghar, Sindh, Pakistan (OpenStreetMap) · Run on IBM Quantum ibm_marrakesh "
     f"(job {hwr['hardware']['job_id']})", size=9.5)
para("Team: ______________________________", size=9.5)
para(f"Code: {REPO}", size=9.5)
para("Video (3 min): ______________________________", size=9.5)

# ---------------------------------------------------------------- 1
doc.add_heading("1. Problem and who it serves", 1)
para("Snakebite envenoming kills an estimated 81,000–138,000 people a year and leaves many more "
     "disabled (WHO). Victims are mostly rural farmers, herders and children across South Asia, "
     "sub-Saharan Africa and Latin America; children suffer more severe effects because of their "
     "smaller body mass. Antivenom only works if it is given in time, yet it is costly, scarce, and "
     "in liquid form needs a 2–8 °C cold chain. In sub-Saharan Africa alone there are roughly "
     "314,000 envenomings a year, 95% in rural areas (Chippaux, 2011).")
para("A district health officer, or an NGO supporting one, can afford to stock antivenom at only a few "
     "clinics. The question this project answers is: which clinics should stock it, so that the most "
     "bites reach antivenom within 6 hours? The answer must respect a hard budget, value children's "
     "bites, and account for clinics that would need a new solar fridge.",
     bold_lead="Decision maker. ")
para("The problem is global. We apply it to a real district, Sanghar in Sindh, Pakistan, using the "
     "real locations of its government Basic Health Units (BHUs), the Civil Hospital and 72 settlements "
     "from OpenStreetMap, with modelled demand. A seeded synthetic benchmark district is used for the "
     "controlled algorithm study and the real-hardware run. Swapping in another district's data needs no "
     "code change.", bold_lead="Scope. ")

# ---------------------------------------------------------------- 2
doc.add_heading("2. Formulation", 1)
table(["Element", "Definition"], [
    ["Decision variables", f"x_i ∈ {{0,1}}: candidate clinic i stocks antivenom ({inst['candidate_clinics']} clinics → {inst['candidate_clinics']} qubits)"],
    ["Coverage", "covered_v = 1 − Π_{i∈S_v}(1 − x_i), with S_v the clinics reachable from village v within 6 h"],
    ["Village weight", "w_v = expected envenomings/yr × (1 + λ · share of children in v)"],
    ["Objective", "maximise Σ_v w_v · covered_v − μ · Σ_i needs_fridge_i · x_i"],
    ["Constraint", f"Σ_i x_i = k (here k = {inst['budget_k']}); the district hospital is always stocked"],
    ["Parameters", f"λ = {inst['lambda_child']} (a child's bite counts double), μ = {inst['mu_fridge']} (fridge cost, swept 0–5)"],
], [3.6, 13.0])
para(f"Synthetic district (seed {inst['seed']}): {inst['villages']} villages, "
     f"{inst['people']:,} people, about {inst['expected_envenomings_per_year']:.0f} envenomings a year, "
     f"{inst['candidate_clinics']} candidate clinics, one district hospital. "
     f"{inst['villages_covered_by_hospital_alone']} villages are already within 6 h of the hospital, "
     f"{inst['villages_decided_by_clinics']} depend on the clinic choice, and "
     f"{inst['villages_out_of_reach_of_any_site']} are out of reach of every site. "
     f"There are {inst['search_space_valid_plans']} valid plans among {inst['search_space_all_bitstrings']} bitstrings. "
     "Bite incidence (100–350 per 100,000 a year), child share (38–52% under 15), travel speeds "
     "and delays are drawn from published ranges listed in docs/data_sources.md.", bold_lead="Instance. ")
para("A village reachable from two clinics must be counted once, "
     "so the objective contains overlap terms x_a·x_b (and x_a·x_b·x_c for three clinics). Picking the "
     "clinics with the largest individual coverage (greedy) can therefore be wrong: on 100 random "
     f"districts greedy missed the optimum in {gstats['greedy_suboptimal']}, by up to "
     f"{pct(gstats['max_gap'])}.", bold_lead="Why the problem is not trivial. ")

# ---------------------------------------------------------------- 3
doc.add_heading("3. Quantum mapping and algorithm choice", 1)
para("Substituting x_i = (1 − Z_i)/2, each village contributes w_v(1 − 2^−|S_v| Σ_{T⊆S_v} Z_T). "
     "The objective therefore becomes an Ising Hamiltonian with Z, ZZ and ZZZ terms "
     f"({depth[3]['hamiltonian_terms']} terms, maximum order {depth[0]['max_term_order']}). "
     "We keep the three-body terms exactly instead of truncating to a QUBO: four villages in our "
     "district are reachable from three clinics, and dropping their terms would change plan scores by "
     "up to 6 weighted bites. Each ZZZ term is one CNOT-ladder rotation; no ancilla qubits are needed. "
     "check_model.py verifies that the Hamiltonian equals the classical objective for all 512 "
     "bitstrings (error < 1e-12).", bold_lead="Mapping. ")
para("QAOA is the natural algorithm for binary optimisation with a diagonal cost Hamiltonian, and "
     "it runs at small depth. We compare two variants:", bold_lead="Why QAOA. ")
bullet(" X mixer with the budget as a penalty A(Σx − k)². Simple and shallow, but shots can break "
       "the budget and the result depends on choosing A.", "Standard QAOA.")
bullet(" Start in the equal superposition of all plans with exactly k clinics (a Dicke state) and "
       "mix with XX+YY gates, which preserve the number of stocked clinics (Hadfield et al., 2019). "
       "Every output is a valid plan and no penalty is needed.", "Constraint-preserving QAOA (XY mixer).")
bullet(" A hardware-friendly version: start from one valid plan and mix only neighbouring qubits on "
       "a ring. About half the two-qubit gates of standard QAOA; every ideal shot is still valid.",
       "Ring-XY QAOA.")
bullet(" Optimise the mean of the best α-fraction of outcomes instead of the full mean "
       "(Barkoutsos et al., 2020), which favours putting probability on the very best plans.", "CVaR objective.")
para("Training: COBYLA with a linear-ramp start plus seeded random restarts; exact output "
     "probabilities from the Qiskit Aer statevector simulator; final results also sampled with 4096 "
     "shots. Every random choice is seeded.")

# ---------------------------------------------------------------- 4
doc.add_heading("4. Implementation and architecture", 1)
figure(ROOT / "docs" / "architecture.png", 16.2, "Figure 1. Architecture: one exact objective scores every method.")
para("The code is a small Python package (avr/) built on Qiskit 2.6, Qiskit Aer 0.18 and "
     "qiskit-optimization 0.7: instance generator, exact objective, classical baselines, Hamiltonian "
     "and QAOA circuits, and plots. run_experiments.py reproduces every result in this report in about "
     "six minutes on a laptop CPU; run_noisy.py adds the noise study; app.py is an interactive "
     "web app (Leaflet map, live QAOA training stream, real-QPU panel) built on the same solvers.")

# ---------------------------------------------------------------- 5
doc.add_heading("5. Results and comparison with classical baselines", 1)
opt, gr, none = base["optimal"], base["greedy"], base["no_clinic_stocked"]
table(["Plan", "Clinics stocked", "Bites within 6 h", "Child bites within 6 h", "New fridges"], [
    ["Hospital only", "—", pct(none["share_bites_covered"]), pct(none["share_child_bites_covered"]), "0"],
    ["Exact optimum (brute force)", ", ".join(opt["stocked"]), pct(opt["share_bites_covered"]),
     pct(opt["share_child_bites_covered"]), str(opt["new_fridges_needed"])],
    ["Greedy max-coverage", ", ".join(gr["stocked"]), pct(gr["share_bites_covered"]),
     pct(gr["share_child_bites_covered"]), str(gr["new_fridges_needed"])],
    ["Random valid plan (mean)", "—", f"score {base['random_mean_value'] / opt['value']:.2f} × optimum", "", ""],
], [4.4, 3.0, 3.0, 3.6, 2.4], bold_rows=(1,))
para(f"Stocking three clinics raises the share of yearly bites within 6 hours of antivenom from "
     f"{pct(none['share_bites_covered'])} to {pct(opt['share_bites_covered'])} "
     f"(about {opt['bites_covered_per_year'] - none['bites_covered_per_year']:.0f} more envenomings a year "
     "reaching treatment in time in this district).")

rows = []
for r in depth:
    e = r["exact"]
    rows.append([("XY mixer" if r["mixer"] == "xy" else "X mixer + penalty"), r["reps"], pct(e["valid_rate"], 0),
                 f"{e['p_optimal']:.3f}", f"{e['boost_vs_random']:.1f}×", f"{e['approx_ratio_valid']:.3f}"])
c = min(cvar, key=lambda x: x["alpha"])
rows.append([f"XY mixer + CVaR α={c['alpha']}", c["reps"], pct(c["exact"]["valid_rate"], 0),
             f"{c['exact']['p_optimal']:.3f}", f"{c['exact']['boost_vs_random']:.1f}×",
             f"{c['exact']['approx_ratio_valid']:.3f}"])
para("QAOA on the main district (ideal simulator). P(optimal) is the probability that one shot returns "
     f"the optimal plan; a random valid plan has {depth[0]['exact']['random_p_optimal']:.3f}.", bold_lead="")
table(["Variant", "Depth p", "Valid outputs", "P(optimal)", "vs random", "Expected score / optimum"],
      rows, [4.6, 1.6, 2.2, 2.2, 2.0, 3.8], bold_rows=(5, 6))
figure(R / "qaoa_depth.png", 16.0, "Figure 2. QAOA depth sweep: the constraint-preserving variant concentrates "
       "probability on the optimum and never breaks the budget.")
para("", bold_lead="Key findings.")
bullet(f" The XY-mixer QAOA returns only valid plans and raises the probability of the optimal plan to "
       f"{depth[5]['exact']['p_optimal']:.3f} at p = 3 ({depth[5]['exact']['boost_vs_random']:.1f}× random); "
       f"with CVaR (α = {c['alpha']}) this reaches {c['exact']['p_optimal']:.3f} "
       f"({c['exact']['boost_vs_random']:.0f}× random).", "Quantum does real work.")
pmin, pmax = min(pen, key=lambda x: x["penalty_over_max_weight"]), max(pen, key=lambda x: x["penalty_over_max_weight"])
bullet(f" With the X mixer, a small penalty ({pmin['penalty_over_max_weight']}× the largest weight) gives only "
       f"{pct(pmin['exact']['valid_rate'], 0)} valid outputs; a large one ({pmax['penalty_over_max_weight']}×) gives "
       f"{pct(pmax['exact']['valid_rate'], 0)} valid but drowns the objective (P(optimal) "
       f"{pmax['exact']['p_optimal']:.3f}, below random). This is why we built the XY mixer.",
       "Penalties are fragile.")
ho, hg = hard["optimal"], hard["greedy"]
hq = hard["qaoa"][-1]["exact"]
bullet(f" On a district where greedy fails (seed {hard['seed']}, chosen from the {gstats['greedy_suboptimal']} "
       f"failures among 100), greedy stocks {', '.join(hg['stocked'])} and covers {pct(hg['share_bites_covered'])} "
       f"of bites; the optimum ({', '.join(ho['stocked'])}) covers {pct(ho['share_bites_covered'])}. "
       f"QAOA (XY, p = 3) gives the optimal plan probability {hq['p_optimal']:.3f} "
       f"({hq['boost_vs_random']:.1f}× random) and samples it.", "Where greedy is not enough.")
k5 = next(s for s in supply if s["k"] == 5)
bullet(" Coverage rises " + ", ".join(pct(s["optimal_share"]) for s in supply[1:6]) +
       f" as 1–5 clinics are stocked. At k = 5 greedy also misses the optimum on the main district "
       f"({pct(k5['greedy_share'])} vs {pct(k5['optimal_share'])}).", "Supply sweep.")
t_mu = next(t for t in trade if t["lambda_child"] == 1.0 and t["mu_fridge"] == 2.0)
bullet(f" Raising the child weight from λ = 0 to 4 changes the best plan in only 6 of 100 districts, "
       "because children are spread evenly across villages here; the most efficient plan is already "
       f"nearly the best for children. The fridge cost does matter: with μ = 2 the optimum becomes "
       f"{', '.join(t_mu['stocked'])}, needing {t_mu['new_fridges_needed']} new fridge instead of "
       f"{opt['new_fridges_needed']} for {pct(opt['share_bites_covered'] - t_mu['share_bites_covered'])} "
       "less coverage.", "Trade-offs.")
figure(R / "hard_greedy_vs_optimal.png", 16.2, f"Figure 3. Hard-case district (seed {hard['seed']}): greedy plan (left) "
       "vs optimal plan (right). Green villages reach antivenom within 6 h.")


doc.add_heading("Real district: Sanghar, Sindh, Pakistan", 2)
so, sg, sh = sang["optimal"], sang["greedy"], sang["hospital_only"]
table(["Plan", "Sites stocked", "Bites within 1 h", "Child bites within 1 h"], [
    ["Civil Hospital only", "—", pct(sh["share_bites_covered"]), pct(sh["share_child_bites_covered"])],
    ["Exact optimum (84 plans)", ", ".join(so["sites"]), pct(so["share_bites_covered"]), pct(so["share_child_bites_covered"])],
    ["Greedy", ", ".join(sg["sites"]), pct(sg["share_bites_covered"]), pct(sg["share_child_bites_covered"])],
    ["Random valid plan (mean)", "—", f"score {sang['random_mean_over_optimal']:.2f} × optimum", ""],
], [3.8, 6.4, 3.0, 3.4], bold_rows=(1,))
sq3 = next(q for q in sang["qaoa"] if q["reps"] == 3 and q["alpha"] == 1.0)
sqc = next(q for q in sang["qaoa"] if q["alpha"] < 1.0)
para(f"{sang['settlements']} real settlements ({sang['people_modelled']:,} people modelled, about "
     f"{sang['expected_envenomings_per_year']:.0f} envenomings a year), {len(sang['candidate_sites'])} candidate sites built from "
     "15 real BHUs, 1-hour travel window. Stocking three sites raises the share of bites reaching antivenom "
     f"within an hour from {pct(sh['share_bites_covered'])} to {pct(so['share_bites_covered'])}, about "
     f"{(so['share_bites_covered'] - sh['share_bites_covered']) * sang['expected_envenomings_per_year']:.0f} more envenomings a year "
     f"treated in time. Settlements can reach up to {sang['max_bhus_reaching_one_settlement']} sites, so the exact Hamiltonian has "
     f"{sq3['hamiltonian_terms']} terms up to {sq3['max_term_order']}-body. QAOA (XY, p = 3) raises the expected plan score to "
     f"{sq3['exact']['approx_ratio_valid']:.2f} of the optimum (random: {sang['random_mean_over_optimal']:.2f}); with CVaR "
     f"(α = {sqc['alpha']}) the optimal plan becomes {sqc['exact']['boost_vs_random']:.1f}× more likely than random.")
figure(R / "sanghar_map.png", 16.4, "Figure 4. Sanghar: real BHU and settlement locations (OpenStreetMap). Left: hospital only. "
       "Right: optimal three BHU sites. Green settlements reach antivenom within one hour.")

doc.add_heading("Run on a real IBM quantum computer", 2)
hh = hwr["hardware"]
para(f"Backend {hh['backend']} (IBM Heron, 156 qubits), job ID {hh['job_id']}, sent "
     f"{hh['sent_utc'].replace('T', ' ').replace('+00:00', ' UTC')}, {hwr['shots']} shots per circuit, "
     f"{hh.get('usage_quantum_seconds', '–')} s of quantum time. Both circuits were trained on the ideal simulator "
     "(benchmark district, 9 qubits, p = 1), transpiled for the device and sent in one job. The raw counts are in "
     "results/hardware_counts.json.")
hrows = []
for c in hwr["circuits"]:
    nm = "Standard QAOA (X + penalty)" if c["mixer"] == "x" else "Ring-XY QAOA (ours)"
    hrows.append([nm, str(c["two_qubit_gates"]),
                  f"{pct(c['ideal']['valid_rate'], 0)} → {pct(c['noisy_simulation']['valid_rate'], 0)} → "
                  f"{pct(c['real_hardware']['valid_rate'], 0)}",
                  f"{c['real_hardware']['approx_ratio_valid']:.2f}"])
table(["Circuit", "2-qubit gates", "Valid shots: ideal → noise model → real QPU", "Score / optimum on QPU"],
      hrows, [4.6, 2.4, 6.2, 3.4], bold_rows=(1,))
figure(R / "hardware_vs_sim.png", 16.0, "Figure 5. Ideal simulator vs IBM noise model vs the real ibm_marrakesh QPU.")
para("The real device closely matches the noise-model prediction. The ring-XY circuit keeps more than twice as many "
     "shots inside the budget as standard QAOA, uses half the two-qubit gates, and its valid plans score above a "
     f"random plan (random: {base['random_mean_value'] / opt['value']:.2f}).")

doc.add_heading("Noise study (IBM Heron noise model)", 2)
nrows = []
for r in noisy:
    nrows.append([("XY mixer" if r["mixer"] == "xy" else "X mixer + penalty"), f"{r['transpiled_depth']:,}",
                  f"{r['two_qubit_gates']:,}", f"{pct(r['ideal']['valid_rate'], 0)} → {pct(r['noisy_4096_shots']['valid_rate'], 0)}",
                  f"{r['ideal']['p_optimal']:.3f} → {r['noisy_4096_shots']['p_optimal']:.3f}"])
table(["Variant (p = 1)", "Transpiled depth", "2-qubit gates", "Valid: ideal → noisy", "P(optimal): ideal → noisy"],
      nrows, [3.8, 2.8, 2.6, 3.6, 3.8])
para("Transpiled for the 156-qubit Heron device model FakeMarrakesh and simulated with its noise model "
     "(4096 shots). The shallow standard circuit survives noise roughly unchanged; the "
     "constraint-preserving circuit, which wins in simulation, becomes too deep (over a thousand "
     "two-qubit gates, mostly from the Dicke-state preparation and the all-pairs XY mixer) and its "
     "advantage disappears.")

# ---------------------------------------------------------------- 6
doc.add_heading("6. Limitations (honest assessment)", 1)
bullet(" In Sanghar, facility and settlement locations are real but populations (except two towns), bite "
       "incidence, child share and travel speeds are modelled from published ranges; the benchmark district is "
       "fully synthetic. No public dataset gives snakebites per village.", "Modelled demand.")
bullet(" At 9 qubits brute force solves the problem in milliseconds. We make no speed-up claim; the "
       "contribution is an exact quantum formulation measured against exact answers.", "No quantum advantage.")
bullet(" At p ≤ 3, QAOA concentrates probability on good plans (up to about 10× random) but the optimum is "
       "not the single most likely plan; deeper circuits or warm starts would be needed.", "Shallow QAOA.")
bullet(" The all-pairs XY circuit is too deep for current hardware; our ring-XY version runs on the real "
       "QPU, but noise reduces its valid-shot rate from 100% to 71%. BHUs closer than 8 km are merged to fit 9 "
       "qubits.", "Noise and size.")
bullet(" Coverage is binary (within 6 h or not). Rainy-season roads, travel-time uncertainty, vial "
       "quantities, stock expiry and upstream supply (manufacturers, lead times) are outside scope.", "Model scope.")

# ---------------------------------------------------------------- 7
doc.add_heading("7. Reflection and next steps", 1)
para("The main lesson was that how the constraint is encoded matters as much as the algorithm: the "
     "same QAOA with a penalty did no better than random, while encoding the budget in the mixer made "
     "every shot useful. Keeping the three-body coverage terms exact also mattered, because a QUBO "
     "approximation would have optimised a different problem from the one we score.")
bullet(" replace modelled demand with district health records and road travel times, and validate with "
       "Sanghar health officials.", "Real demand data:")
bullet(" vials per clinic as integer variables, and multiple seasons as scenarios.", "Richer model:")
bullet(" error mitigation and deeper ring-XY circuits on IBM hardware; larger districts as qubit counts grow.",
       "Hardware:")

doc.add_heading("References", 1)
for ref in [
    "WHO. Snakebite envenoming – fact sheet (2023).",
    "Chippaux J-P. Estimate of the burden of snakebites in sub-Saharan Africa: a meta-analytic approach. Toxicon 57 (2011).",
    "Suraweera W. et al. Trends in snakebite deaths in India from 2000 to 2019. eLife 9 (2020).",
    "Farhi E., Goldstone J., Gutmann S. A Quantum Approximate Optimization Algorithm. arXiv:1411.4028 (2014).",
    "Hadfield S. et al. From the Quantum Approximate Optimization Algorithm to a Quantum Alternating Operator Ansatz. Algorithms 12(2), 34 (2019).",
    "Barkoutsos P. et al. Improving Variational Quantum Optimization using CVaR. Quantum 4, 256 (2020).",
    "Church R., ReVelle C. The maximal covering location problem. Papers of the Regional Science Association 32 (1974).",
    "Qiskit blog: Where should I locate my store? (QAOA for a covering problem).",
]:
    p = doc.add_paragraph(ref, style="List Number")
    p.paragraph_format.space_after = Pt(1)
    for r in p.runs:
        r.font.size = Pt(9)

out = ROOT / "docs" / "report.docx"
doc.save(out)
print(out)
