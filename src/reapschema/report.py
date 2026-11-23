"""Generation of LaTeX macros and tables from saved results.

Every number quoted in the manuscript, the supporting information and the comment
is written here as a LaTeX macro in ``generated/values.tex``; tables are written
as ``generated/tab_*.tex``. The values file records a hash of the result summaries
it was built from, which a test compares with the current summaries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from reapschema import burden as bm
from reapschema.config import Config, load_config
from reapschema.experiments import NAMED_SPECS
from reapschema.pipeline import SUMMARY_FILES
from reapschema.provenance import REPO_ROOT
from reapschema.schema.build import schema_elements, schema_view
from reapschema.synth.errors import ERROR_CLASSES
from reapschema.validate import OPTIONAL_ELEMENTS, RULES

ELEMENT_LABELS = {
    "billing_dates": "billing-period start and end dates",
    "read_type": "read type (actual or estimated)",
    "bill_charges": "energy charge per bill",
    "meter_ids": "account and meter identifiers",
    "res_post_bills": "post-installation utility bills (RES)",
    "export_channel": "exported energy and netting basis (RES)",
    "inverter_monthly": "monthly production-meter readings (RES)",
    "pv_geometry": "array tilt and azimuth (RES)",
    "inverter_interval": "interval production data (RES)",
    "enduse_share": "affected end-use share (EEI)",
    "claim_method": "declared calculation method",
    "utility_interval": "utility interval data",
    "weather_normalization": "weather normalization by the Agency",
}
SPEC_NAMES = {"current": "Current", "dates": "Dates", "dates_norm": "DatesNorm",
              "dates_norm_read": "DatesNormRead", "production_meter": "ProductionMeter",
              "netting": "Netting", "metadata": "Metadata", "interval": "Interval",
              "recommended": "Rec", "recommended_interval": "RecInterval"}
COND_NAMES = {"error_free": "Clean", "with_errors_validated": "Validated",
              "with_errors_unvalidated": "Unvalidated"}
CLASS_NAMES = {"unit": "Unit", "transposed_digits": "Transposed", "wrong_period": "Period",
               "double_counting": "Double", "gross_net": "GrossNet",
               "nameplate_hours": "Nameplate"}
CLASS_LABELS = {"unit": "Unit", "transposed_digits": "Transposed digits",
                "wrong_period": "Wrong period", "double_counting": "Double counting",
                "gross_net": "Gross/net", "nameplate_hours": "Nameplate $\\times$ hours"}
PATH_NAMES = {"eei_undated": "Undated", "eei_dated": "Dated",
              "eei_normalized_monthly": "NormUnguarded", "eei_normalized_guarded": "Norm",
              "eei_normalized_merged": "NormMerged", "eei_interval": "IntervalPath"}
MODE_NAMES = {"manual_transcription": "Manual", "utility_file_upload": "Upload",
              "green_button_download": "GreenButton", "automated_utility_access": "Automated"}
MODE_LABELS = {"manual_transcription": "Manual transcription",
               "utility_file_upload": "Utility file upload",
               "green_button_download": "Green Button download",
               "automated_utility_access": "Automated utility data access"}
NUMBER_WORDS = {0: "Zero", 1: "One", 2: "Two", 3: "Three"}


def summaries_hash(summary_dir: Path) -> str:
    h = hashlib.sha256()
    for name in SUMMARY_FILES:
        path = summary_dir / name
        if path.exists():
            h.update(name.encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Rows of a table as plain dictionaries."""
    return [{str(k): v for k, v in row.items()} for row in frame.to_dict("records")]


def rows_of(frame: pd.DataFrame) -> list[Any]:
    """Rows of a table as named tuples (typed loosely for formatting code)."""
    return list(frame.itertuples())


def fmt_int(x: Any) -> str:
    return f"{int(round(x)):,}".replace(",", "{,}")


def fmt(x: Any, digits: int = 1) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{x:.{digits}f}"


def pct(x: Any, digits: int = 1) -> str:
    return fmt(100.0 * x, digits)


def tex_escape(text: Any) -> str:
    text = str(text)
    for a, b in (("&", "\\&"), ("%", "\\%"), ("_", "\\_"), ("#", "\\#"), ("$", "\\$")):
        text = text.replace(a, b)
    escaped: str = text.replace("§", "\\S")
    return escaped


class Values:
    def __init__(self) -> None:
        self.items: dict[str, str] = {}

    def add(self, name: str, value: str) -> None:
        if not name.isalpha():
            raise ValueError(f"macro names must be alphabetic: {name}")
        if name in self.items:
            raise ValueError(f"duplicate macro {name}")
        self.items[name] = value

    def write(self, path: Path, header: list[str]) -> None:
        lines = [f"% {h}" for h in header]
        lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(self.items.items())]
        path.write_text("\n".join(lines) + "\n")


def element_list(elements: list[str]) -> str:
    return "; ".join(ELEMENT_LABELS[e] for e in OPTIONAL_ELEMENTS if e in elements)


