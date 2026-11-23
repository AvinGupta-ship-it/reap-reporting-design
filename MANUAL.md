---
title: "Verification Accuracy and Reporting Burden for Metered Performance Evidence in Rural Energy Grants"
subtitle: "Project Technical Design Manual"
date: "Regulatory status verified November 23, 2026"
---

# 1. Project Specification

This manual is the complete technical specification for one computational research project. Its finished form is a reproducible research repository, a scientific preprint, and a formal regulatory comment. Section 1 specifies the project (A: identity and significance; B: methodology; C: data and references; D: codebase; E: experiments; F: validation and limitations; G: preprint; H: regulatory comment; I: final artifacts). Section 2 sets the scientific standards the work must meet. Section 3 defines the deliverable architecture.

**Conventions.** Every statement of regulatory status was verified from the Federal Register, Regulations.gov, agency web pages or docket documents on November 23, 2026, and must be re-verified on the day any comment is submitted. Sources marked **[verify]** were identified but not confirmed (DOI not resolved, document not read, or URL not tested); they must be confirmed before use, and may not be cited until they are. Facts drawn from secondary sources are labeled as such. Numbers quoted from Federal Register documents were read from text extractions and must be checked against the official PDF before they are quoted in a manuscript or comment. All scenario parameters not taken from a cited source are hypothetical and are labeled as such in code, figures and text.


## 1.A Project identity and research significance

**Manuscript title.** *Verifying documented performance in small renewable-energy and efficiency grants: a machine-readable evidence schema, automated validation, and the accuracy–burden frontier for twelve-month pre/post metered data*

**Agency and docket.** U.S. Department of Agriculture, Rural Business-Cooperative Service (RBCS). Docket RBS-26-Business-0529.

**Verified proceeding.** "Unleashing American Energy and Economic Prosperity; Rural Energy for America Program (REAP)," **final rule with comment period**, 91 FR 62600–62633 (October 1, 2026), FR Doc. 2026-20178, RIN 0570-AB13, 7 CFR part 4280 subparts B and C, effective October 16, 2026. The docket is not a stand-alone information-collection notice: the Paperwork Reduction Act (PRA) notice for OMB Control Number 0570-0067 ("Revision of a currently approved information collection") is embedded in the rule's preamble.

**Status (verified November 23, 2026).**

- Comments on the rule: closed **November 2, 2026**.
- **PRA comments on the information collection: open until November 30, 2026** ("must be received by November 30, 2026 to be assured of consideration"), via Regulations.gov under docket RBS-26-Business-0529 (search by docket or RIN 0570-AB13). This is the earliest open deadline among the ten projects. PRA contact: Kimble Brown, RD Innovation Center.
- Current OMB approval for 0570-0067: ICR reference 202602-0570-001, approved April 20, 2026, expiring September 30, 2028, 81,765 annual responses and 257,879 annual burden hours. No pending OMB submission for the revision was visible on reginfo.gov at verification; a subsequent OMB submission (and possibly a 30-day notice) may follow and must be checked.

**What the open comment addresses.** The four PRA questions: (a) whether the collection is necessary, including practical utility; (b) accuracy of the burden estimate, including methodology and assumptions; (c) ways to enhance quality, utility and clarity; (d) ways to minimize burden, including automated collection and information technology. The substance of the rule (eligibility, scoring, award structure) is outside this comment.

**Burden estimate published in the notice.** Respondents "nonprofit corporations and institutions of higher education" (apparently inconsistent with REAP subpart B applicants, who are agricultural producers and rural small businesses); 2,977 respondents; 37.64 responses per respondent; 112,073 responses; 1.34 hours per response; 150,883 total hours. The products do not reconcile exactly (2,977 × 37.64 = 112,054; 112,073 × 1.34 = 150,178), and the section is labeled a "Notice of Extension" although it is a revision. No per-form burden table appears in the Federal Register text.

**Rule changes that define the information collection (from the preamble; verify against regulatory text).**

1. Projects must be constructed and operational before application (§4280.122). Applicants submit **12 months of actual post-installation energy production or savings data and 12 months of pre-installation data**; awards are based on documented performance. Annual energy production is measured at the common point of electrical coupling (e.g., the inverter), in kWh or MWh (§4280.104); metering arrangements (net metering, net billing, aggregate and virtual net metering) are defined.
2. Post-award semi-annual reports, final project development reports and Form RD 4280-3D (Annual Outcome Project Performance Certification) are eliminated (§4280.160); a new Equipment report is added.
3. Technical-report Appendices A–D are removed; their content is in §4280.131. Energy assessor and auditor qualifications revised.
4. One national competition (plus a competition for requests ≤ $20,000), selecting the top two scoring applications per State meeting the minimum score, then rank order (§4280.150); streamlined scoring (§4280.140).
5. Storage capped at 120% of average energy use over the prior 12 months; payback no longer than useful life; newly ineligible categories include multilocation projects and solar or wind projects with components from foreign-adversary countries.

