"""Photovoltaic production with the PVWatts model implemented through pvlib."""

from __future__ import annotations

import numpy as np
import pvlib

from reapschema.synth.weather import SiteWeather


def pvwatts_ac(
    *, ghi: np.ndarray, dni: np.ndarray, dhi: np.ndarray, temp_air: np.ndarray,
    wind: np.ndarray, zenith: np.ndarray, azimuth: np.ndarray, dni_extra: np.ndarray,
    capacity_kw: float, tilt: float, surface_azimuth: float, dc_ac_ratio: float,
    inverter_efficiency: float, system_losses: float, temperature_coefficient: float,
    albedo: float = 0.2,
) -> np.ndarray:
    """Hourly AC energy (kWh) of a fixed-tilt array, PVWatts formulation.

    Plane-of-array irradiance uses the Hay-Davies transposition with a physical
    incidence-angle modifier on the beam component; cell temperature uses the SAPM
    open-rack model; DC power, system losses and the inverter follow PVWatts.
    """
    aoi = pvlib.irradiance.aoi(tilt, surface_azimuth, zenith, azimuth)
    poa = pvlib.irradiance.get_total_irradiance(
        tilt, surface_azimuth, zenith, azimuth, dni, ghi, dhi, dni_extra=dni_extra,
        albedo=albedo, model="haydavies",
    )
    iam = pvlib.iam.physical(aoi)
    effective = np.nan_to_num(
        np.asarray(poa["poa_direct"]) * np.asarray(iam) + np.asarray(poa["poa_diffuse"])
    )
    effective = np.maximum(effective, 0.0)
    t_cell = pvlib.temperature.sapm_cell(effective, temp_air, wind, -3.56, -0.075, 3.0)
    pdc = pvlib.pvsystem.pvwatts_dc(effective, np.asarray(t_cell), capacity_kw,
                                    temperature_coefficient)
    pdc = np.asarray(pdc) * (1.0 - system_losses)
    pac0 = capacity_kw / dc_ac_ratio
    pac = pvlib.inverter.pvwatts(pdc, pac0 / inverter_efficiency, inverter_efficiency)
    return np.maximum(np.nan_to_num(np.asarray(pac, dtype=float)), 0.0)


def simulate_site_pv(weather: SiteWeather, h0: int, h1: int, *, capacity_kw: float,
                     tilt: float, surface_azimuth: float, dc_ac_ratio: float,
                     inverter_efficiency: float, system_losses: float,
                     temperature_coefficient: float) -> np.ndarray:
    s = slice(h0, h1)
    return pvwatts_ac(
        ghi=weather.ghi[s], dni=weather.dni[s], dhi=weather.dhi[s],
        temp_air=weather.temp_site[s], wind=weather.wind[s], zenith=weather.zenith[s],
        azimuth=weather.azimuth[s], dni_extra=weather.dni_extra[s],
        capacity_kw=capacity_kw, tilt=tilt, surface_azimuth=surface_azimuth,
        dc_ac_ratio=dc_ac_ratio, inverter_efficiency=inverter_efficiency,
        system_losses=system_losses, temperature_coefficient=temperature_coefficient,
    )
