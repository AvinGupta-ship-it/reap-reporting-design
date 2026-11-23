"""Idempotent transformations from raw downloads to analysis-ready data.

Outputs under ``data/processed/``:

* ``weather/<ST>.parquet`` - hourly (UTC) irradiance, site temperature, wind and
  station temperature for the radiation years;
* ``weather_load_year/<ST>.parquet`` - site temperature for the load-profile year;
* ``load_profiles.parquet`` and ``load_response.json`` - normalised end-use shapes
  and temperature responses derived from ComStock aggregates;
* ``prices.csv`` - State average commercial electricity price;
* ``reap_awards.csv`` - award amounts by fiscal year, State and project category.
"""

from __future__ import annotations

import gzip
import io
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from reapschema.data.fetch import RAW, Site, load_sites
from reapschema.provenance import REPO_ROOT, sha256_file, write_sidecar

PROCESSED = REPO_ROOT / "data" / "processed"

BASE_END_USES = {
    "interior_lighting": ["out.electricity.interior_lighting.energy_consumption.kwh"],
    "exterior_lighting": ["out.electricity.exterior_lighting.energy_consumption.kwh"],
    "equipment": ["out.electricity.interior_equipment.energy_consumption.kwh"],
    "refrigeration": ["out.electricity.refrigeration.energy_consumption.kwh"],
    "water_heating": ["out.electricity.water_systems.energy_consumption.kwh"],
    "fans_pumps": [
        "out.electricity.fans.energy_consumption.kwh",
        "out.electricity.pumps.energy_consumption.kwh",
        "out.electricity.heat_recovery.energy_consumption.kwh",
    ],
}
COOLING_COLUMNS = [
    "out.electricity.cooling.energy_consumption.kwh",
    "out.electricity.heat_rejection.energy_consumption.kwh",
]
HEATING_COLUMNS = ["out.electricity.heating.energy_consumption.kwh"]
TOTAL_COLUMN = "out.electricity.total.energy_consumption.kwh"
# ComStock aggregate time series are published in Eastern Standard Time.
COMSTOCK_UTC_OFFSET = -5


def read_pvgis(path: Path) -> pd.DataFrame:
    """Parse a PVGIS ``seriescalc`` CSV (horizontal plane, components) into UTC hourly data."""
    lines = path.read_text().splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("time,"))
    end = next(i for i in range(start + 1, len(lines)) if not lines[i][:2].isdigit())
    frame = pd.read_csv(io.StringIO("\n".join(lines[start:end])))
    index = pd.to_datetime(frame["time"], format="%Y%m%d:%H%M", utc=True).dt.floor("h")
    beam_h = frame["Gb(i)"].to_numpy(float)
    dhi = frame["Gd(i)"].to_numpy(float)
    elevation = np.radians(frame["H_sun"].to_numpy(float))
    sin_el = np.sin(elevation)
    dni = np.where(sin_el > np.sin(np.radians(3.0)), beam_h / np.maximum(sin_el, 1e-6), 0.0)
    dni = np.clip(dni, 0.0, 1100.0)
    out = pd.DataFrame(
        {
            "ghi": beam_h + dhi,
            "dhi": dhi,
            "dni": dni,
            "temp_site": frame["T2m"].to_numpy(float),
            "wind": frame["WS10m"].to_numpy(float),
        },
        index=pd.DatetimeIndex(index, name="time_utc"),
    )
    return out[~out.index.duplicated()]


def read_isd_lite(paths: list[Path]) -> pd.Series:
    """Hourly station air temperature (deg C, UTC) from ISD-Lite files; gaps interpolated."""
    parts = []
    for path in paths:
        text = gzip.decompress(path.read_bytes()).decode("ascii", errors="replace")
        frame = pd.read_csv(io.StringIO(text), sep=r"\s+", header=None, usecols=[0, 1, 2, 3, 4],
                            names=["y", "m", "d", "h", "t"])
        idx = pd.to_datetime(
            {"year": frame["y"], "month": frame["m"], "day": frame["d"], "hour": frame["h"]},
            utc=True,
        )
        series = pd.Series(frame["t"].to_numpy(float), index=pd.DatetimeIndex(idx))
        series[series <= -9990] = np.nan
        parts.append(series / 10.0)
    temp = pd.concat(parts).sort_index()
    temp = temp[~temp.index.duplicated()]
    return temp


def _regular_hourly(series: pd.Series, first_year: int, last_year: int) -> pd.Series:
    index = pd.date_range(f"{first_year}-01-01", f"{last_year}-12-31 23:00", freq="h", tz="UTC")
    out = series.reindex(index).interpolate(method="time", limit_direction="both")
    return out