**Oversight evidence.** USDA OIG Audit Report 34001-0001-21, "Rural Energy for America Program" (August 2016), as summarized in the OIG memorandum "Prior OIG Audits Relevant to Rural Development's Inflation Reduction Act Funding" (January 9, 2023; https://usdaoig.oversight.gov/sites/default/files/reports/2023-12/RD-Lessons-Learned-MemoFinal.pdf), found REAP performance data incomplete or inaccurate, missing performance reports, and inaccurate reported energy produced or saved. Secondary reporting of the audit gives an estimated 80% of annual performance reports (4,338 of 5,423) lacking accurate energy data, largely from savings-calculation errors and absence of calculation guidance. The original report PDF must be located before these figures are cited.

**Exact regulatory question.** Does the revised collection obtain the information needed to verify claimed energy production and savings from 12-month pre/post data with practical utility, is the burden estimate accurate, and what data elements, formats and automated checks would improve verification accuracy while reducing burden?

**Scientific problem.** Under the new rule, award decisions rest on 12 months of pre- and post-installation data. Such data are short, weather-dependent, affected by billing-period misalignment, net-metering conventions and estimated reads, and prone to the calculation errors the OIG documented. How accurately annual production or savings can be inferred from such data, and how much accuracy each additional data element buys relative to the respondent time it costs, is a measurement-and-verification (M&V) and information-design question that can be answered quantitatively with physically grounded synthetic data.

**Central research question.** For the project types REAP funds, what is the error distribution of annual energy production and savings estimated from 12-month pre/post evidence under alternative data specifications; which automated validation rules detect the reporting errors observed historically; and what set of data elements minimizes verification error, and the probability that verification error changes competitive selection, per unit of respondent burden?

**Original contribution.**

1. A formal, machine-readable schema (LinkML, exported to JSON Schema and tabular templates) for REAP performance evidence aligned to §4280.104 and §4280.131 and the Equipment report.
2. A physically grounded synthetic-applicant generator (explicitly synthetic) combining public building end-use load profiles, measured-weather photovoltaic simulation, efficiency measures, billing-cycle and metering processes, and controlled error injection.
3. A quantitative evaluation of verification error under monthly-bill versus interval data, with and without billing-period dates, weather normalization and gross/net metering metadata, using open M&V methods.
4. An integer-programming formulation of the accuracy–burden trade-off over data elements, producing a Pareto frontier and a decision-relevant metric: the probability that verification error alters selection under the rule's top-two-per-State procedure.

**Independent value.** Pre/post performance evidence for distributed energy projects is used across federal, state and utility programs. The schema, generator and evaluation method are reusable for any program that awards funds on documented performance.

**Relationship to the decision.** OMB approval of the revised collection and RBCS's response to PRA comments are the decisions at stake. The project's results speak directly to practical utility, burden accuracy, quality and automation, which are the four PRA questions.

**Chain of relevance.** Question (how accurately can 12-month evidence verify performance, at what burden?) → schema + synthetic applicants + M&V estimation + validation + burden optimization → error distributions, detection rates, Pareto frontier, burden-arithmetic audit → PRA questions (a)–(d) for OMB 0570-0067 → recommendations on data elements, formats, automated validation and burden estimation.

**Feasibility relative to the deadline.** The burden-arithmetic audit and the schema can be completed before November 30, 2026; a focused PRA comment can be filed on that basis with whatever validated computational results exist by then. The full study and preprint proceed independently of the deadline, and a later OMB-stage comment opportunity (if a 30-day notice is published) should be checked.

## 1.B Mathematical and computational methodology

**B.1 Evidence schema.** Classes: `Applicant`, `Facility` (location, climate zone, nearest weather station), `Project` (technology class from a controlled vocabulary for RES and EEI types; installed capacity with unit; in-service date), `Meter` (type: utility revenue meter, inverter, sub-meter; netting arrangement; interval length), `BillingRecord` (start date, end date, read type actual/estimated, kWh imported, kWh exported, demand, cost), `IntervalSeries` (timestamped energy with time zone), `PerformanceClaim` (annual production or savings, method, normalization basis, uncertainty), `EquipmentItem` (make, model, quantity, country of origin of components). Constraints are expressed in the schema (types, units via UCUM codes, cardinalities) and in a rule layer (B.4).

**B.2 Synthetic applicant generator.** Each synthetic applicant \(n\) is defined by facility type, location and project:

- *Baseline load*: hourly load from NREL ComStock/ResStock end-use load profiles (or EIA CBECS-derived shapes for agricultural facilities where profiles are lacking, with stated limitations), scaled to a sampled annual consumption, with multiplicative day-to-day noise and occupancy changes.
- *Weather*: actual-year hourly weather from NSRDB (for PV) and NOAA ISD (for degree days) at the facility location for two consecutive years (pre and post), so that weather differs between periods as in reality.
- *RES*: photovoltaic production simulated with pvlib (single-diode or PVWatts model with documented loss assumptions) from actual-year NSRDB irradiance; wind using power curves and measured wind where included.
- *EEI*: measure-specific load reductions (lighting fraction, HVAC efficiency improvements, grain-dryer or irrigation pumping efficiency) applied to relevant end uses.
- *Metering and billing*: billing cycles of 27–34 days with read-date jitter; estimated reads with probability \(p_e\); net-metering netting of exports per arrangement; inverter-level production meter for RES.
- *Errors*: injected at controlled rates by class — unit errors (kWh/MWh), transposed digits, wrong billing period, double counting across meters, gross/net confusion, savings computed without weather normalization, use of nameplate × hours instead of measured data. Error classes follow those described in the OIG audit summary; rates are scenario parameters (synthetic), not estimates of REAP error prevalence.

Ground truth (true annual production; true weather-normalized savings) is known for every synthetic applicant.

**B.3 M&V estimators.**

*EEI (whole-facility, monthly bills).* Following ASHRAE Guideline 14 and the open CalTRACK monthly method, fit baseline models on pre-period billing data:
\[
E_m = \beta_0 d_m + \beta_H\,\mathrm{HDD}_m(T_H)+\beta_C\,\mathrm{CDD}_m(T_C)+\varepsilon_m,
\]
with \(d_m\) days in billing period \(m\), degree days computed on each bill's actual dates, balance points \(T_H,T_C\) selected by grid search with model selection by adjusted \(R^2\)/CV(RMSE). Avoided energy use \(\hat S=\sum_{m\in\text{post}}[\hat E_m^{\mathrm{base}}-E_m]\) and normalized annual savings using a typical meteorological year. Uncertainty by the ASHRAE 14 fractional savings uncertainty approximation with autocorrelation adjustment, compared against a residual block-bootstrap.

*RES.* Measured 12-month production \(\hat P\) and a weather-normalized annual production \(\hat P_{\mathrm{TMY}}=\hat P\cdot \frac{Y_{\mathrm{TMY}}}{Y_{\mathrm{actual}}}\), with \(Y\) the modeled yield for the system under typical and actual weather. Plausibility statistic \(z=(\hat P-\hat P_{\mathrm{model}})/\sigma_{\mathrm{model}}\) where \(\hat P_{\mathrm{model}}\) uses declared capacity, orientation and location.

**B.4 Validation rules.** A rule set \(\mathcal{V}\) of deterministic and statistical checks: unit and range checks; billing-period continuity and overlap; sum of billing-period days consistency; import/export consistency with metering arrangement; capacity-factor bounds by technology and location (from the physical model); savings bounded by baseline end-use share; storage ≤ 120% of average use; payback ≤ declared useful life; RES plausibility \(|z|<z^*\); EEI model-fit criteria (CV(RMSE), net determination bias). Each rule is evaluated on synthetic applicants with known injected errors, yielding per-rule and ensemble detection rates, false-positive rates, and ROC curves for statistical thresholds.

**B.5 Burden model.** Each data element \(j\) has respondent time \(\tau_j\) depending on the collection mode (manual transcription from bills; upload of utility CSV; Green Button download; automated utility data access). Element times are modeled as distributions with ranges documented from available sources (the PRA supporting statement if obtainable; published time-use or survey-burden literature; explicit assumptions where none exist). The model is calibrated so that total burden for the current specification equals the agency's published per-response estimate, and the reconciliation of the notice's burden arithmetic is reported separately.

**B.6 Accuracy–burden optimization.** Binary decision \(x_j\in\{0,1\}\) for each element (or mode), with feasibility constraints (elements required by regulation fixed at 1; logical dependencies, e.g., degree-day normalization requires billing dates). Accuracy is the expected loss \(\mathcal{L}(\mathbf{x})\), estimated by simulation, for two loss functions: (i) mean absolute relative error of verified annual production/savings; (ii) probability that verification error changes selection under the top-two-per-State rule, simulated with the §4280.140 scoring formula applied to synthetic competitions. Because \(\mathcal{L}\) is evaluated by simulation, the frontier is computed by (a) exhaustive evaluation when the number of optional elements is ≤ 16 (≤ 65,536 specifications, feasible with vectorized simulation), otherwise (b) a surrogate-assisted ILP: fit \(\mathcal{L}(\mathbf{x})\approx w_0+\sum_j w_j x_j+\sum_{j<k}w_{jk}x_jx_k\) on a designed sample, then solve \(\min \mathcal{L}\ \text{s.t.}\ \sum_j \tau_j x_j\le B\) for a sweep of \(B\) with HiGHS, and verify selected specifications by direct simulation.

## 1.C Data and scientific references

| Source | Identifier | Use | Limitations |
|---|---|---|---|
| Final rule with PRA notice | 91 FR 62600; FR Doc 2026-20178; https://www.federalregister.gov/documents/2026/10/01/2026-20178/unleashing-american-energy-and-economic-prosperity-rural-energy-for-america-program-reap ; XML https://www.federalregister.gov/documents/full_text/xml/2026/10/01/2026-20178.xml | Data requirements (§§4280.104, .122, .131, .140, .150, .160); burden estimate | — |
| OMB ICR record 0570-0067 | reginfo.gov ICR 202602-0570-001 | Current inventory, forms, supporting statement | Supporting statement download failed at verification |
| eCFR 7 CFR 4280 subparts B and C | https://www.ecfr.gov/current/title-7/subtitle-B/chapter-XLII/part-4280/subpart-B | Regulatory text | Check "up to date as of" date |
| USDA OIG memo summarizing Audit 34001-0001-21 | https://usdaoig.oversight.gov/sites/default/files/reports/2023-12/RD-Lessons-Learned-MemoFinal.pdf | Documented error classes | Original audit PDF to be located |
| NREL End-Use Load Profiles (ComStock, ResStock) | https://www.nrel.gov/buildings/end-use-load-profiles.html and Open Energy Data Initiative **[verify URLs]** | Hourly baseline loads by building type and location | Building types; agricultural facilities underrepresented |
| NSRDB | https://catalog.data.gov/dataset/national-solar-radiation-database-nsrdb ; Sengupta et al. (2018) | Hourly irradiance, temperature | NREL API key required (registration by the project owner) |
| NOAA ISD | https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database **[verify]** | Temperatures for degree days | Station representativeness |
| PVWatts v5 manual | Dobos (2014), NREL/TP-6A20-62641, https://www.osti.gov/biblio/1158421 | PV model and loss assumptions | — |
| pvlib python | Holmgren, Hansen & Mikofski (2018), *Journal of Open Source Software* **[verify DOI]** | PV simulation | — |
| CalTRACK methods | caltrack.org **[verify]** | Open monthly-billing M&V specification | Developed for California programs |
| ASHRAE Guideline 14; IPMVP | ASHRAE; Efficiency Valuation Organization | M&V uncertainty methods | Proprietary documents; equations cited from open literature where possible |
| Green Button (NAESB REQ.21 ESPI) | greenbuttondata.org **[verify]** | Automated utility data format | Utility adoption varies |
| EIA retail electricity prices (EIA-861 / Electric Power Monthly) | api.eia.gov **[verify]** | Valuation of savings in scoring | — |
| USDA REAP award charts; USAspending Assistance Listing 10.868 | rd.usda.gov award PDFs; usaspending.gov | Distribution of project types and sizes for synthetic population | Financial data only |

**References.** Wang, R. Y., & Strong, D. M. (1996). Beyond accuracy: What data quality means to data consumers. *Journal of Management Information Systems*, 12(4), 5–33 **[verify DOI]**. Pipino, L. L., Lee, Y. W., & Wang, R. Y. (2002). Data quality assessment. *Communications of the ACM*, 45(4), 211–218 **[verify]**. Fellegi, I. P., & Sunter, A. B. (1969). A theory for record linkage. *JASA*, 64, 1183–1210 **[verify DOI]** (duplicate-claim detection). Dobos (2014); Sengupta et al. (2018) *Renewable and Sustainable Energy Reviews* 89, 51–60 **[verify DOI]**. Kissock, Haberl & Claridge on inverse change-point models for building energy (ASHRAE RP-1050) **[verify]**. Literature on response burden measurement (e.g., in the *Journal of Official Statistics*) **[locate and verify]**.

## 1.D Research codebase specification

Repository `reap-reporting-schema`, package `reapschema`.

| Module | Function |
|---|---|
| `reapschema/schema/` | LinkML source; generated JSON Schema, pydantic models, CSV templates, documentation |
| `reapschema.requirements` | Parser that extracts data requirements from the rule XML into a traceability table (requirement → schema element) |
| `reapschema.synth.loads` | Baseline load sampling from end-use load profiles |
| `reapschema.synth.weather` | NSRDB and ISD retrieval and alignment |
| `reapschema.synth.pv` | pvlib simulation |
| `reapschema.synth.eei` | Efficiency measure models |
| `reapschema.synth.billing` | Billing cycles, estimated reads, netting |
| `reapschema.synth.errors` | Error injection with ground-truth labels |
| `reapschema.mv` | Degree-day change-point models, savings and uncertainty, RES normalization |
| `reapschema.validate` | Rule engine (schema validation plus rule layer); per-rule diagnostics |
| `reapschema.burden` | Element time model; burden arithmetic audit |
| `reapschema.optimize` | Exhaustive and surrogate-ILP frontier computation |
| `reapschema.competition` | Scoring and top-two-per-State selection simulation |

Libraries: LinkML, jsonschema, pydantic, pandas, NumPy, SciPy, statsmodels, pvlib, xarray, linopy/highspy, matplotlib, pytest, hypothesis.

Tests: schema round-trip (YAML → JSON Schema → validation of fixtures); every regulatory requirement in the traceability table maps to a schema element; degree-day model recovers known coefficients from synthetic data without noise; billing aggregation conserves energy; validation rules flag each injected error class in unit fixtures; burden audit reproduces the published figures and their discrepancies.

Network hosts required: www.federalregister.gov, www.ecfr.gov, www.reginfo.gov, developer.nrel.gov, oedi-data-lake (AWS open data) or data.openei.org, www.ncei.noaa.gov, api.eia.gov.

## 1.E Computational experiments

| # | Varied | Output | Purpose | Criteria |
|---|---|---|---|---|
| E1 | — | Burden arithmetic reconciliation; respondent-category consistency | PRA question (b) | Exact arithmetic; documented discrepancies |
| E2 | Data specification (monthly bills vs interval; billing dates; weather normalization; netting metadata) | Error distribution of verified annual production/savings | Accuracy of evidence types | Median absolute relative error; 90% intervals |
| E3 | Error classes and rates | Detection and false-positive rates per rule and ensemble | Validation effectiveness | ROC/AUC; recall at fixed false-positive rate |
| E4 | Weather difference between pre/post years | Bias in unnormalized vs normalized savings | Need for normalization | Bias and RMSE |
| E5 | Missing or estimated months | Error and validation outcomes | Effect of incomplete evidence | Error growth curves |
| E6 | Element subsets under burden budgets | Pareto frontier (accuracy vs burden) | Optimal information design | Frontier with Monte Carlo bands |
| E7 | Specification | Probability verification error changes selection | Decision consequence | Probability with intervals |
| E8 | Collection mode (manual vs automated utility data) | Burden and error | PRA question (d) | Burden reduction at equal accuracy |

**Competing outcomes.** Monthly bills with dates and weather normalization may achieve accuracy close to interval data (in which case the marginal elements are cheap metadata, not new data streams), or interval data may be necessary for some project types; validation may catch most error classes cheaply, or some (gross/net confusion, unnormalized savings) may require specific metadata; selection may be robust to verification error or sensitive near score cutoffs.

## 1.F Validation and limitations

1. *Numerical correctness*: unit tests on estimators against analytical cases; energy conservation in synthetic billing; reproducibility.
2. *Model verification*: M&V estimators reproduce published CalTRACK/ASHRAE test cases where available; pvlib output matches PVWatts for identical inputs within documented tolerance.
3. *Empirical validity*: synthetic applicants are not REAP data; error-class prevalence is not estimated. If public metered datasets with pre/post periods exist (e.g., open M&V benchmark datasets), use them to check estimator error distributions; otherwise state the limitation.
4. *Regulatory applicability*: results address PRA questions on the information collection only.

## 1.G Scientific preprint

**Title.** *Verifying documented performance in small renewable-energy and efficiency grants: a machine-readable evidence schema, automated validation, and the accuracy–burden frontier for twelve-month pre/post metered data.*

**Target venues.** *Energy Efficiency* (Springer); *Energy and Buildings*; *Data & Policy*. Preprint on arXiv (stat.AP) or SSRN.

**Structure.** Abstract; 1 Introduction (performance-based grant design; M&V with short billing records; data quality and response burden; documented REAP data problems; gap); 2 Methods (schema; synthetic generator; M&V estimators; validation rules; burden model; optimization; competition simulation); 3 Results (burden audit; accuracy by specification; validation performance; normalization; missing data; frontier; selection effects; collection modes); 4 Discussion; 5 Limitations; 6 Conclusions. *Figures*: (1) schema diagram; (2) synthetic generator pipeline; (3) error distributions by specification; (4) validation ROC curves by error class; (5) normalization bias vs weather difference; (6) accuracy–burden Pareto frontier; (7) selection-change probability vs specification. *Tables*: requirement-to-schema traceability (summary); validation rules; burden audit; frontier specifications. *SI*: full schema, generator parameters with sources, estimator details, additional results.

## 1.H Formal regulatory comment

**Proceeding and route.** PRA comment on OMB 0570-0067 in docket RBS-26-Business-0529 via Regulations.gov, received by **November 30, 2026**. Address it to the PRA notice in FR Doc. 2026-20178, referencing the four PRA questions. Re-check reginfo.gov for an OMB submission and any 30-day notice, which would be a second opportunity.

**Issues addressed.** PRA (a) practical utility of the 12-month pre/post evidence as specified; (b) accuracy of the burden estimate, including the reconciliation and respondent-category issues found in E1; (c) quality and clarity: specification of evidence elements (billing dates, meter type, netting arrangement, normalization method), standardized machine-readable format; (d) automated collection (utility data access formats; schema-based validation at submission).

**Findings that could support recommendations (determined by results).** Element-level accuracy gains and burden costs (E2, E6); detection performance of automated checks (E3); effect of normalization (E4); consequences for selection (E7); burden reductions from automated modes (E8). Recommendations are limited to information-collection design and burden estimation.

**Structure.** Identification and docket; summary of recommendations organized by PRA questions (a)–(d); burden-estimate analysis; evidence-specification analysis with Figures 3, 4, 6; recommended data elements and formats; limitations (synthetic data, no REAP microdata); references; technical attachment including the schema documentation.

## 1.I Final artifacts

Repository `reap-reporting-schema` (schema with generated artifacts, generator, estimators, validation engine, optimization); synthetic applicant datasets (labeled synthetic) with generator configurations; seven figures and four tables; manuscript (LaTeX, PDF, DOCX) and SI; PRA comment (DOCX, PDF) and technical attachment.

# 2. Scientific Standards

The standards in this section apply to every part of this project. Where Section 1 is more specific, Section 1 governs.

## 2.1 Computational reproducibility

1. **Single-command reproduction.** Every repository exposes one entry point (`make all`, or `python -m reapschema.pipeline run --config configs/paper.yaml`) that regenerates every number, table and figure in the manuscript and the comment attachments from raw inputs. A second target (`make quick`) runs a reduced configuration (fewer Monte Carlo replicates, coarser grids) for continuous integration and must finish on a laptop.
2. **Pinned environments.** Python ≥ 3.11. Dependencies are declared in `pyproject.toml` and locked (`uv.lock` or `conda-lock.yml`). A `Dockerfile` or `environment.yml` reproduces the environment. Solvers external to Python (HiGHS, AERMOD, AERMET) are pinned by version and checksum, and the build fetches them by script.
3. **Seeded randomness.** All stochastic code takes an explicit `numpy.random.Generator`. Seeds are stored in the configuration file and written into every output's metadata. Parallel Monte Carlo uses `SeedSequence.spawn` so results do not depend on worker count.
4. **Configuration as data.** Every experiment is a YAML file under `configs/` validated by a schema (pydantic). No parameter that appears in the manuscript may be hard-coded in a module.
5. **Output provenance.** Each output file (Parquet, NetCDF, CSV, PNG/PDF) carries or is accompanied by a JSON sidecar recording the git commit, configuration hash, input-data checksums, package versions and seed.
6. **Deterministic figures.** Figures are produced only by scripts in `figures/` reading saved results, never by notebooks with hidden state. Fonts and styles are fixed in a shared `matplotlibrc`.

## 2.2 Numerical validation

Each project separates four levels of evidence, and each manuscript reports them separately:

| Level | Question | Typical evidence |
|---|---|---|
| Numerical correctness | Does the code compute what the equations say? | Unit tests, analytical solutions, conservation and identity checks, convergence under refinement, solver optimality certificates |
| Model verification | Do the equations represent the intended conceptual model? | Comparison with independent implementations or published benchmark cases; limiting-case behavior; dimensional analysis |
| Empirical validity | Does the model reproduce observations of the real system? | Out-of-sample comparison with measured data where any exist; otherwise explicitly stated as not established |
| Regulatory applicability | Does the result bear on the decision the agency is actually making? | Mapping from result to a specific provision, question or criterion in the docket |

Minimum requirements for all projects:

- Monte Carlo estimators report standard errors and the replicate count is chosen so that the Monte Carlo standard error of every reported headline quantity is below 2% of its value (or a stated absolute tolerance), demonstrated by a convergence plot in the supporting information.
- Discretized solvers report a grid- or time-step-refinement study with the observed order of convergence.
- Optimization models report solver status, optimality gap (MILP gap ≤ 0.1% unless stated) and verify primal feasibility of the returned solution with an independent check.
- Units are carried with `pint` in input parsing and checked by dimensional tests at module boundaries; core numerical kernels may operate on plain arrays in SI units.
- Property-based tests (`hypothesis`) cover invariants (non-negativity, monotonicity in a parameter where theory requires it, conservation).

## 2.3 Source reliability and hierarchy

Sources are ranked and the rank is recorded in the bibliography database:

1. Statute, regulation (eCFR), and Federal Register documents; docket documents (technical support documents, supporting statements, memoranda to the docket).
2. Agency datasets with documented methodology (EPA AQS, EIA-930, PHMSA incident data, EMTS, AP-42, USGS).
3. Peer-reviewed literature and recognized technical standards (NFPA, IEC, API, ASTM).
4. National-laboratory and government technical reports (NREL, LBNL, Sandia, GAO, OIG, CRS).
5. Grey literature from trade associations, advocacy organizations and consultancies, used only to locate primary sources or to represent stakeholder positions, never as the sole basis of a quantitative parameter.

A parameter taken from rank-5 material must be flagged in the parameter table and included in the sensitivity analysis.

## 2.4 Data provenance

- Raw downloaded files are stored unmodified under `data/raw/` (or fetched on demand by `scripts/fetch_data.py` when licensing or size forbids redistribution), with a `data/MANIFEST.yaml` recording source organization, URL, retrieval date, SHA-256 checksum, license or terms of use, and the exact query parameters used.
- All transformations from raw to analysis-ready data are code in `src/reapschema/data/` and are idempotent. No manual spreadsheet edits.
- Synthetic data are generated only by code, stored under `data/synthetic/`, and every synthetic file name and metadata record carries the word `synthetic`. Figures based on synthetic data say so in the caption.
- Values digitized or transcribed from documents (tables in a Federal Register notice, a technical support document, a figure in a paper) are stored in `data/transcribed/` with a citation to page and table, and are double-entered and reconciled by a test that compares the two entries.

## 2.5 Citation accuracy

- Every reference is held in a single BibTeX file per repository. Every DOI is resolved through doi.org and the resolved metadata (title, authors, year, venue) is checked against the entry by a script (`scripts/check_refs.py`) that queries Crossref; mismatches fail the build.
- Federal Register documents are cited by volume, page, date and FR document number; regulations by CFR section and the eCFR "current as of" date; docket documents by their Regulations.gov document ID or FERC eLibrary accession number.
- A reference is cited only for a claim it actually supports. Statements in this manual marked **[verify]** identify sources that must be located and checked before use; they may not be cited until verified.
- No preprint DOI, journal acceptance or review status is stated unless it exists.

## 2.6 Statistical rigor

- Uncertainty is propagated, not appended: reported quantities are accompanied by intervals derived from the uncertainty model (parametric distributions, bootstrap, or posterior), with the interval type stated.
- Global sensitivity analysis uses variance-based Sobol indices (Saltelli estimator with Jansen formulas, implemented with `SALib`) when inputs are independent and the model is cheap enough for N(k+2) evaluations with N ≥ 2¹²; otherwise Morris elementary effects for screening followed by Sobol indices on the retained factors. Bootstrap confidence intervals on indices are reported.
- Hypothesis tests are pre-specified in the configuration, with multiplicity controlled (Holm or Benjamini–Hochberg as stated) when more than one comparison supports a single claim.
- Rare-event probabilities below 10⁻³ are estimated with variance reduction (importance sampling or subset simulation) or analytically, never by naive Monte Carlo with too few events. The number of observed events behind each estimate is reported.
- Distributions fitted to data report goodness of fit (Anderson–Darling or a likelihood-based comparison) and the effect of the distributional choice on headline results is tested.

## 2.7 Professional manuscript preparation

- Manuscripts are written in LaTeX (`revtex4-2` or `elsarticle` class, per the intended venue) with a single notation table per paper, SI units, and equations numbered. Every number in the text is generated by the pipeline into `paper/generated/values.tex` as LaTeX macros, so prose and results cannot drift apart. A test fails if any macro is undefined or stale.
- Figures are vector PDF with embedded fonts, colorblind-safe palettes (Okabe–Ito or viridis family), labeled axes with units, and captions that state the data basis (observed, modeled, synthetic, hypothetical scenario).
- Editable output: the LaTeX source plus a DOCX produced with `pandoc` from the same source. PDF output: compiled with `latexmk`.
- Author contributions, funding and competing-interest statements follow venue conventions. Acknowledgments name only people and organizations that contributed.
- Target venues are suggested in each project specification; the manuscript must also stand alone as a preprint (arXiv physics.soc-ph, stat.AP, eess.SY, or EarthArXiv / ESS Open Archive, as appropriate).

## 2.8 Regulatory relevance

Each comment satisfies these tests before it is finalized:

1. **Proceeding test.** The comment is addressed to the exact document and docket identified in the project specification and was confirmed open on the date of submission from the Federal Register or the agency docket. If the period has closed, the comment is not filed as if timely; the specification states the alternative (later stage of the same proceeding, or no filing).
2. **Scope test.** Each recommendation names the provision, question, criterion or decision in the docket it addresses and the agency authority under which it could be acted on in that proceeding.
3. **Evidence test.** Each recommendation is traced to a specific figure or table in the attachment and to the validation level (Section 2.2) that supports it. Recommendations resting only on hypothetical scenarios are phrased as requests for analysis, disclosure or clarification, not as findings about real facilities.
4. **Restraint test.** No claim of harm, violation, or benefit at a real facility is made without facility-specific evidence. Adverse or null results that bear on the question are reported.

Comments follow a common structure: (i) identification of commenter and docket; (ii) summary of recommendations (one page); (iii) the specific issue in the proposal; (iv) analysis and findings, with figures; (v) recommendations, each tied to a provision; (vi) limitations; (vii) references; (viii) technical attachment (a condensed version of the preprint and the repository archive identifier, if public). Comments are submitted as PDF with an editable DOCX retained.

## 2.9 Scientific integrity

- Conclusions are determined by validated results. Each project specification lists competing hypotheses and the observations that would distinguish them; the manuscript reports which outcome occurred, including null or unfavorable results.
- No empirical data, measurements, validation results, citations, or publication metadata are fabricated. A model that cannot be validated against observations is described as a verified model of stated assumptions, not as a prediction.
- Hypothetical scenarios are labeled as such everywhere they appear: configuration names (`scenario_hypothetical_*`), figure captions, table headers, and text.
- Any facility, site, or company is analyzed only from public documents, and inferences about it are stated with the evidence they rest on.

## 2.10 Research repository organization

The repository `reap-reporting-schema` uses this skeleton:

```
reap-reporting-schema/
├── README.md               # purpose, installation, reproduction, citation
├── LICENSE                 # BSD-3-Clause for code; CC BY 4.0 for text, figures, derived data
├── CITATION.cff
├── pyproject.toml
├── uv.lock                 # or conda-lock.yml
├── Dockerfile
├── Makefile
├── configs/                # experiment configurations (YAML), schema-validated
├── data/
│   ├── MANIFEST.yaml       # provenance of every input
│   ├── raw/                # unmodified downloads (or fetched by script)
│   ├── transcribed/        # values transcribed from documents, double-entered
│   ├── synthetic/          # generated synthetic inputs
│   └── processed/          # analysis-ready derived data
├── src/reapschema/          # importable library
├── scripts/                # fetch_data.py, check_refs.py, run_experiments.py
├── figures/                # one script per manuscript figure
├── notebooks/              # exploratory analysis with scientific content only
├── tests/                  # unit, property, validation and regression tests
├── results/                # generated outputs (git-ignored except small summaries)
├── docs/
│   ├── model.md            # mathematical specification of the model
│   ├── data.md             # data sources, variables, limitations
│   └── reproduction.md     # step-by-step reproduction and expected runtimes
├── paper/                  # LaTeX manuscript, SI, bibliography, generated values
└── comment/                # regulatory comment source, attachments, final PDF
```

Files that do not serve a scientific, computational, documentation, publication or regulatory function are not created. In particular, repositories contain no development logs, progress records, session notes, change narratives beyond conventional `git` history and a `CHANGELOG.md` limited to released versions, task lists, or files describing how the repository was produced.

Continuous integration (GitHub Actions) runs linting (`ruff`), type checking (`mypy --strict` on `src/`), the test suite, `make quick`, and the reference checker on every push.

# 3. Deliverable Architecture

## 3.1 Repository

The project is implemented as one self-contained repository, `reap-reporting-schema`, with importable Python package `reapschema`, organized as in Section 2.10 and with the modules listed in Section 1.D. It has no code dependency on any other repository and can be archived, cited and reproduced alone.

## 3.2 Publication package

Each project produces, inside its repository:

- `paper/manuscript.tex`, `paper/manuscript.pdf`, `paper/manuscript.docx` — the preprint.
- `paper/si.tex`, `paper/si.pdf` — supporting information (extended methods, verification results, convergence studies, full parameter tables, additional figures).
- `paper/figures/` — final vector figures as used in the manuscript.
- `comment/comment.docx`, `comment/comment.pdf` — the formal regulatory comment.
- `comment/attachment_technical.pdf` — the technical attachment (condensed methods, results and figures, written for agency technical staff).
- A tagged release (`v1.0.0`) archived to Zenodo when made public, producing a DOI that is then (and only then) cited in the comment and manuscript.
