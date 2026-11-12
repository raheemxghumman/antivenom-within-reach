# Data sources: what is real and what is modelled

This repository uses two kinds of district:

1. **Sanghar, Sindh, Pakistan (real geography)** — `avr/sanghar.py`, `data/sanghar_osm.json`.
2. **Synthetic benchmark districts** — `avr/instance.py` (seed 2026 = main benchmark,
   seed 82 = hard case where greedy fails, seeds 0–99 = greedy statistics).

The model and solvers are identical for both; only the input data changes.

## Sanghar district (real geography)

| Item | Real or modelled | Source / value |
|---|---|---|
| Locations and names of 15 government Basic Health Units | **Real** | OpenStreetMap, Overpass API extract, bbox 25.70–26.40 N, 68.70–69.50 E, fetched 12 Nov 2026 |
| Location of the Civil Hospital, Sanghar (district hospital) | **Real** | OpenStreetMap (tagged "سول ہسپتال", Civil Hospital) |
| Locations and names of 72 settlements (city, towns, villages, hamlets) | **Real** | OpenStreetMap `place=*` nodes |
| Population of Sanghar city (75,410) and Khipro town (51,081) | **Real** | OpenStreetMap `population` tags |
| Population of other settlements | Modelled | log-normal, median 1,500 (village) / 300 (hamlet); 20,000 for towns without a tag |
| Envenoming incidence | Modelled | 100–350 per 100,000 per year (same range as below) |
| Share of people under 15 | Modelled | 36–46% (Pakistan's population is ~35–40% under 15) |
| Travel speed | Modelled | 15 km/h cart / qingqi (30%), 25 km/h motorbike (50%), 40 km/h car / ambulance (20%) |
| Road detour factor | Modelled | 1.35 × straight-line distance |
| Time window | Modelled | **1 hour** of travel (facilities are close together, so a 6-hour window would cover almost everyone) |
| Which BHUs already have a fridge | Modelled | random, ~50% |
| Candidate sites | Rule | all 15 BHUs; BHUs closer than 8 km are merged into one site (they serve overlapping villages) → 9 sites = 9 qubits. Private GP clinics and small dispensaries are excluded |

Map data © OpenStreetMap contributors, available under the Open Database License (ODbL).

## Synthetic benchmark districts

No village, clinic or person in these is real. Parameters are drawn from the ranges below, so
the scale is realistic.

## Burden (why the problem matters)

| Fact | Source |
|---|---|
| ~5.4 million snakebites a year, 1.8–2.7 million envenomings, 81,410–137,880 deaths | [WHO fact sheet: Snakebite envenoming](https://www.who.int/news-room/fact-sheets/detail/snakebite-envenoming) |
| Agricultural workers and children are the most affected; children often suffer more severe effects because of their smaller body mass | WHO fact sheet (above) |
| WHO goal: halve deaths and disability from snakebite by 2030 | WHO snakebite strategy (2019) |
| India: ~58,000 snakebite deaths a year (2000–2019) | Suraweera et al., *eLife* 2020 |
| Ghana: antivenom stock-outs were less likely at facilities served by drone delivery (about 30%) than at those without (about 73%) | Study of Zipline deliveries in Ghana (see report) |
| Sub-Saharan Africa: ~314,000 envenomings a year, 95% in rural areas | Chippaux, *Toxicon* 2011 (meta-analysis) |

## Parameters used in `avr/instance.py`

| Parameter | Value or range used | Basis |
|---|---|---|
| Envenoming incidence | 100–350 per 100,000 people per year (per village, uniform) | Chippaux reports 100–650 bites per 100,000/yr for Africa; a Côte d'Ivoire rural survey found ~130 (savanna) to ~195 (forest) |
| Village population | log-normal, median ~1,100, clipped 200–5,000 | typical rural village sizes (assumption) |
| Share of people under 15 | 38–52% | sub-Saharan Africa age structure (~40–45% under 15) |
| Delay before travel (deciding, traditional healer, finding transport) | 0.5–2.5 h | assumption; delays to care are widely reported |
| Travel speed | 4 km/h on foot (40%), 8 km/h bicycle/cart (40%), 15 km/h motorbike (20%) | assumption |
| Road distance / straight-line distance | 1.35 | common detour factor (assumption) |
| Treatment window | 6 hours | time-to-antivenom target used by access studies (e.g. Duke/NIH Fogarty work in the Amazon) |
| Clinics with a working 2–8 °C fridge | ~50% (random) | liquid antivenom needs a cold chain; many rural facilities lack reliable power (WHO/IRENA 2023) |

Sources from the literature search:
[MDPI TropicalMed 9(4):68](https://www.mdpi.com/2414-6366/9/4/68),
[Chippaux, Snakebite in Africa](https://www.taylorfrancis.com/chapters/edit/10.1201/9780429054204-44/snakebite-africa-jean-philippe-chippaux),
[MSF briefing paper](https://www.msf.org.za/sites/default/files/briefing_paper_snakebite_070915.pdf).
