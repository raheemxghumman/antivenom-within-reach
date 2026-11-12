"""A real-geography district: Sanghar, Sindh, Pakistan (OpenStreetMap data).

Real (from OpenStreetMap, data/sanghar_osm.json, (c) OpenStreetMap contributors, ODbL):
  * locations and names of government Basic Health Units (BHUs) and of the Civil Hospital, Sanghar
  * locations and names of the 72 mapped settlements; populations of Sanghar city and Khipro town
Modelled (seeded, documented in docs/data_sources.md):
  * populations of settlements OpenStreetMap does not give, bite incidence, child share,
    travel speed and road detour factor, which clinics already have a fridge.

Candidate clinics: every BHU in the extract; BHUs less than 8 km apart are merged into one
site (they serve overlapping villages; antivenom would be held at one of them). This keeps
the problem at 9 candidate sites = 9 qubits. Private GP clinics and small dispensaries are excluded
because antivenom must be given where staff can treat a severe reaction.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .instance import District

DATA = Path(__file__).resolve().parents[1] / "data" / "sanghar_osm.json"
LAT0, LON0 = 25.70, 68.70          # south-west corner of the extract
KM_PER_DEG_LAT = 110.57
KM_PER_DEG_LON = 111.32 * np.cos(np.radians(26.05))
POP_DEFAULT = {"village": 1500, "hamlet": 300, "town": 20000, "city": 75000}


def to_km(lat, lon):
    return np.c_[(np.asarray(lon) - LON0) * KM_PER_DEG_LON, (np.asarray(lat) - LAT0) * KM_PER_DEG_LAT]


def is_bhu(name: str) -> bool:
    n = name.lower()
    return "basic health unit" in n or n.startswith("bhu ")


def short_name(name: str) -> str:
    n = name.replace("Basic Health Unit ", "").replace("BHU ", "").strip()
    return n.title() if n.isupper() else n


def load_osm():
    return json.loads(DATA.read_text(encoding="utf-8"))


def candidate_sites(osm, merge_km=8.0):
    """BHUs, merged when closer than merge_km. Returns names, lat, lon (merged = mean)."""
    bhus = [f for f in osm["facilities"] if is_bhu(f["name"])]
    xy = to_km([f["lat"] for f in bhus], [f["lon"] for f in bhus])
    groups, used = [], set()
    for i in range(len(bhus)):
        if i in used:
            continue
        g = [i] + [j for j in range(i + 1, len(bhus)) if j not in used and np.linalg.norm(xy[i] - xy[j]) < merge_km]
        used.update(g)
        groups.append(g)
    names = [short_name(bhus[g[0]]["name"]) + (f" (+{len(g) - 1} BHU{'s' if len(g) > 2 else ''})" if len(g) > 1 else "")
             for g in groups]
    members = [[short_name(bhus[j]["name"]) for j in g] for g in groups]
    lat = np.array([np.mean([bhus[j]["lat"] for j in g]) for g in groups])
    lon = np.array([np.mean([bhus[j]["lon"] for j in g]) for g in groups])
    return names, lat, lon, members


def make_sanghar(seed: int = 2026, window_h: float = 1.0) -> District:
    """Sanghar district with real facility and settlement locations, modelled demand."""
    osm = load_osm()
    rng = np.random.default_rng(seed)
    names, clat, clon, members = candidate_sites(osm)
    hosp = next(f for f in osm["facilities"] if "سول" in f["name"] or "civil" in f["name"].lower())

    places = osm["places"]
    pop = []
    for p in places:
        if p.get("population") and p["place"] in ("city", "town"):
            pop.append(float(p["population"]))
        elif p["place"] in ("village", "hamlet"):
            pop.append(float(np.clip(rng.lognormal(np.log(POP_DEFAULT[p["place"]]), 0.5), 100, 8000)))
        else:
            pop.append(float(POP_DEFAULT[p["place"]]))
    pop = np.round(np.array(pop))
    n_v = len(places)
    d = District(
        village_xy=to_km([p["lat"] for p in places], [p["lon"] for p in places]),
        village_pop=pop,
        child_share=rng.uniform(0.36, 0.46, n_v),              # Pakistan: ~35-40% under 15
        incidence=rng.uniform(100, 350, n_v) / 1e5,
        seek_delay_h=np.zeros(n_v),                              # window counts travel time only
        speed_kmh=rng.choice([15.0, 25.0, 40.0], n_v, p=[0.3, 0.5, 0.2]),   # cart/qingqi, motorbike, car/ambulance
        clinic_xy=to_km(clat, clon),
        clinic_fridge=rng.random(len(names)) < 0.5,
        hospital_xy=to_km([hosp["lat"]], [hosp["lon"]])[0],
        window_h=window_h,
        road_factor=1.35,
        seed=seed,
    )
    d.clinic_labels = names                                        # real BHU names
    d.clinic_members = members
    d.village_labels = [p["name"] for p in places]
    d.clinic_latlon = np.c_[clat, clon]
    d.village_latlon = np.array([[p["lat"], p["lon"]] for p in places])
    d.hospital_latlon = np.array([hosp["lat"], hosp["lon"]])
    d.hospital_label = "Civil Hospital, Sanghar"
    return d