def build_weather(sites: list[Site], years: tuple[int, int], load_year: int) -> None:
    selection = json.loads((RAW / "isd" / "station_selection.json").read_text())
    (PROCESSED / "weather").mkdir(parents=True, exist_ok=True)
    (PROCESSED / "weather_load_year").mkdir(parents=True, exist_ok=True)
    for site in sites:
        out = PROCESSED / "weather" / f"{site.state}.parquet"
        out_ly = PROCESSED / "weather_load_year" / f"{site.state}.parquet"
        src = RAW / "pvgis" / f"{site.state}_nsrdb_{years[0]}_{years[1]}.csv"
        src_ly = RAW / "pvgis" / f"{site.state}_era5_{load_year}.csv"
        if out.exists() and out_ly.exists():
            continue
        station = selection[site.state]["station"]
        frame = read_pvgis(src)
        index = pd.date_range(f"{years[0]}-01-01", f"{years[1]}-12-31 23:00", freq="h", tz="UTC")
        frame = frame.reindex(index).interpolate(limit=3).fillna(0.0)
        isd_paths = [RAW / "isd_lite" / f"{station}-{y}.gz" for y in range(years[0], years[1] + 1)]
        frame["temp_station"] = _regular_hourly(read_isd_lite(isd_paths), *years).to_numpy()
        frame.index.name = "time_utc"
        frame.astype("float32").to_parquet(out)
        ly = read_pvgis(src_ly)[["temp_site"]]
        idx_ly = pd.date_range(f"{load_year}-01-01", f"{load_year}-12-31 23:00", freq="h",
                               tz="UTC")
        ly = ly.reindex(idx_ly).interpolate(limit_direction="both")
        ly.index.name = "time_utc"
        ly.astype("float32").to_parquet(out_ly)
    write_sidecar(PROCESSED / "weather", config={"years": years, "load_year": load_year},
                  seed=None,
                  inputs={"station_selection": sha256_file(RAW / "isd" / "station_selection.json")})


def _fit_response(y: np.ndarray, temp: np.ndarray, group: np.ndarray, cooling: bool,
                  grid: np.ndarray) -> tuple[float, np.ndarray, float]:
    """Fit ``y = a[group] * max(+-(T - Tb), 0)`` by least squares over a balance-point grid."""
    best: tuple[float, np.ndarray, float] | None = None
    sst = float(np.sum((y - y.mean()) ** 2))
    n_groups = int(group.max()) + 1
    for tb in grid:
        x = np.maximum(temp - tb, 0.0) if cooling else np.maximum(tb - temp, 0.0)
        num = np.bincount(group, weights=x * y, minlength=n_groups)
        den = np.bincount(group, weights=x * x, minlength=n_groups)
        coef = np.where(den > 0, num / np.maximum(den, 1e-12), 0.0)
        sse = float(np.sum((y - coef[group] * x) ** 2))
        r2 = 1.0 - sse / sst if sst > 0 else 0.0
        if best is None or r2 > best[2]:
            best = (float(tb), coef, r2)
    assert best is not None
    return best


def comstock_hourly(path: Path, utc_offset: int) -> pd.DataFrame:
    """Hourly end-use electricity in local standard time from a ComStock aggregate file."""
    columns = [c for cols in BASE_END_USES.values() for c in cols]
    columns += COOLING_COLUMNS + HEATING_COLUMNS + [TOTAL_COLUMN]
    frame = pd.read_csv(path, usecols=["timestamp", *columns], parse_dates=["timestamp"])
    # 15-minute records are stamped at the end of the interval
    stamp = frame["timestamp"] - pd.Timedelta(minutes=15)
    stamp = stamp + pd.Timedelta(hours=utc_offset - COMSTOCK_UTC_OFFSET)
    hourly = frame[columns].groupby(stamp.dt.floor("h")).sum()
    out = pd.DataFrame(index=hourly.index)
    for name, cols in BASE_END_USES.items():
        out[name] = hourly[cols].sum(axis=1)
    out["cooling"] = hourly[COOLING_COLUMNS].sum(axis=1)
    out["heating"] = hourly[HEATING_COLUMNS].sum(axis=1)
    out["total"] = hourly[TOTAL_COLUMN]
    return out


