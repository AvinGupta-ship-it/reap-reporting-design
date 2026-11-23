"""Site weather: alignment of irradiance, site and station temperature in local time.

Radiation (NSRDB, as distributed by PVGIS 5.2) and site temperature (ERA5) describe
the conditions at the facility; the ISD station temperature is the series a
verifier would use for degree days. All arrays are hourly in local standard time
and trimmed to whole local days.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
import pvlib

from reapschema.data.fetch import RAW, Site, load_sites
from reapschema.data.process import PROCESSED


@dataclass(frozen=True)
class SiteWeather:
    site: Site
    station_id: str
    station_distance_km: float
    index: pd.DatetimeIndex  # naive local standard time, hourly
    ghi: np.ndarray
    dni: np.ndarray
    dhi: np.ndarray
    temp_site: np.ndarray
    temp_station: np.ndarray
    wind: np.ndarray
    zenith: np.ndarray
    azimuth: np.ndarray
    dni_extra: np.ndarray
    month: np.ndarray  # 1-12
    daytype: np.ndarray  # 0 weekday, 1 weekend
    hour: np.ndarray  # 0-23
    daily_temp_site: np.ndarray
    daily_temp_station: np.ndarray

    @property
    def n_days(self) -> int:
        return int(self.daily_temp_site.size)

    @property
    def first_date(self) -> pd.Timestamp:
        return pd.Timestamp(self.index[0]).normalize()

    def day_of(self, date: str | pd.Timestamp) -> int:
        return int((pd.Timestamp(date).normalize() - self.first_date).days)

    def date_of(self, day: int) -> pd.Timestamp:
        return self.first_date + pd.Timedelta(days=int(day))

    def climate_zone(self) -> int:
        """IECC/ASHRAE 169 thermal zone number from long-term degree days (SI criteria)."""
        years = self.n_days / 365.25
        cdd10 = float(np.maximum(self.daily_temp_site - 10.0, 0.0).sum() / years)
        hdd18 = float(np.maximum(18.0 - self.daily_temp_site, 0.0).sum() / years)
        if cdd10 > 5000:
            return 1
        if cdd10 > 3500:
            return 2
        if hdd18 <= 2000 and cdd10 > 2500:
            return 3
        if hdd18 <= 3000:
            return 3 if cdd10 > 2500 else 4
        if hdd18 <= 4000:
            return 5
        if hdd18 <= 5000:
            return 6
        if hdd18 <= 7000:
            return 7
        return 8


def build_site_weather(site: Site) -> SiteWeather:
    frame = pd.read_parquet(PROCESSED / "weather" / f"{site.state}.parquet")
    utc_index = pd.DatetimeIndex(frame.index)
    solpos = pvlib.solarposition.get_solarposition(utc_index, site.latitude, site.longitude)
    dni_extra = pvlib.irradiance.get_extra_radiation(utc_index)
    local = (utc_index + pd.Timedelta(hours=site.utc_offset)).tz_localize(None)
    first_full = local[0].normalize() + (pd.Timedelta(days=1) if local[0].hour != 0
                                         else pd.Timedelta(0))
    last_full = local[-1].normalize() if local[-1].hour != 23 else (
        local[-1].normalize() + pd.Timedelta(days=1))
    keep = np.asarray((local >= first_full) & (local < last_full))
    idx = local[keep]
    selection = json.loads((RAW / "isd" / "station_selection.json").read_text())[site.state]

    def col(name: str) -> np.ndarray:
        return frame[name].to_numpy(dtype=float)[keep]

    temp_site = col("temp_site")
    temp_station = col("temp_station")
    return SiteWeather(
        site=site,
        station_id=str(selection["station"]),
        station_distance_km=float(selection["distance_km"]),
        index=idx,
        ghi=col("ghi"), dni=col("dni"), dhi=col("dhi"),
        temp_site=temp_site, temp_station=temp_station, wind=col("wind"),
        zenith=solpos["apparent_zenith"].to_numpy(dtype=float)[keep],
        azimuth=solpos["azimuth"].to_numpy(dtype=float)[keep],
        dni_extra=np.asarray(dni_extra, dtype=float)[keep],
        month=np.asarray(idx.month), daytype=np.asarray((idx.dayofweek >= 5).astype(int)),
        hour=np.asarray(idx.hour),
        daily_temp_site=temp_site.reshape(-1, 24).mean(axis=1),
        daily_temp_station=temp_station.reshape(-1, 24).mean(axis=1),
    )


@lru_cache(maxsize=64)
def site_weather(state: str) -> SiteWeather:
    _cfg, sites = load_sites()
    by_state = {s.state: s for s in sites}
    return build_site_weather(by_state[state])


def available_states() -> list[str]:
    _cfg, sites = load_sites()
    return [s.state for s in sites if (PROCESSED / "weather" / f"{s.state}.parquet").exists()]
