"""A synthetic rural district: villages, candidate clinics and one district hospital.

Nothing here is real data. Every number is drawn from a range documented in
docs/data_sources.md, so the instance is realistic in scale but not a real place.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class District:
    village_xy: np.ndarray      # (V, 2) km
    village_pop: np.ndarray     # (V,) people
    child_share: np.ndarray     # (V,) share of people under 15
    incidence: np.ndarray       # (V,) envenomings per person per year
    seek_delay_h: np.ndarray    # (V,) hours lost before travel starts (deciding, healer, transport)
    speed_kmh: np.ndarray       # (V,) effective travel speed (foot / bicycle / motorbike)
    clinic_xy: np.ndarray       # (C, 2) km, candidate clinics (one qubit each)
    clinic_fridge: np.ndarray   # (C,) True if the clinic already has a working 2-8 C fridge
    hospital_xy: np.ndarray     # (2,) district hospital, always stocked
    window_h: float = 6.0       # antivenom counts as "within reach" inside this many hours
    road_factor: float = 1.35   # road distance / straight-line distance
    seed: int = 0

    @property
    def n_villages(self) -> int:
        return len(self.village_pop)

    @property
    def n_clinics(self) -> int:
        return len(self.clinic_xy)

    @property
    def clinic_names(self) -> list[str]:
        return [f"C{i + 1}" for i in range(self.n_clinics)]

    def hours_to(self, xy: np.ndarray) -> np.ndarray:
        """Hours from each village to each point in xy (shape (V, P))."""
        pts = np.atleast_2d(xy)
        dist = np.linalg.norm(self.village_xy[:, None, :] - pts[None, :, :], axis=2)
        return self.seek_delay_h[:, None] + dist * self.road_factor / self.speed_kmh[:, None]

    @property
    def clinic_hours(self) -> np.ndarray:
        return self.hours_to(self.clinic_xy)

    @property
    def hospital_hours(self) -> np.ndarray:
        return self.hours_to(self.hospital_xy)[:, 0]

    @property
    def reach(self) -> np.ndarray:
        """reach[v, i] is True if clinic i is inside the time window for village v."""
        return self.clinic_hours <= self.window_h

    @property
    def hospital_covers(self) -> np.ndarray:
        return self.hospital_hours <= self.window_h

    @property
    def envenomings(self) -> np.ndarray:
        """Expected envenomings per year in each village."""
        return self.village_pop * self.incidence

    @property
    def child_envenomings(self) -> np.ndarray:
        return self.envenomings * self.child_share

    def weights(self, lam: float) -> np.ndarray:
        """Value of covering each village: a child's bite counts (1 + lam) times an adult's."""
        return self.envenomings * (1.0 + lam * self.child_share)

    @property
    def cold_cost(self) -> np.ndarray:
        """1 if stocking this clinic needs a new solar fridge, else 0."""
        return (~self.clinic_fridge).astype(float)


def _spread_points(rng, n, size, min_gap, avoid=(), margin=6.0):
    pts = []
    while len(pts) < n:
        p = rng.uniform(margin, size - margin, 2)
        if all(np.linalg.norm(p - q) >= min_gap for q in [*pts, *avoid]):
            pts.append(p)
    return np.array(pts)


def make_district(seed: int = 2026, n_villages: int = 30, n_clinics: int = 9,
                  size_km: float = 90.0, window_h: float = 6.0) -> District:
    """Build a reproducible synthetic district (same seed -> same district)."""
    rng = np.random.default_rng(seed)
    hospital = np.array([size_km * 0.5, size_km * 0.5])
    clinics = _spread_points(rng, n_clinics, size_km, min_gap=17.0, avoid=[hospital])
    villages = rng.uniform(3.0, size_km - 3.0, (n_villages, 2))

    pop = np.clip(rng.lognormal(np.log(1100), 0.55, n_villages), 200, 5000).round()
    child_share = rng.uniform(0.38, 0.52, n_villages)
    # Rural sub-Saharan savanna: ~100-350 envenomings per 100,000 people per year (see docs).
    incidence = rng.uniform(100, 350, n_villages) / 1e5
    seek_delay = rng.uniform(0.5, 2.5, n_villages)
    speed = rng.choice([4.0, 8.0, 15.0], n_villages, p=[0.4, 0.4, 0.2])
    fridge = rng.random(n_clinics) < 0.5

    return District(villages, pop, child_share, incidence, seek_delay, speed,
                    clinics, fridge, hospital, window_h=window_h, seed=seed)
