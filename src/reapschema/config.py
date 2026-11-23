"""Experiment configuration: YAML files validated by pydantic models."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Triple = tuple[float, float, float]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LoadConfig(_Strict):
    daily_noise_sd: float = Field(ge=0)
    daily_noise_ar1: float = Field(ge=0, lt=1)
    hourly_noise_sd: float = Field(ge=0)
    hvac_coef_log_sd: float = Field(ge=0)
    balance_shift_sd_c: float = Field(ge=0)
    occupancy_change_prob: float = Field(ge=0, le=1)
    occupancy_change_sd: float = Field(ge=0)
    occupancy_change_window_days: int = Field(ge=1)
    occupancy_factor_min: float = Field(gt=0)


class ResConfig(_Strict):
    cost_per_watt_median: float = Field(gt=0)
    cost_per_watt_log_sd: float = Field(ge=0)
    replaced_fraction_range: tuple[float, float]
    tilt_range_deg: tuple[float, float]
    azimuth_mean_deg: float
    azimuth_sd_deg: float
    azimuth_range_deg: tuple[float, float]
    albedo: float = Field(ge=0, le=1)
    sapm_cell: Triple
    dc_ac_ratio: float = Field(gt=0)
    inverter_efficiency: float = Field(gt=0, le=1)
    system_losses: float = Field(ge=0, lt=1)
    temperature_coefficient: float
    derate_log_sd: float = Field(ge=0)
    shading_loss_max: float = Field(ge=0, lt=1)
    irradiance_bias_sd: float = Field(ge=0)
    meter_error_sd: float = Field(ge=0)
    storage_share: float = Field(ge=0, le=1)
    useful_life_years: float = Field(gt=0)
    netting_arrangements: dict[str, float]


class MeasureConfig(_Strict):
    end_uses: list[str]
    reduction: tuple[float, float]


class EeiConfig(_Strict):
    measures: dict[str, MeasureConfig]
    payback_median_years: float = Field(gt=0)
    payback_log_sd: float = Field(ge=0)
    payback_min_years: float = Field(gt=0)
    reported_share_noise_sd: float = Field(ge=0)
    useful_life_years: float = Field(gt=0)
    min_savings_fraction: float = Field(ge=0)


class PopulationConfig(_Strict):
    res_share_source: str
    award_share_of_cost: float = Field(gt=0, le=1)
    historical_award_share_of_cost: float = Field(gt=0, le=1)
    size_fit_fiscal_years: list[int]
    size_distribution: Literal["empirical", "lognormal"]
    max_request_res: float
    max_request_eei: float
    min_request: float
    install_date_range: tuple[str, str]
    facility_types: dict[str, float]
    load: LoadConfig
    res: ResConfig
    eei: EeiConfig

    @model_validator(mode="after")
    def _shares_sum(self) -> PopulationConfig:
        if abs(sum(self.facility_types.values()) - 1.0) > 1e-9:
            raise ValueError("facility_types shares must sum to 1")
        return self


class BillingConfig(_Strict):
    cycle_mean_days: float = Field(gt=0)
    read_jitter_days: int = Field(ge=0)
    estimated_read_prob: float = Field(ge=0, le=1)
    estimate_noise_sd: float = Field(ge=0)
    charge_noise_sd: float = Field(ge=0)
    history_days_before: int = Field(ge=760)
    history_days_after: int = Field(ge=400)
    fixed_charge_usd: float = Field(ge=0)
    transcription_rounding: int = Field(ge=1)


class ErrorConfig(_Strict):
    rates: dict[str, float]
    second_meter_fraction_range: tuple[float, float]
    second_meter_noise_sd: float = Field(ge=0)
    unit_factor: float = Field(gt=1)
    variant_probability: float = Field(ge=0, le=1)
    transposed_targets_res: dict[str, float]
    transposed_targets_eei: dict[str, float]
    straddle_shift_max_bills: int = Field(ge=1)
    correction_success: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _rates(self) -> ErrorConfig:
        if sum(self.rates.values()) > 1.0:
            raise ValueError("error class rates must sum to at most 1")
        return self


class ValidationConfig(_Strict):
    capacity_factor_bounds_rel: tuple[float, float]
    billing_days_total: tuple[int, int]
    billing_days_each: tuple[int, int]
    period_alignment_days: int
    payback_lower_bound_years: float
    claim_recompute_tolerance: float
    enduse_bound_tolerance: float
    statistical_rule_fpr: float = Field(gt=0, lt=1)
    charge_consistency_tolerance: float
    payback_upper_multiple: float
    estimated_share_max: float
    outlier_scale_floor: float = Field(gt=0)
    export_excess_tolerance: float = Field(ge=0)
    export_equal_tolerance: float = Field(ge=0)
    cvrmse_max: float
    ndb_max: float


class MvConfig(_Strict):
    balance_grid_f: tuple[float, float, float]
    daily_heating_grid_f: tuple[float, float, float]
    daily_cooling_grid_f: tuple[float, float, float]
    confidence: float = Field(gt=0, lt=1)
    bootstrap_replicates: int = Field(ge=10)
    bootstrap_block: int = Field(ge=1)
    bootstrap_subsample: int = Field(ge=1)
    default_tilt_deg: float
    default_azimuth_deg: float
    min_nonzero_periods: int = Field(ge=1)
    pvwatts_annual_tolerance: float = Field(gt=0)
    pvwatts_monthly_tolerance: float = Field(gt=0)


class PointsConfig(_Strict):
    employees_prob: float
    critical_service_prob: float
    forest_point_prob: float
    water_point_prob: float
    prior_award_probs: dict[str, float]
    priority_points_values: list[float]
    priority_points_probs: list[float]


class CompetitionConfig(_Strict):
    n_applicants: int = Field(ge=10)
    n_competitions: int = Field(ge=1)
    funding_ratio: float = Field(gt=0)
    funding_ratio_sensitivity: list[float]
    top_per_state: int = Field(ge=0)
    small_request_threshold: float
    small_request_reserve_share: float = Field(ge=0, le=1)
    minimum_score: float
    points: PointsConfig


class BurdenConfig(_Strict):
    anchor_responses: float = Field(gt=0)
    calibrate_to_notice: bool
    rework_minutes: Triple
    elements: dict[str, dict[str, Any]]
    modes: dict[str, dict[str, Any]]
    monte_carlo_draws: int = Field(ge=10)
    sobol_base_samples: int = Field(ge=16)


class NoiseScenario(_Strict):
    noise_multiplier: float = Field(ge=0)
    occupancy_multiplier: float = Field(ge=0)


class ExperimentConfig(_Strict):
    noise_scenarios: dict[str, NoiseScenario]
    are_cap: float = Field(gt=0)
    error_share_thresholds: tuple[float, float]
    savings_bands: tuple[float, float]
    e4_bins: int = Field(ge=2)
    recall_fpr: float = Field(gt=0, lt=1)
    surrogate_sample: int = Field(ge=100)
    ilp_budgets: int = Field(ge=1)
    mip_gap: float = Field(gt=0)
    frontier_budget_points: int = Field(ge=2)
    convergence_points: int = Field(ge=2)
    convergence_min_n: int = Field(ge=1)
    e4_min_per_bin: int
    e5_missing_months: list[int]
    e5_estimated_read_probs: list[float]
    e5_subsample: int
    e3_rate_multipliers: list[float]
    roc_points: int
    bootstrap_replicates: int
    frontier_mc_bands: tuple[float, float]
    availability_grid: list[float]
    recommended_tolerance: float = Field(ge=0, le=1)
    e3_per_class: int = Field(ge=1)
    size_sensitivity_n: int = Field(ge=1)
    evidence_sample: int = Field(ge=1)


class HypothesisTest(_Strict):
    id: str
    description: str
    a: str
    b: str


class HypothesisConfig(_Strict):
    alpha: float = Field(gt=0, lt=1)
    correction: str
    family: list[HypothesisTest]


class Config(_Strict):
    name: str
    seed: int
    n_applicants: int = Field(ge=1)
    n_workers: int = Field(ge=1)
    population: PopulationConfig
    billing: BillingConfig
    errors: ErrorConfig
    validation: ValidationConfig
    mv: MvConfig
    competition: CompetitionConfig
    burden: BurdenConfig
    experiments: ExperimentConfig
    hypothesis_tests: HypothesisConfig


def load_config(path: Path | str) -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    return Config.model_validate(raw)