def build_values(res: Path, cfg: Config) -> Values:
    v = Values()

    def rd(name: str) -> pd.DataFrame:
        return pd.read_csv(res / name)

    def rj(name: str) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads((res / name).read_text())
        return loaded

    # --- E1 ---------------------------------------------------------------------------
    a = rj("e1_burden_audit.json")
    v.add("AuditRespondents", fmt_int(a["respondents"]))
    v.add("AuditResponsesPerRespondent", fmt(a["responses_per_respondent"], 2))
    v.add("AuditResponses", fmt_int(a["responses"]))
    v.add("AuditHoursPerResponse", fmt(a["hours_per_response"], 2))
    v.add("AuditTotalHours", fmt_int(a["total_hours"]))
    v.add("AuditProductResponses", fmt_int(a["product_responses"]))
    v.add("AuditResponsesDiscrepancy", fmt_int(a["responses_discrepancy"]))
    v.add("AuditProductHours", fmt_int(a["product_hours"]))
    v.add("AuditHoursDiscrepancy", fmt_int(a["hours_discrepancy"]))
    v.add("AuditHoursDiscrepancyPct", fmt(a["hours_discrepancy_percent"], 2))
    v.add("AuditImpliedResponsesPerRespondent", fmt(a["implied_responses_per_respondent"], 4))
    v.add("AuditImpliedHoursPerResponse", fmt(a["implied_hours_per_response"], 4))
    v.add("AuditRoundedResponsesPerRespondent",
          fmt(a["rounded_implied_responses_per_respondent"], 2))
    v.add("AuditRoundedHoursPerResponse", fmt(a["rounded_implied_hours_per_response"], 2))
    v.add("AuditHoursPerRespondent", fmt(a["hours_per_respondent"], 1))
    v.add("AuditChainedHours", fmt_int(a["chained_product_hours"]))
    v.add("AuditChainedShortfall", fmt_int(a["total_hours"] - a["chained_product_hours"]))
    v.add("InvResponses", fmt_int(a["inventory_responses"]))
    v.add("InvHours", fmt_int(a["inventory_hours"]))
    v.add("InvRespondents", fmt_int(a["inventory_respondents"]))
    v.add("InvHoursPerResponse", fmt(a["inventory_hours_per_response"], 2))
    v.add("InvResponsesPerRespondent", fmt(a["inventory_responses_per_respondent"], 1))
    v.add("InvHoursPerRespondent", fmt(a["inventory_hours_per_respondent"], 1))
    v.add("ChangeResponsesPct", fmt(a["change_responses_percent"], 0))
    v.add("ChangeHoursPct", fmt(-a["change_hours_percent"], 0))
    v.add("ChangeRespondentsPct", fmt(-a["change_respondents_percent"], 0))
    v.add("ChangeHoursPerResponsePct", fmt(100 * (1 - a["implied_hours_per_response"]
                                                  / a["inventory_hours_per_response"]), 0))
    v.add("ChangeResponsesPerRespondentFactor",
          fmt(a["implied_responses_per_respondent"]
              / a["inventory_responses_per_respondent"], 1))

    oig = bm.load_transcribed("oig_34001-0001-21.yaml")["entry_a"]
    v.add("OigInaccurate", fmt_int(oig["projects_inaccurate"]))
    v.add("OigWithReports", fmt_int(oig["projects_with_reports"]))
    v.add("OigPct", fmt_int(oig["percent_inaccurate"]))
    v.add("OigCiLow", fmt_int(oig["ci_low_percent"]))
    v.add("OigCiHigh", fmt_int(oig["ci_high_percent"]))
    v.add("OigSampleInaccurate", fmt_int(oig["sample_projects_inaccurate"]))
    v.add("OigNoReports", fmt_int(oig["recipients_without_reports"]))
    v.add("OigRequired", fmt_int(oig["recipients_required"]))
    v.add("OigNoReportsPct", fmt_int(oig["percent_without_reports"]))
    scoring = bm.load_transcribed("scoring_4280_140.yaml")["numeric"]
    eei_bands = [b for b in scoring["percent_saved_eei"]["lower_bounds"] if b > 0]
    v.add("EeiBandEdges", ", ".join(f"{b:g}\\%" for b in eei_bands[:-1])
          + f" and {eei_bands[-1]:g}\\%")
    v.add("ScoreEnergyCap", fmt_int(scoring["energy_per_dollar"]["cap"]))
    v.add("ScoreMinimum", fmt_int(scoring["minimum_score"]))
    v.add("SmallRequest", fmt_int(cfg.competition.small_request_threshold))
    ria = bm.load_transcribed("ria_RBS-26-BUSINESS-0529-0004.yaml")["entry_a"]
    v.add("RiaApplications", fmt_int(ria["res_eei_applications_per_year"]))
    v.add("RiaEaReda", fmt_int(ria["ea_reda_applications_per_year"]))
    v.add("RiaTotal", fmt_int(ria["res_eei_applications_per_year"]
                              + ria["ea_reda_applications_per_year"]))
    inv = bm.load_transcribed("omb_inventory_0570-0067.yaml")["entry_a"]
    v.add("InvIcr", str(inv["icr_reference"]))

    # --- population and schema ------------------------------------------------------------
    p = rj("population.json")
    rec = pd.read_parquet(res / "records.parquet", columns=["category", "error_class"])
    v.add("NApplicants", fmt_int(p["n"]))
    v.add("NRes", fmt_int((rec["category"] == "RES").sum()))
    v.add("NEei", fmt_int((rec["category"] == "EEI").sum()))
    v.add("ResShareAwards", pct(p["res_share_awards"], 0))
    v.add("NStates", fmt_int(p["n_states"]))
    v.add("MedianRequest", fmt_int(p["median_request"]))
    v.add("MedianCapacity", fmt(p["median_capacity_kw"], 0))
    v.add("MedianSavingsFraction", pct(p["median_savings_fraction"], 0))
    v.add("MedianReplacedFraction", pct(p["median_replaced_fraction"], 0))
    v.add("MedianStationDistance", fmt(p["median_station_distance_km"], 0))
    v.add("ErrorShare", pct(p["error_share"], 0))
    for cat in ("RES", "EEI"):
        v.add(f"AwardFitAD{cat.title()}", fmt(p["award_fit"][cat]["anderson_darling"], 1))
        v.add(f"AwardFitN{cat.title()}", fmt_int(p["award_fit"][cat]["n"]))
    awards = pd.read_csv(REPO_ROOT / "data" / "processed" / "reap_awards.csv")
    fit_awards = awards[awards["fiscal_year"].isin(cfg.population.size_fit_fiscal_years)]
    v.add("AwardShareAtSmallCap", pct(
        (fit_awards["amount_usd"] == cfg.competition.small_request_threshold).mean(), 0))
    v.add("AwardFitADCritical", fmt(p["award_fit"]["RES"]["ad_critical_5pct"], 2))
    trace = rd("traceability.csv")
    v.add("TraceTotal", fmt_int(len(trace)))
    v.add("TraceEvidence", fmt_int((trace["scope"] == "evidence").sum()))
    v.add("TraceOutOfScope", fmt_int((trace["scope"] == "out_of_scope").sum()))
    elements = schema_elements()
    slots = {e for e in elements if "." in e and not e.startswith("EvidencePackage.")}
    used = {x for cell in trace["schema_elements"].dropna() for x in cell.split("; ") if x}
    v.add("SchemaClasses", fmt_int(len([e for e in elements if "." not in e])))
    v.add("SchemaSlots", fmt_int(len(slots)))
    v.add("SchemaSlotsTraced", fmt_int(len(slots & used)))
    v.add("SchemaSlotsBeyondRule", fmt_int(len(slots - used)))
    v.add("NRules", fmt_int(len(RULES)))
    v.add("NOptionalElements", fmt_int(len(OPTIONAL_ELEMENTS)))

    # --- E2 ---------------------------------------------------------------------------
    acc = rd("e2_accuracy.csv")
    for r in records(acc):
        if r["condition"] in COND_NAMES:
            base = f"Acc{SPEC_NAMES[r['spec']]}{COND_NAMES[r['condition']]}{r['category'].title()}"
            digits = 2 if r["category"] == "RES" else 1
            v.add(base + "Median", pct(r["median"], digits))
            v.add(base + "QLow", pct(r["q05"], digits))
            v.add(base + "QHigh", pct(r["q95"], digits))
            v.add(base + "Mare", pct(r["mare_capped"], 1))
            v.add(base + "ShareTen", pct(r["share_above_10pct"], 1))
        elif r["condition"].startswith("path_vs_"):
            basis = "Normal" if r["condition"].endswith("normal_year") else "Post"
            base = f"Path{PATH_NAMES[r['spec']]}{basis}"
            v.add(base + "Median", pct(r["median"], 1))
            v.add(base + "QLow", pct(r["q05"], 1))
            v.add(base + "QHigh", pct(r["q95"], 1))
            v.add(base + "ShareTen", pct(r["share_above_10pct"], 0))
            v.add(base + "MedianSE", pct(r["median_se"], 1))
        else:
            base = "PathCpre" + ("Dated" if r["spec"] == "cpre_dated" else "Undated")
            v.add(base + "Median", pct(r["median"], 2))
            v.add(base + "QHigh", pct(r["q95"], 1))
    pth = acc[acc["condition"] == "path_vs_normal_year"].set_index("spec")["median"]
    v.add("GapClosedPct", pct((pth["eei_undated"] - pth["eei_normalized_merged"])
                              / (pth["eei_undated"] - pth["eei_interval"]), 0))
    bands = rd("e2_by_savings_fraction.csv")
    band_names = {"below 10%": "Low", "10-20%": "Mid", "above 20%": "High"}
    for r in records(bands):
        if r["estimator"] in ("eei_undated", "eei_normalized_guarded", "eei_interval"):
            v.add(f"Band{band_names[r['savings_fraction']]}{PATH_NAMES[r['estimator']]}Median",
                  pct(r["median_are"], 0))
    for label, name in band_names.items():
        v.add(f"Band{name}N", fmt_int(bands[bands["savings_fraction"] == label]["n"].iloc[0]))
    tests = rd("e2_hypothesis_tests.csv")
    for r in records(tests):
        tag = {"H1": "One", "H2": "Two", "H3": "Three", "H4": "Four"}[r["id"]]
        pv = r["p_holm"]
        v.add(f"Test{tag}P", "<0.001" if pv < 0.001 else fmt(pv, 3))
        v.add(f"Test{tag}Diff", pct(r["median_difference"], 2))
    v.add("TestsRejected", fmt_int(tests["reject"].sum()))
    v.add("TestsTotal", fmt_int(len(tests)))

    # --- E3 ---------------------------------------------------------------------------
    ens = rd("e3_ensemble.csv")
    ens1 = ens[ens["rate_multiplier"] == 1.0]
    for r in records(ens1):
        base = f"Det{SPEC_NAMES[r['spec']]}{r['category'].title()}"
        for cls, cname in CLASS_NAMES.items():
            if not pd.isna(r[cls]):
                v.add(base + cname, pct(r[cls], 0))
        v.add(base + "FalsePositive", pct(r["false_positive_rate"], 1))
        v.add(base + "Recall", pct(r["recall"], 0))
        v.add(base + "Ppv", pct(r["ppv"], 0))
    for mult, tag in ((0.5, "Half"), (2.0, "Double")):
        sel = ens[(ens["rate_multiplier"] == mult) & (ens["spec"] == "metadata")]
        for r in records(sel):
            v.add(f"PpvMetadata{r['category'].title()}{tag}", pct(r["ppv"], 0))
    roc = pd.read_parquet(res / "e3_roc.parquet")
    auc = roc.groupby(["rule", "category", "error_class"])[["auc", "recall_at_5pct_fpr"]].first()
    for (rule, cat, cls), tag in {
        ("plausibility_z", "RES", "nameplate_hours"): "AucPlausNameplate",
        ("plausibility_z_geometry", "RES", "nameplate_hours"): "AucPlausGeomNameplate",
        ("plausibility_z", "RES", "gross_net"): "AucPlausGrossNet",
        ("bill_difference", "RES", "gross_net"): "AucBillDiffGrossNet",
        ("bill_difference_unlabelled", "RES", "gross_net"): "AucBillDiffUnlabGrossNet",
        ("bill_outlier_dated", "EEI", "transposed_digits"): "AucOutlierTransposed",
        ("monthly_shape", "RES", "transposed_digits"): "AucShapeTransposed",
    }.items():
        v.add(tag, fmt(auc.loc[(rule, cat, cls), "auc"], 2))
        v.add(tag.replace("Auc", "Recall"), pct(auc.loc[(rule, cat, cls),
                                                        "recall_at_5pct_fpr"], 0))
    matrix = rd("e3_rule_matrix.csv")
    by_rule = matrix[matrix["category"] == "RES"].set_index("rule")
    v.add("DetRulePlausNameplate", pct(by_rule.loc["plausibility_z", "nameplate_hours"], 0))
    v.add("DetRulePlausGeomNameplate",
          pct(by_rule.loc["plausibility_z_geometry", "nameplate_hours"], 0))
    v.add("DetRulePlausGrossNet", pct(by_rule.loc["plausibility_z", "gross_net"], 0))
    fit = matrix[matrix["rule"] == "model_fit"].iloc[0]
    v.add("ModelFitFailShare", pct(fit["false_positive_rate"], 0))
    v.add("StatRuleFpr", pct(cfg.validation.statistical_rule_fpr, 0))
    v.add("NPerClass", fmt_int(cfg.experiments.e3_per_class))

    # --- E4 ---------------------------------------------------------------------------
    e4 = rd("e4_summary.csv").set_index(["category", "estimator"])
    for (cat, est), tag in {
        ("EEI", "unnormalized"): "NormEeiRaw", ("EEI", "normalized_annual"): "NormEeiNorm",
        ("EEI", "normalized_unguarded"): "NormEeiUnguarded",
        ("EEI", "interval_normalized"): "NormEeiInterval",
        ("EEI", "normalized_avoided"): "NormEeiAvoided",
        ("RES", "unnormalized"): "NormResRaw", ("RES", "normalized_annual"): "NormResNorm",
    }.items():
        e4_row: Any = e4.loc[(cat, est)]
        v.add(tag + "Rmse", pct(e4_row["rmse"], 1))
        v.add(tag + "Bias", pct(e4_row["bias"], 2))
        v.add(tag + "Slope", fmt(100 * e4_row["slope_per_degC"] if cat == "EEI"
                                 else e4_row["slope_per_degC"], 2))
        v.add(tag + "SlopeP", "<0.001" if e4_row["slope_p"] < 0.001 else fmt(e4_row["slope_p"], 3))

    # --- E5 ---------------------------------------------------------------------------
    e5 = rd("e5_incomplete.csv")
    p0 = cfg.experiments.e5_estimated_read_probs[0]
    for m in cfg.experiments.e5_missing_months:
        sel = e5[(e5["missing_months"] == m) & (e5["estimated_read_prob"] == p0)].set_index(
            "estimator")
        w = NUMBER_WORDS[m]
        v.add(f"Missing{w}CpreUndated", pct(sel.loc["cpre_undated", "median_are"], 1))
        v.add(f"Missing{w}CpreDated", pct(sel.loc["cpre_dated", "median_are"], 1))
        v.add(f"Missing{w}SavUndated", pct(sel.loc["s_undated", "median_are"], 0))
        v.add(f"Missing{w}SavNorm", pct(sel.loc["s_norm", "median_are"], 0))
    for prob, tag in zip(cfg.experiments.e5_estimated_read_probs, ("A", "B", "C", "D"),
                         strict=False):
        sel = e5[(e5["missing_months"] == 0) & (e5["estimated_read_prob"] == prob)].set_index(
            "estimator")
        v.add(f"Est{tag}Prob", pct(prob, 0))
        v.add(f"Est{tag}SavNorm", pct(sel.loc["s_norm", "median_are"], 0))
        v.add(f"Est{tag}SavMerged", pct(sel.loc["s_norm_merged", "median_are"], 0))
        v.add(f"Est{tag}SavUndated", pct(sel.loc["s_undated", "median_are"], 0))
    v.add("EFiveN", fmt_int(cfg.experiments.e5_subsample))

    # --- E6 ---------------------------------------------------------------------------
    r6 = rj("recommended.json")
    specs = pd.read_parquet(res / "e6_specs.parquet")
    manual = specs[specs["mode"] == "manual_transcription"]
    cal = rd("e6_calibration.csv").iloc[0]
    v.add("NSpecs", fmt_int(len(manual)))
    v.add("Kappa", fmt(cal["kappa"], 2))
    v.add("AnchorMinutes", fmt(cal["base_burden_min"], 0))
    v.add("AnchorResponses", fmt(cfg.burden.anchor_responses, 0))
    v.add("BaseBurden", fmt(r6["baseline_burden_min"], 0))
    v.add("BaseMare", pct(r6["baseline_mare"], 1))
    v.add("BaseSel", pct(r6["baseline_selection_change"], 1))
    v.add("BaseFlagRate", pct(r6["baseline_flag_rate"], 0))
    v.add("RecBurden", fmt(r6["burden_min"], 0))
    v.add("RecMare", pct(r6["mare"], 1))
    v.add("RecSel", pct(r6["selection_change"], 1))
    v.add("RecFlagRate", pct(r6["flag_rate"], 0))
    v.add("RecElements", element_list(r6["elements"]))
    v.add("RecNElements", fmt_int(len(r6["elements"])))
    v.add("RecBurdenIncrease", fmt(r6["burden_min"] - r6["baseline_burden_min"], 0))
    v.add("RecBurdenIncreasePct", pct(r6["burden_min"] / r6["baseline_burden_min"] - 1, 0))
    v.add("RecMareReductionPct", pct(1 - r6["mare"] / r6["baseline_mare"], 0))
    v.add("RecSelReductionPct", pct(1 - r6["selection_change"]
                                    / r6["baseline_selection_change"], 0))
    v.add("RecIntervalBurden", fmt(r6["interval_burden_min"], 0))
    v.add("RecIntervalMare", pct(r6["interval_mare"], 1))
    v.add("RecIntervalSel", pct(r6["interval_selection_change"], 1))
    v.add("RecIntervalElements", element_list(r6["interval_elements"]))
    v.add("RecIntervalBurdenIncreasePct",
          pct(r6["interval_burden_min"] / r6["baseline_burden_min"] - 1, 0))
    v.add("RecTolerance", pct(r6["tolerance"], 0))
    for e in OPTIONAL_ELEMENTS:
        v.add("Tau" + "".join(w.title() for w in e.split("_")), fmt(cal[f"tau_{e}"], 1))
    dn = manual[(manual["billing_dates"] == 1) & (manual["weather_normalization"] == 1)
                & (manual["n_elements"] == 2)].iloc[0]
    v.add("DatesNormBurden", fmt(dn["burden_min"], 0))
    v.add("DatesNormBurdenIncrease", fmt(dn["burden_min"] - r6["baseline_burden_min"], 0))
    v.add("DatesNormMare", pct(dn["mare"], 1))
    v.add("DatesNormMareReductionPct", pct(1 - dn["mare"] / r6["baseline_mare"], 0))
    v.add("FrontierPoints", fmt_int(manual["on_frontier_mare"].sum()))
    ilp = rd("e6_ilp.csv")
    v.add("IlpMaxRegret", pct(ilp["regret"].max(), 2))
    v.add("IlpAllOptimal", "all" if (ilp["condition"] == "optimal").all() else "not all")
    v.add("IlpNBudgets", fmt_int(len(ilp)))
    v.add("SurrogateRsq", fmt(ilp["surrogate_r2"].iloc[0], 3))
    v.add("IlpGap", pct(ilp["mip_gap_tolerance"].iloc[0], 2))
    conv = rd("convergence.csv")
    last = conv.sort_values("n").groupby("spec").tail(1).set_index("spec")
    v.add("ConvRelSeCurrent", pct(last.loc["current", "relative_se"], 1))
    v.add("ConvRelSeRec", pct(last.loc["recommended", "relative_se"], 1))
    v.add("BaseMareSe", pct(last.loc["current", "se"], 2))
    v.add("RecMareSe", pct(last.loc["recommended", "se"], 2))

    # --- E7 ---------------------------------------------------------------------------
    e7 = rd("e7_selection.csv")
    ratios = sorted(e7["funding_ratio"].unique())
    tags = dict(zip(ratios, ("Low", "Mid", "High"), strict=False))
    for r in records(e7):
        if r["spec"] not in SPEC_NAMES:
            continue
        v.add(f"Sel{SPEC_NAMES[r['spec']]}{COND_NAMES[r['condition']]}{tags[r['funding_ratio']]}",
              pct(r["selection_change"], 1))
    for ratio, tag in tags.items():
        v.add(f"FundRatio{tag}", pct(ratio, 0))
        v.add(f"MeanSelected{tag}", fmt_int(e7[e7["funding_ratio"] == ratio][
            "mean_selected"].iloc[0]))
    v.add("SelMaxSe", pct(e7["se"].max(), 2))
    v.add("NCompetitions", fmt_int(cfg.competition.n_competitions))
    v.add("NCompetitionApplicants", fmt_int(cfg.competition.n_applicants))
    sc = rj("score_structure.json")
    v.add("ShareEnergyCap", pct(sc["share_energy_points_at_cap"], 1))
    v.add("ShareEligibleRes", pct(sc["share_eligible_res"], 0))
    v.add("ShareEligibleEei", pct(sc["share_eligible_eei"], 0))
    v.add("DistinctEnergyScores", fmt_int(sc["distinct_energy_scores"]))

    # --- E8 ---------------------------------------------------------------------------
    e8 = rd("e8_modes.csv")
    full = e8[e8["availability"] == 1.0]
    for r in records(full):
        if r["spec"] not in SPEC_NAMES:
            continue
        base = f"Mode{SPEC_NAMES[r['spec']]}{MODE_NAMES[r['mode']]}"
        v.add(base + "Burden", fmt(r["burden"], 0))
        v.add(base + "BurdenLow", fmt(r["burden_lo"], 0))
        v.add(base + "BurdenHigh", fmt(r["burden_hi"], 0))
        v.add(base + "Mare", pct(r["mare"], 1))
    cur = full[(full["spec"] == "current") & (full["mode"] == "manual_transcription")][
        "burden"].iloc[0]
    for spec in ("recommended", "metadata", "recommended_interval"):
        for mode in ("utility_file_upload", "green_button_download",
                     "automated_utility_access"):
            b = full[(full["spec"] == spec) & (full["mode"] == mode)]["burden"].iloc[0]
            v.add(f"Mode{SPEC_NAMES[spec]}{MODE_NAMES[mode]}VsCurrentPct", pct(1 - b / cur, 0))
    half = e8[(e8["availability"] == 0.5) & (e8["spec"] == "recommended")
              & (e8["mode"] == "utility_file_upload")]["burden"].iloc[0]
    v.add("ModeRecUploadHalfBurden", fmt(half, 0))

    # --- sensitivity and intervals -------------------------------------------------------------
    sob = rd("sobol_burden.csv").sort_values("ST", ascending=False)
    v.add("SobolTopName", tex_escape(sob["parameter"].iloc[0]))
    v.add("SobolTopST", fmt(sob["ST"].iloc[0], 2))
    v.add("SobolSecondName", tex_escape(sob["parameter"].iloc[1]))
    v.add("SobolSecondST", fmt(sob["ST"].iloc[1], 2))
    v.add("SobolOutputMean", fmt(sob["output_mean"].iloc[0], 0))
    v.add("SobolOutputSd", fmt(sob["output_sd"].iloc[0], 0))
    v.add("SobolN", fmt_int(cfg.burden.sobol_base_samples))
    cov = rd("interval_coverage.csv").iloc[0]
    v.add("CoverageNominal", pct(cov["nominal"], 0))
    v.add("CoverageFsu", pct(cov["coverage_fsu"], 0))
    v.add("CoverageBootstrap", pct(cov["coverage_bootstrap"], 0))
    v.add("CoverageN", fmt_int(cov["n"]))
    v.add("HalfwidthFsu", pct(cov["median_halfwidth_fsu_rel"], 0))
    v.add("HalfwidthBootstrap", pct(cov["median_halfwidth_bootstrap_rel"], 0))
    sens = rd("sensitivity_size_distribution.csv").set_index(["size_distribution", "spec"])
    for dist, dtag in (("empirical", "Emp"), ("lognormal", "Logn")):
        for spec, stag in (("current", "Current"), ("recommended", "Rec")):
            v.add(f"Size{dtag}{stag}Mare", pct(sens.loc[(dist, spec), "mare"], 1))
        v.add(f"Size{dtag}EeiMedian", pct(sens.loc[(dist, "current"), "median_are_eei"], 1))
    v.add("SizeSensN", fmt_int(cfg.experiments.size_sensitivity_n))

    # --- model verification: PVWatts reference --------------------------------------------------
    pv = pvwatts_comparison()
    v.add("PvRefAnnualDiff", pct(abs(pv["annual"]), 1))
    v.add("PvRefMonthlyMaxDiff", pct(pv["monthly_max"], 1))
    v.add("PvRefCorrelation", fmt(pv["correlation"], 4))

    # --- configuration values quoted in the text -----------------------------------------------
    v.add("CfgSeed", str(cfg.seed))
    v.add("CfgEstimatedProb", pct(cfg.billing.estimated_read_prob, 0))
    v.add("CfgCvrmseMax", pct(cfg.validation.cvrmse_max, 0))
    v.add("CfgConfidence", pct(cfg.mv.confidence, 0))
    v.add("CfgFundingRatio", pct(cfg.competition.funding_ratio, 0))
    v.add("CfgTopPerState", fmt_int(cfg.competition.top_per_state))
    v.add("CfgReserveShare", pct(cfg.competition.small_request_reserve_share, 0))
    v.add("CfgMcDraws", fmt_int(cfg.burden.monte_carlo_draws))
    v.add("CfgBootstrap", fmt_int(cfg.experiments.bootstrap_replicates))
    v.add("CfgOccupancyProb", pct(cfg.population.load.occupancy_change_prob, 0))
    v.add("CfgDailyNoise", pct(cfg.population.load.daily_noise_sd, 0))
    for cls, rate in cfg.errors.rates.items():
        v.add(f"CfgRate{CLASS_NAMES[cls]}", pct(rate, 0))
    return v


