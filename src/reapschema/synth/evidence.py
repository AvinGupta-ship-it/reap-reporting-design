"""In-memory representation of an application's performance evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from reapschema.synth.billing import Bills


@dataclass(frozen=True)
class Evidence:
    """Evidence of one application in internal units (kWh, kW, day indices)."""

    applicant_id: str
    state: str
    category: str  # "RES" or "EEI"
    technology: str
    in_service_day: int
    project_cost: float
    amount_requested: float
    energy_price: float
    useful_life_years: float
    pre_bills: Bills
    post_bills: Bills
    claim_value: float
    claim_pre_energy: float
    claim_method: str
    capacity_kw: float = 0.0
    tilt: float = 0.0
    azimuth: float = 180.0
    has_storage: bool = False
    arrangement: str = "none"
    inverter_start: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    inverter_end: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    inverter_kwh: np.ndarray = field(default_factory=lambda: np.zeros(0))
    enduse_share: float = 0.0
    interval_pre_daily: np.ndarray = field(default_factory=lambda: np.zeros(0))
    interval_post_daily: np.ndarray = field(default_factory=lambda: np.zeros(0))
    interval_post_export_daily: np.ndarray = field(default_factory=lambda: np.zeros(0))
    interval_inverter_total: float = 0.0


def to_package(ev: Evidence, first_date: pd.Timestamp, *, latitude: float, longitude: float,
               station_id: str, climate_zone: int, collection_mode: str = "manual_transcription"
               ) -> dict[str, Any]:
    """Serialise evidence as an ``EvidencePackage`` instance of the LinkML schema."""

    def date(day: int) -> str:
        return str((first_date + pd.Timedelta(days=int(day))).date())

    meters: list[dict[str, Any]] = [{
        "id": f"{ev.applicant_id}-utility",
        "meter_type": "utility_revenue_meter",
        "netting_arrangement": ev.arrangement,
        "billed_quantity_basis": ev.post_bills.basis,
        "dedicated": bool(np.all(ev.pre_bills.n_accounts == 1)),
        "utility_account": f"synthetic-{ev.applicant_id}",
    }]
    records: list[dict[str, Any]] = []
    for is_pre, bills in ((True, ev.pre_bills), (False, ev.post_bills)):
        for i in range(len(bills)):
            records.append({
                "meter": meters[0]["id"],
                "is_pre_installation": is_pre,
                "period_start": date(bills.start[i]),
                "period_end": date(bills.end[i]),
                "read_type": "estimated" if bills.estimated[i] else "actual",
                "energy_imported": round(float(bills.printed[i]), 1),
                "energy_exported": round(float(bills.export[i]), 1),
                "energy_unit": "kW.h",
                "peak_demand": round(float(bills.demand[i]), 2),
                "energy_charge": round(float(bills.charge[i]), 2),
            })
    project: dict[str, Any] = {
        "id": f"{ev.applicant_id}-project",
        "category": ev.category,
        "technology": ev.technology,
        "in_service_date": date(ev.in_service_day),
        "project_cost": round(ev.project_cost, 2),
        "amount_requested": round(ev.amount_requested, 2),
        "useful_life_years": ev.useful_life_years,
    }
    if ev.category == "RES":
        project.update({
            "rated_capacity": round(ev.capacity_kw, 3), "rated_capacity_unit": "kW",
            "array_tilt": round(ev.tilt, 1), "array_azimuth": round(ev.azimuth, 1),
        })
        meters.append({"id": f"{ev.applicant_id}-inverter", "meter_type": "inverter"})
        for i in range(ev.inverter_kwh.size):
            records.append({
                "meter": meters[1]["id"], "is_pre_installation": False,
                "period_start": date(ev.inverter_start[i]),
                "period_end": date(ev.inverter_end[i]), "read_type": "actual",
                "energy_imported": round(float(ev.inverter_kwh[i]), 1),
                "energy_unit": "kW.h",
            })
    else:
        project["affected_end_use_share"] = round(min(max(ev.enduse_share, 0.0), 1.0), 4)
    return {
        "id": f"synthetic-{ev.applicant_id}",
        "collection_mode": collection_mode,
        "applicant": {"id": f"{ev.applicant_id}-applicant",
                      "legal_name": f"Synthetic applicant {ev.applicant_id}",
                      "applicant_type": "rural_small_business"},
        "facility": {"id": f"{ev.applicant_id}-facility",
                     "address": f"scenario_hypothetical_site_{ev.state}", "state": ev.state,
                     "latitude": latitude, "longitude": longitude,
                     "climate_zone": climate_zone, "weather_station_id": station_id},
        "project": project,
        "meters": meters,
        "billing_records": records,
        "performance_claim": {
            "quantity": "annual_energy_production" if ev.category == "RES"
            else "annual_energy_savings",
            "claimed_value": round(float(ev.claim_value), 1),
            "energy_unit": "kW.h",
            "method": ev.claim_method,
            "normalization_basis": "none",
            "pre_period_energy": round(float(max(ev.claim_pre_energy, 0.0)), 1),
            "energy_price": round(ev.energy_price, 4),
        },
    }