def build_load_profiles(sites: list[Site], building_types: list[str], load_year: int) -> None:
    out_profiles = PROCESSED / "load_profiles.parquet"
    out_response = PROCESSED / "load_response.json"
    if out_profiles.exists() and out_response.exists():
        return
    rows: list[pd.DataFrame] = []
    response: dict[str, Any] = {}
    for site in sites:
        temp_utc = pd.read_parquet(PROCESSED / "weather_load_year" / f"{site.state}.parquet")
        temp_local = temp_utc["temp_site"].copy()
        temp_local.index = (temp_local.index + pd.Timedelta(hours=site.utc_offset)).tz_localize(
            None
        )
        for bt in building_types:
            hourly = comstock_hourly(
                RAW / "comstock" / site.state / f"up00-{site.state.lower()}-{bt}.csv",
                site.utc_offset,
            )
            hourly = hourly[hourly.index.year == load_year]
            temp = temp_local.reindex(hourly.index).interpolate(limit_direction="both")
            annual = float(hourly["total"].sum())
            daytype = (hourly.index.dayofweek >= 5).astype(int)
            hour = hourly.index.hour
            group = np.asarray(daytype * 24 + hour)
            for name in BASE_END_USES:
                prof = (hourly[name] / annual).groupby(
                    [hourly.index.month, daytype, hour]
                ).mean()
                prof.index.names = ["month", "daytype", "hour"]
                part = prof.rename("value").reset_index()
                part.insert(0, "end_use", name)
                part.insert(0, "building_type", bt)
                part.insert(0, "state", site.state)
                rows.append(part)
            tc, coef_c, r2_c = _fit_response(
                hourly["cooling"].to_numpy() / annual, temp.to_numpy(), group, True,
                np.arange(6.0, 24.5, 1.0),
            )
            th, coef_h, r2_h = _fit_response(
                hourly["heating"].to_numpy() / annual, temp.to_numpy(), group, False,
                np.arange(4.0, 22.5, 1.0),
            )
            response[f"{site.state}/{bt}"] = {
                "cooling_balance_c": tc, "cooling_coef": coef_c.tolist(), "cooling_r2": r2_c,
                "heating_balance_c": th, "heating_coef": coef_h.tolist(), "heating_r2": r2_h,
                "cooling_share": float(hourly["cooling"].sum() / annual),
                "heating_share": float(hourly["heating"].sum() / annual),
            }
    profiles = pd.concat(rows, ignore_index=True)
    profiles["value"] = profiles["value"].astype("float64")
    profiles.to_parquet(out_profiles, index=False)
    out_response.write_text(json.dumps(response, indent=1, sort_keys=True) + "\n")
    write_sidecar(out_profiles, config={"building_types": building_types,
                                        "load_year": load_year}, seed=None)


def build_prices() -> None:
    src = RAW / "eia" / "avgprice_annual.xlsx"
    raw = pd.read_excel(src, header=1)
    raw = raw[raw["Industry Sector Category"] == "Total Electric Industry"]
    latest = int(raw["Year"].max())
    sel = raw[(raw["Year"] == latest) & (raw["State"].str.len() == 2)]
    out = pd.DataFrame(
        {
            "state": sel["State"].to_numpy(),
            "year": latest,
            "commercial_usd_per_kwh": sel["Commercial"].to_numpy(float) / 100.0,
        }
    ).sort_values("state")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_csv(PROCESSED / "prices.csv", index=False)
    write_sidecar(PROCESSED / "prices.csv", config={"sector": "Commercial", "year": latest},
                  seed=None, inputs={src.name: sha256_file(src)})


def classify_award(description: str | None) -> str | None:
    """Project category of a USAspending award description (None for non-project grants)."""
    text = (description or "").upper()
    if "AUDIT" in text or "TECH" in text or "DEVELOPMENT ASSIST" in text:
        return None
    if "EFFICIENCY" in text or "(EEI)" in text:
        return "EEI"
    if "RENEW" in text or "(RES)" in text:
        return "RES"
    return None


def build_awards() -> None:
    rows = []
    inputs: dict[str, str] = {}
    for path in sorted((RAW / "usaspending").glob("reap_10868_fy*.json")):
        payload = json.loads(path.read_text())
        inputs[path.name] = sha256_file(path)
        for rec in payload["results"]:
            category = classify_award(rec.get("Description"))
            amount = rec.get("Award Amount")
            if category is None or amount is None or amount <= 0:
                continue
            rows.append({"fiscal_year": payload["fiscal_year"],
                         "state": rec.get("Place of Performance State Code"),
                         "category": category, "amount_usd": float(amount)})
    out = pd.DataFrame(rows).sort_values(["fiscal_year", "state", "category", "amount_usd"])
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_csv(PROCESSED / "reap_awards.csv", index=False)
    write_sidecar(PROCESSED / "reap_awards.csv", config={"listing": "10.868"}, seed=None,
                  inputs=inputs)


def build_all() -> None:
    cfg, sites = load_sites()
    years = (int(cfg["radiation_years"][0]), int(cfg["radiation_years"][1]))
    load_year = int(cfg["load_profile_year"])
    build_prices()
    build_awards()
    build_weather(sites, years, load_year)
    build_load_profiles(sites, list(cfg["comstock_building_types"]), load_year)


if __name__ == "__main__":
    build_all()
