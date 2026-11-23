# Data sources, variables and limitations

Provenance of every downloaded file (URL, query, retrieval date, SHA-256, terms) is in
`data/MANIFEST.yaml`. The source rank follows the hierarchy used in the bibliography
(1 regulation and docket documents; 2 agency datasets; 3 peer-reviewed literature and
standards; 4 government and national-laboratory reports; 5 grey literature). No
rank-5 source is used for any parameter.

## Inputs

| Input | Source (rank) | Use | Limitations |
|---|---|---|---|
| Rule text and PRA notice | 91 FR 62600–62633, FR Doc. 2026-20178, XML, JSON and official PDF (1) | Data requirements; burden figures; scoring tables | Regulatory text was also confirmed in the eCFR current as of 2026-11-19 |
| OMB inventory for 0570-0067 | reginfo.gov ICR 202602-0570-001 (1) | Current responses, hours, respondents | Values transcribed from the web record (`data/transcribed/`); the supporting statement on file predates the rule |
| OIG audit 34001-0001-21 (2016) and OIG memorandum of 2023-01-09 | USDA OIG (4) | Kinds of reporting error observed historically | The audit was retrievable only from an Internet Archive capture; its estimates concern fiscal years 2009–2014 and the reporting system then in use |
| End-use load profiles | NREL ComStock, 2024 release 2, AMY2018, State aggregates for four building types (2; methodology report rank 4) | Hourly end-use shapes and temperature response of commercial facilities | Aggregates of many modelled buildings, smoother than a single facility; no agricultural building types |
| Irradiance | NSRDB as distributed by PVGIS 5.2 (`PVGIS-NSRDB`), 2005–2015, hourly, horizontal components (2/4) | Photovoltaic simulation at the hypothetical sites | Retrieved through PVGIS rather than the NREL developer API, which requires a registered key; direct normal irradiance is reconstructed from the horizontal beam component and solar elevation; coverage ends at 60°N |
| Site temperature and wind | ERA5 reanalysis as returned by PVGIS 5.2 (2/4) | Load response and cell temperature (conditions at the facility) | Reanalysis grid values, not measurements |
| Station temperature | NOAA ISD-Lite, nearest station with at least 95% hourly coverage in every year (2) | Degree days as a verifier would compute them | Median site-to-station distance is reported in the manuscript; gaps are interpolated |
| Electricity price | EIA average commercial price by State, 2020 (latest year in the file) (2) | Energy charges, simple payback | State averages; no tariff structure |
| Award sizes and mix | USAspending.gov, Assistance Listing 10.868, FY2021–FY2023 (2) | Share of RES among projects; distribution of project size; State weights | Financial data only; category inferred from the award description; FY2021–2022 awards are used for size because the 25% cost-share limit applied |
| PVWatts reference run | NREL PVWatts v8 API, one site (4) | Independent check of the pvlib implementation on identical weather | One site and geometry |

## Hypothetical inputs

- **Sites.** One illustrative rural location per State (`configs/sites.yaml`). They are
  not REAP project locations. Puerto Rico, the U.S. Virgin Islands and the Western
  Pacific, which §4280.150 treats as States, are not represented.
- **Agricultural load shapes.** Irrigation, grain-drying and dairy facilities use the
  parametric shapes in `configs/facility_shapes_hypothetical.yaml`. They represent
  electricity only; fuel use (for example propane for grain drying) is outside the
  model.
- **Scenario parameters.** Noise levels, occupancy changes, measure reductions, cost per
  watt, payback distribution, billing behaviour, error-class rates, competition size and
  funding, non-energy score points and element times are scenario values recorded in
  `configs/paper.yaml`. Error-class rates are not estimates of error prevalence in REAP
  submissions.
- **Element times.** No public source reports respondent time by data element for this
  collection. Times are triangular distributions stated in the configuration and scaled
  so that the evidence required by the current rule equals two responses of the
  notice's average size. The scaling does not change the ordering of specifications by
  burden; the Sobol analysis in the supporting information shows which times drive the
  burden differences.

## Transcribed values

`data/transcribed/` holds values typed from documents, each entered twice
(`entry_a`, `entry_b`). `tests/test_requirements.py` requires the two entries to agree
and to match the values parsed from the Federal Register XML.

## Processed data

| File | Content |
|---|---|
| `data/processed/load_profiles.parquet` | Mean hourly end-use electricity by State, building type, month, day type and hour, as a share of annual electricity |
| `data/processed/load_response.json` | Cooling and heating balance points and hour-of-day coefficients fitted to the ComStock HVAC end uses against 2018 site temperature, with fit R² |
| `data/processed/weather/<ST>.parquet` | Hourly (UTC) irradiance, site temperature, wind, station temperature, 2005–2015 (rebuilt locally) |
| `data/processed/prices.csv` | State commercial price, USD/kWh |
| `data/processed/reap_awards.csv` | Award amount by fiscal year, State and category |

ComStock aggregate time series are stamped in Eastern Standard Time; they are shifted
to each State's local standard time before averaging. This was checked against the
hour of the weekday lighting peak across time zones.

## Synthetic outputs

See `data/synthetic/README.md`. Every synthetic file name contains `synthetic` and each
sidecar records `"data_basis": "synthetic"`.

## Empirical validity

No open dataset with labelled pre- and post-retrofit meter data for small rural
facilities was found. The Building Data Genome Project 2 contains hourly meter data
without retrofit labels; the EVO testing portal is not openly downloadable. Estimator
error distributions are therefore verified on synthetic data only, and the model's
agreement with real REAP submissions is not established.