def pvwatts_comparison() -> dict[str, float]:
    """Difference between the pvlib implementation and the stored PVWatts v8 run."""
    import pvlib

    from reapschema.data.fetch import RAW
    from reapschema.synth.pv import pvwatts_ac

    data = json.loads((RAW / "pvwatts" / "pvwatts_v8_reference.json").read_text())
    out, inp, info = data["outputs"], data["inputs"], data["station_info"]
    index = pd.date_range("2019-01-01 00:30", periods=8760, freq="h",
                          tz=f"Etc/GMT{-int(info['tz']):+d}")
    solpos = pvlib.solarposition.get_solarposition(index, float(inp["lat"]), float(inp["lon"]))
    zen = solpos["apparent_zenith"].to_numpy()
    dn, df = np.asarray(out["dn"], float), np.asarray(out["df"], float)
    ours = pvwatts_ac(
        ghi=dn * np.maximum(np.cos(np.radians(zen)), 0) + df, dni=dn, dhi=df,
        temp_air=np.asarray(out["tamb"], float), wind=np.asarray(out["wspd"], float),
        zenith=zen, azimuth=solpos["azimuth"].to_numpy(),
        dni_extra=pvlib.irradiance.get_extra_radiation(index).to_numpy(),
        capacity_kw=float(inp["system_capacity"]), tilt=float(inp["tilt"]),
        surface_azimuth=float(inp["azimuth"]), dc_ac_ratio=1.2, inverter_efficiency=0.96,
        system_losses=float(inp["losses"]) / 100.0, temperature_coefficient=-0.0037)
    ref = np.asarray(out["ac"], float) / 1000.0
    monthly = pd.Series(ours, index=index).groupby(index.month).sum().to_numpy()
    ref_m = pd.Series(ref, index=index).groupby(index.month).sum().to_numpy()
    return {"annual": float(ours.sum() / ref.sum() - 1.0),
            "monthly_max": float(np.max(np.abs(monthly / ref_m - 1.0))),
            "correlation": float(np.corrcoef(ours, ref)[0, 1])}


