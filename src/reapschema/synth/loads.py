"""Baseline electric load of a facility from end-use shapes and temperature response.

Commercial facility types use shapes derived from NREL ComStock State aggregates;
agricultural types use the hypothetical shapes in
``configs/facility_shapes_hypothetical.yaml``. A facility's hourly load is

    L(t) = A * [ sum_e b_e(month, daytype, hour) + sum_r c_r(daytype, hour) * dd_r(T(t)) ]

multiplied by day-to-day and hourly noise, with A set by the annual consumption.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from functools import lru_cache

import numpy as np
import pandas as pd
import yaml

from reapschema.config import LoadConfig
from reapschema.data.process import PROCESSED
from reapschema.provenance import REPO_ROOT
from reapschema.synth.weather import SiteWeather

HYPOTHETICAL_SHAPES = REPO_ROOT / "configs" / "facility_shapes_hypothetical.yaml"


@dataclass(frozen=True)
class Response:
    end_use: str
    kind: str  # "cooling" (load rises above the balance point) or "heating"
    balance_c: float
    coef: np.ndarray  # shape (48,), indexed by daytype * 24 + hour
    months: np.ndarray  # shape (12,), 1.0 where the response is active


@dataclass(frozen=True)
class FacilityModel:
    facility_type: str
    base: dict[str, np.ndarray]  # end use -> array (12, 2, 24)
    responses: tuple[Response, ...]

    def end_uses(self) -> list[str]:
        return [*self.base, *[r.end_use for r in self.responses]]


@lru_cache(maxsize=1)
def _comstock_tables() -> tuple[pd.DataFrame, dict[str, dict[str, object]]]:
    profiles = pd.read_parquet(PROCESSED / "load_profiles.parquet")
    response = json.loads((PROCESSED / "load_response.json").read_text())
    return profiles, response


def _hypothetical_model(name: str) -> FacilityModel:
    spec = yaml.safe_load(HYPOTHETICAL_SHAPES.read_text())[name]
    base: dict[str, np.ndarray] = {}
    for end_use, params in spec["base"].items():
        day = np.full(24, float(params["level"]))
        if "hours" in params:
            lo, hi = params["hours"]
            mask = (np.arange(24) >= lo) & (np.arange(24) < hi)
            day = np.where(mask, day, 0.0)
        for lo, hi in params.get("peak_hours", []):
            mask = (np.arange(24) >= lo) & (np.arange(24) < hi)
            day = np.where(mask, day * float(params["peak_factor"]), day)
        base[end_use] = np.broadcast_to(day, (12, 2, 24)).copy()
    responses = []
    for r in spec["responses"]:
        months = np.zeros(12)
        months[np.asarray(r["months"]) - 1] = 1.0
        responses.append(Response(r["end_use"], r["kind"], float(r["balance_c"]),
                                  np.full(48, float(r["coef"])), months))
    return FacilityModel(name, base, tuple(responses))


@lru_cache(maxsize=512)
def facility_model(state: str, facility_type: str) -> FacilityModel:
    if facility_type.startswith("scenario_hypothetical_"):
        return _hypothetical_model(facility_type)
    profiles, response = _comstock_tables()
    sel = profiles[(profiles["state"] == state) & (profiles["building_type"] == facility_type)]
    if sel.empty:
        raise KeyError(f"no load profile for {state}/{facility_type}")
    base: dict[str, np.ndarray] = {}
    for end_use, grp in sel.groupby("end_use"):
        arr = np.zeros((12, 2, 24))
        arr[grp["month"].to_numpy() - 1, grp["daytype"].to_numpy(),
            grp["hour"].to_numpy()] = grp["value"].to_numpy()
        base[str(end_use)] = arr
    rec = response[f"{state}/{facility_type}"]
    all_months = np.ones(12)
    responses = (
        Response("cooling", "cooling", float(rec["cooling_balance_c"]),  # type: ignore[arg-type]
                 np.asarray(rec["cooling_coef"], dtype=float), all_months),
        Response("heating", "heating", float(rec["heating_balance_c"]),  # type: ignore[arg-type]
                 np.asarray(rec["heating_coef"], dtype=float), all_months),
    )
    return FacilityModel(facility_type, base, responses)


def individualize(model: FacilityModel, rng: np.random.Generator, cfg: LoadConfig
                  ) -> FacilityModel:
    """Draw facility-specific temperature responses around the type-level model."""
    responses = tuple(
        replace(r,
                coef=r.coef * float(rng.lognormal(0.0, cfg.hvac_coef_log_sd)),
                balance_c=r.balance_c + float(rng.normal(0.0, cfg.balance_shift_sd_c)))
        for r in model.responses
    )
    return replace(model, responses=responses)


def end_use_loads(model: FacilityModel, weather: SiteWeather, h0: int, h1: int
                  ) -> dict[str, np.ndarray]:
    """Deterministic hourly end-use loads (relative units) for hours ``h0:h1``."""
    month = weather.month[h0:h1] - 1
    daytype = weather.daytype[h0:h1]
    hour = weather.hour[h0:h1]
    temp = weather.temp_site[h0:h1]
    out: dict[str, np.ndarray] = {}
    for end_use, table in model.base.items():
        out[end_use] = table[month, daytype, hour].astype(float)
    group = daytype * 24 + hour
    for r in model.responses:
        dd = np.maximum(temp - r.balance_c, 0.0) if r.kind == "cooling" else np.maximum(
            r.balance_c - temp, 0.0)
        out[r.end_use] = out.get(r.end_use, 0.0) + r.coef[group] * dd * r.months[month]
    return out


def noise_factors(rng: np.random.Generator, n_hours: int, cfg: LoadConfig) -> np.ndarray:
    """Multiplicative noise: AR(1) lognormal daily factor times lognormal hourly factor."""
    n_days = n_hours // 24 + 1
    eps = rng.normal(0.0, 1.0, n_days)
    z = np.empty(n_days)
    z[0] = eps[0]
    rho = cfg.daily_noise_ar1
    scale = np.sqrt(1.0 - rho * rho)
    for i in range(1, n_days):
        z[i] = rho * z[i - 1] + scale * eps[i]
    daily = np.exp(cfg.daily_noise_sd * z - 0.5 * cfg.daily_noise_sd**2)
    hourly = np.exp(rng.normal(0.0, cfg.hourly_noise_sd, n_hours) - 0.5 * cfg.hourly_noise_sd**2)
    return np.repeat(daily, 24)[:n_hours] * hourly