# --- tables -----------------------------------------------------------------------------------


def _tabular(header: list[str], rows: list[list[str]], align: str, longtable: bool = False,
             caption: str | None = None, label: str | None = None) -> str:
    env = "longtable" if longtable else "tabular"
    lines = [f"\\begin{{{env}}}{{{align}}}"]
    if longtable and caption:
        lines.append(f"\\caption{{{caption}}}\\label{{{label}}}\\\\")
    lines += ["\\hline", " & ".join(header) + " \\\\", "\\hline"]
    if longtable:
        lines += ["\\endfirsthead", "\\hline", " & ".join(header) + " \\\\", "\\hline",
                  "\\endhead"]
    lines += [" & ".join(r) + " \\\\" for r in rows]
    lines += ["\\hline", f"\\end{{{env}}}"]
    return "\n".join(lines) + "\n"


def build_tables(res: Path, out: Path, cfg: Config) -> None:
    def rd(name: str) -> pd.DataFrame:
        return pd.read_csv(res / name)

    # burden audit
    a = json.loads((res / "e1_burden_audit.json").read_text())
    rows = [
        ["Respondents", fmt_int(a["respondents"]), "published"],
        ["Responses per respondent", fmt(a["responses_per_respondent"], 2), "published"],
        ["Responses", fmt_int(a["responses"]), "published"],
        ["Hours per response", fmt(a["hours_per_response"], 2), "published"],
        ["Total annual hours", fmt_int(a["total_hours"]), "published"],
        ["Respondents $\\times$ responses per respondent", fmt_int(a["product_responses"]),
         f"{fmt_int(a['responses_discrepancy'])} below published responses"],
        ["Responses $\\times$ hours per response", fmt_int(a["product_hours"]),
         f"{fmt_int(a['hours_discrepancy'])} hours below published total"],
        ["Responses $\\div$ respondents", fmt(a["implied_responses_per_respondent"], 4),
         f"rounds to {fmt(a['rounded_implied_responses_per_respondent'], 2)}; "
         f"truncates to {fmt(a['truncated_implied_responses_per_respondent'], 2)}"],
        ["Total hours $\\div$ responses", fmt(a["implied_hours_per_response"], 4),
         f"rounds to {fmt(a['rounded_implied_hours_per_response'], 2)}; "
         f"truncates to {fmt(a['truncated_implied_hours_per_response'], 2)}"],
        ["Total hours $\\div$ respondents", fmt(a["hours_per_respondent"], 1), "derived"],
        ["Current inventory: responses", fmt_int(a["inventory_responses"]),
         "ICR 202602-0570-001"],
        ["Current inventory: hours", fmt_int(a["inventory_hours"]), "ICR 202602-0570-001"],
        ["Current inventory: hours per response", fmt(a["inventory_hours_per_response"], 2),
         "derived"],
    ]
    (out / "tab_burden_audit.tex").write_text(
        _tabular(["Quantity", "Value", "Basis"], rows, "p{0.42\\linewidth}rp{0.36\\linewidth}"))

    # traceability summary
    trace = rd("traceability.csv").fillna("")
    trace["section"] = trace["requirement_id"].str.extract(r"^(\d{4}\.\d+)")[0]
    rows = []
    titles = {"4280.104": "Definitions", "4280.122": "Project eligibility",
              "4280.131": "Application requirements", "4280.160": "Reporting requirements"}
    for section, grp in trace.groupby("section"):
        ev = grp[grp["scope"] == "evidence"]
        used = sorted({x.split(".")[0] for cell in ev["schema_elements"] for x in
                       cell.split("; ") if x})
        rows.append([f"\\S{section}", titles[str(section)], str(len(grp)), str(len(ev)),
                     ", ".join(used)])
    (out / "tab_traceability.tex").write_text(_tabular(
        ["Section", "Subject", "Paragraphs", "Mapped", "Schema classes used"], rows,
        "llrrp{0.42\\linewidth}"))
    rows = [[tex_escape(r.requirement_id), tex_escape(r.heading[:38]),
             "evidence" if r.scope == "evidence" else "out of scope",
             tex_escape(r.schema_elements.replace("; ", ", "))]
            for r in rows_of(trace)]
    (out / "tab_traceability_full.tex").write_text(_tabular(
        ["Requirement", "Heading", "Scope", "Schema elements"], rows,
        "p{0.2\\linewidth}p{0.2\\linewidth}p{0.09\\linewidth}p{0.42\\linewidth}",
        longtable=True, caption="Requirement-to-schema traceability for 7 CFR part 4280 "
        "subpart B (91 FR 62600). A mapping to a paragraph covers its sub-paragraphs unless "
        "they are mapped separately.", label="tab:trace-full"))

    # validation rules with detection rates
    matrix = rd("e3_rule_matrix.csv")
    rows = []
    for rule in RULES:
        sel = matrix[matrix["rule"] == rule.key]
        cells = []
        for cls in ERROR_CLASSES:
            vals = sel[cls].dropna()
            cells.append(fmt(100 * vals.mean(), 0) if len(vals) else "--")
        fp = sel["false_positive_rate"].mean()
        rows.append([tex_escape(rule.description),
                     tex_escape(", ".join(sorted(rule.requires)).replace("_", " ")) or "none",
                     rule.applies_to if rule.applies_to != "both" else "all",
                     rule.kind[:4] + ".", fmt(100 * fp, 1), *cells])
    header = ["Rule", "Elements required", "Applies", "Type", "FP"] + [
        {"unit": "U", "transposed_digits": "T", "wrong_period": "P", "double_counting": "D",
         "gross_net": "G", "nameplate_hours": "N"}[c] for c in ERROR_CLASSES]
    (out / "tab_rules.tex").write_text(_tabular(
        header, rows, "p{0.33\\linewidth}p{0.17\\linewidth}llrrrrrrr"))

    # frontier specifications
    front = rd("e6_frontier.csv")
    sel = front[(front["mode"] == "manual_transcription")
                & (front["on_frontier_mare"] | (front["n_elements"] == 0))].sort_values(
        "burden_min")
    rows = []
    for r in records(sel):
        els = [e.replace("_", " ") for e in OPTIONAL_ELEMENTS if r[e] == 1]
        rows.append([", ".join(els) or "(current rule)", fmt(r["burden_min"], 0),
                     pct(r["mare"], 1), pct(r["mare_res"], 1), pct(r["mare_eei"], 1),
                     pct(r["selection_change"], 1), pct(r["detection_rate"], 0),
                     pct(r["false_positive_rate"], 1)])
    (out / "tab_frontier.tex").write_text(_tabular(
        ["Optional elements collected", "Min.", "MARE", "RES", "EEI", "Sel.", "Det.", "FP"],
        rows, "p{0.44\\linewidth}rrrrrrr"))

    # supporting-information tables
    e5 = rd("e5_incomplete.csv")
    rows = [[pct(r.estimated_read_prob, 0), str(r.missing_months),
             tex_escape(r.estimator), str(r.n), pct(r.median_are, 1), pct(r.q95_are, 0),
             pct(r.date_rules_flag_rate, 0)] for r in rows_of(e5)]
    (out / "tab_e5.tex").write_text(_tabular(
        ["Estimated reads (\\%)", "Missing months", "Estimator", "$n$", "Median ARE (\\%)",
         "95th pct. (\\%)", "Date rules flag (\\%)"], rows, "rrlrrrr", longtable=True,
        caption="Synthetic data: error with missing or estimated billing periods (E5).",
        label="tab:e5"))
    e8 = rd("e8_modes.csv")
    full = e8[e8["availability"] == 1.0]
    rows = [[tex_escape(r.spec.replace("_", " ")), MODE_LABELS[r.mode], fmt(r.burden, 0),
             f"{fmt(r.burden_lo, 0)}--{fmt(r.burden_hi, 0)}", pct(r.mare, 1),
             pct(r.selection_change, 1)] for r in rows_of(full)]
    (out / "tab_modes.tex").write_text(_tabular(
        ["Specification", "Collection mode", "Minutes", "90\\% interval", "MARE (\\%)",
         "Selection change (\\%)"], rows, "llrrrr"))
    sob = rd("sobol_burden.csv").sort_values("ST", ascending=False).head(10)
    rows = [[tex_escape(r.parameter), fmt(r.S1, 3), fmt(r.S1_conf, 3), fmt(r.ST, 3),
             fmt(r.ST_conf, 3)] for r in rows_of(sob)]
    (out / "tab_sobol.tex").write_text(_tabular(
        ["Time parameter", "$S_1$", "$\\pm$", "$S_T$", "$\\pm$"], rows, "lrrrr"))
    ilp = rd("e6_ilp.csv")
    rows = [[fmt(r.budget_extra_min, 0), r.condition, "yes" if r.primal_feasible else "no",
             pct(r.simulated_loss, 2), pct(r.enumeration_optimum, 2), pct(r.regret, 2)]
            for r in rows_of(ilp)]
    (out / "tab_ilp.tex").write_text(_tabular(
        ["Added budget (min)", "Solver status", "Feasible", "ILP choice, simulated (\\%)",
         "Enumeration optimum (\\%)", "Regret (pp)"], rows, "rllrrr"))
    tests = rd("e2_hypothesis_tests.csv")
    rows = [[r.id, tex_escape(r.description), str(r.n), pct(r.median_a, 1), pct(r.median_b, 1),
             "$<0.001$" if r.p_holm < 0.001 else fmt(r.p_holm, 3)] for r in rows_of(tests)]
    (out / "tab_tests.tex").write_text(_tabular(
        ["", "Comparison (a vs b)", "$n$", "Median a (\\%)", "Median b (\\%)", "Holm $p$"],
        rows, "lp{0.5\\linewidth}rrrr"))
    paths = rd("e2_accuracy.csv")
    paths = paths[paths["condition"] == "path_vs_normal_year"]
    rows = [[tex_escape(r.label), pct(r.q05, 1), pct(r.median, 1), pct(r.q95, 0),
             pct(r.share_above_10pct, 0)] for r in rows_of(paths)]
    (out / "tab_paths.tex").write_text(_tabular(
        ["Estimator of annual savings", "5th pct.", "Median", "95th pct.", "Share $>10\\%$"],
        rows, "p{0.5\\linewidth}rrrr"))
    bands = rd("e2_by_savings_fraction.csv")
    piv = bands.pivot(index="estimator", columns="savings_fraction", values="median_are")
    order = ["below 10%", "10-20%", "above 20%"]
    rows = [[tex_escape(est.replace("eei_", "").replace("_", " ")),
             *[pct(piv.loc[est, c], 0) for c in order]] for est in piv.index]
    (out / "tab_savings_bands.tex").write_text(_tabular(
        ["Estimator", "Savings $<10\\%$", "10--20\\%", "$>20\\%$"], rows, "lrrr"))
    acc = rd("e2_accuracy.csv")
    acc = acc[acc["condition"].isin(list(COND_NAMES))]
    rows = [[tex_escape(NAMED_SPECS[r.spec][0][:60]), COND_NAMES[r.condition], r.category,
             pct(r.q05, 2), pct(r.median, 2), pct(r.q95, 1), pct(r.mare_capped, 1),
             pct(r.share_above_10pct, 1)] for r in rows_of(acc)]
    (out / "tab_accuracy_full.tex").write_text(_tabular(
        ["Specification", "Condition", "Type", "5th", "Median", "95th", "MARE", "$>10\\%$"],
        rows, "p{0.36\\linewidth}llrrrrr", longtable=True,
        caption="Synthetic data: absolute relative error (\\%) of the verified quantity by "
        "specification and condition (E2).", label="tab:acc-full"))
    params = bm.time_parameters(cfg.burden)
    rows = [[tex_escape(p.name), fmt(p.low, 2), fmt(p.mode, 2), fmt(p.high, 2)] for p in params]
    (out / "tab_time_parameters.tex").write_text(_tabular(
        ["Time parameter (minutes)", "Low", "Mode", "High"], rows, "lrrr"))
    flat = pd.json_normalize(cfg.model_dump(mode="json"), sep=".").iloc[0]
    rows = [[tex_escape(str(k)), tex_escape(str(val))[:70]] for k, val in flat.items()
            if not str(k).startswith(("burden.elements", "burden.modes", "hypothesis"))]
    (out / "tab_parameters.tex").write_text(_tabular(
        ["Parameter", "Value"], rows, "p{0.55\\linewidth}p{0.38\\linewidth}", longtable=True,
        caption="Configuration of the reported run (\\texttt{configs/paper.yaml}). Values not "
        "attributed to a source in the comments of that file are hypothetical scenario "
        "parameters.", label="tab:params"))
    view = schema_view()
    rows = []
    for cls in view.all_classes():
        for slot in view.class_induced_slots(cls):
            unit = slot.unit.ucum_code if slot.unit is not None else ""
            rows.append([tex_escape(str(cls)), tex_escape(slot.name), tex_escape(str(slot.range)),
                         "yes" if slot.required else "no", tex_escape(unit or "")])
    (out / "tab_schema.tex").write_text(_tabular(
        ["Class", "Element", "Range", "Required", "Unit"], rows, "llllp{0.1\\linewidth}",
        longtable=True, caption="Elements of the evidence schema (generated from the LinkML "
        "source).", label="tab:schema"))


def build(config_path: Path, out: Path | None = None) -> Path:
    cfg = load_config(config_path)
    res = REPO_ROOT / "results" / cfg.name
    out_dir = out or (REPO_ROOT / "paper" / "generated" if cfg.name == "paper"
                      else res / "generated")
    out_dir.mkdir(parents=True, exist_ok=True)
    values = build_values(res, cfg)
    header = [
        "Generated by reapschema.report; do not edit.",
        f"config: {cfg.name}",
        f"results-hash: {summaries_hash(REPO_ROOT / 'results' / 'summaries' / cfg.name)}",
    ]
    values.write(out_dir / "values.tex", header)
    build_tables(res, out_dir, cfg)
    (out_dir / "config_used.yaml").write_text(
        yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False))
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    print(build(Path(args.config)))


if __name__ == "__main__":
    main()
