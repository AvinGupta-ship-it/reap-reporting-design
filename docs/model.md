# Mathematical specification

Units: energy in kWh, power in kW, temperature in °C (degree days in °F·day, following
the billing-analysis convention), time in days or hours, money in U.S. dollars.
Quantities entering through the schema carry UCUM unit codes and are converted with
`reapschema.units`.

## 1. Synthetic applicant

For applicant *n* with facility type *f*, State *s*, in-service day *D*:

**Load.** With end uses *e* (base profiles *b_e* indexed by month *m*, day type *d* and
hour *h*) and temperature responses *r* (coefficients *c_r*, balance points *T_r*),

    ℓ(t) = Σ_e o_e(t)·b_e(m,d,h) + Σ_r c_r(d,h)·[±(T_site(t) − T_r)]⁺·1{m ∈ M_r}
    L_cf(t) = A · ℓ(t) · ε_day(t) · ε_hour(t)

where *o_e(t)* is 1 or, after a non-routine change, a constant factor applied to the base
end uses; ε_day is a lognormal AR(1) daily factor and ε_hour an independent lognormal
hourly factor, both with unit mean; *A* scales the 365 days before *D* to the sampled
annual consumption. For commercial types, *b_e* and *c_r* come from ComStock State
aggregates (cooling and heating responses are least-squares fits of the HVAC end uses
to `max(T − T_c, 0)` and `max(T_h − T, 0)` by day type and hour, with the balance point
chosen on a 1 °C grid); each facility draws a lognormal factor on *c_r* and a normal
shift of *T_r*.

**Efficiency measure (EEI).** A measure reduces a set of end uses *E* by a fraction ρ
from day *D*:  `L(t) = L_cf(t) − 1{t ≥ D}·A·ρ·Σ_{e∈E} ℓ_e(t)·ε(t)`.

**Photovoltaic system (RES).** Hourly AC energy *P(t)* from the PVWatts formulation in
pvlib: Hay–Davies transposition, physical incidence-angle modifier on the beam
component, SAPM open-rack cell temperature, `pvwatts_dc`, system losses, PVWatts
inverter with the configured DC/AC ratio. A system-specific factor (lognormal derate ×
shading loss × irradiance bias) multiplies the output. Delivered and exported energy are
`[L − P]⁺` and `[P − L]⁺`.

**Billing.** Scheduled reads every 30.4375 days with independent integer jitter. A bill
is the difference of register reads; with probability *p_e* a read is estimated as the
previous read plus the prior period's daily average times the days (with noise, and not
beyond the next actual register), and the next actual read restores the true register.
Under conventional net metering the printed quantity is delivered minus exported energy;
otherwise delivered energy. The pre-installation set is the last twelve bills ending
before *D*; the post-installation set is the first twelve bills starting on or after *D*.

**Ground truth.** Production `P* = Σ_{t∈[D,D+365)} P(t)`; pre-installation use
`C* = Σ_{t∈[D−365,D)} L(t)`; avoided energy use `S_avoid = Σ_{t∈[D,D+365)} (L_cf − L)`;
normal-year savings *S** and production: the mean annual value of the noise-free model
over the 2005–2015 weather record. The verification target is *P** for RES and *S** for
EEI.

**Errors.** One of six classes is injected with scenario probabilities: unit (factor
10⁻³ or 10³), transposed adjacent digits in one typed value, wrong period (bills of the
preceding year, or a set straddling *D*), double counting (a second meter added to
pre-installation bills), gross/net confusion (exports or bill reduction reported as
production; RES), nameplate × peak sun hours reported as production (RES).

## 2. Estimators

**Billing models.** For periods *m* with days *d_m* and degree days on the bill's dates,

    E_m = β₀ d_m + β_H HDD_m(T_H) + β_C CDD_m(T_C) + ε_m,

fitted by weighted least squares on average daily use with weights *d_m*, over a grid of
balance points (30–90 °F, 3 °F steps), over the intercept-only, heating-only,
cooling-only and combined forms. Candidates with a non-positive degree-day coefficient
or fewer than three periods with non-zero degree days are rejected; the highest adjusted
R² is selected. CV(RMSE) and net determination bias are reported.

- Undated difference: `Σ pre − Σ post` (the calculation in the rule's definition of
  Simple Payback).
- Dated difference: `365·(Σ pre / Σ d_pre − Σ post / Σ d_post)`.
- Avoided energy use: `Σ_post (Ê_m^base − E_m)`.
- Normalized annual savings: baseline model minus reporting-period model, both evaluated
  with mean annual degree days of the 2005–2015 station record (used in place of a
  typical-meteorological-year file). Normalization is applied only when both models have
  CV(RMSE) at or below the configured limit; otherwise the dated difference is retained
  ("guarded" estimator).
- With read type: an estimated read is merged with the following period before fitting.
- Interval data: the same model on daily energy with a weekday/weekend term.

**Uncertainty.** Fractional savings uncertainty
`U = t·1.26·CV·[(n/n′)(1 + 2/n′)/m]^{1/2}/F`, `n′ = n(1−ρ)/(1+ρ)`, with ρ the lag-1
autocorrelation of baseline residuals, *F* the savings fraction and *t* the Student
quantile with *n − p* degrees of freedom; and a residual moving-block bootstrap.

**RES.** Verified production is the claim, the sum of monthly production-meter readings
or the interval total, depending on the specification. Normalized production is
`P̂·Y_normal/Y_actual` with *Y* the modeled yield. Plausibility statistic:
`z = ln(P̂/P̂_model)/σ`, with σ a robust scale of the log ratio on error-free submissions.

## 3. Validation rules

Rules, the elements they need and their type are listed in
`reapschema.validate.RULES`. Deterministic rules flag a submission when a condition
fails. Statistical rules flag when a score exceeds its (1 − α) quantile on error-free
submissions, α being the configured false-positive rate. A diagnostic rule (baseline
model fit) is reported but does not flag. Under a specification **x** the active rules
are those whose required elements are in **x**. A flagged erroneous submission is
corrected on resubmission; a flagged error-free submission costs rework time.

## 4. Burden

Element times τ are triangular. For specification **x** and mode *q*,

    B(x, q) = κ·[ Σ_c w_c ( b_c(q) + Σ_j τ_{jc}(q) x_j ) + φ(x)·τ_rework ],

with *w_c* the RES/EEI mix, *b_c* the time for required evidence, φ the flag rate and κ
the factor that sets *B(∅, manual)* (without rework) to `anchor_responses × 1.34 h`.
In file-based modes the billing-history file replaces locating and transcribing bills
and supplies dates, read type, charges, identifiers, post-installation bills and
exports at no additional time.

## 5. Optimization

Decision **x** ∈ {0,1}^13 with dependencies (weather normalization needs billing dates
or interval data; the export channel needs post-installation bills). Loss (i) is the
mean of `min(|V − target|/|target|, 1)` over applicants; loss (ii) is the mean share of
applications selected on true values that are not selected on verified values. All
feasible specifications are enumerated. As a check of the method intended for larger
element sets, a quadratic pseudo-Boolean surrogate is fitted to a sample of
specifications and `min L̂(x) s.t. τᵀx ≤ B` is solved as a mixed-integer program
(products linearized) with HiGHS at a relative gap of 10⁻⁴; the returned specification
is checked for feasibility and evaluated by direct simulation.

## 6. Competition

Energy-dependent points (§4280.140(d)(2), (3), (6)) use
`min(round(3412.14·kWh / request / 100, 2), 25)`, the percentage tables after rounding
to one decimal place, and the payback tables. The payback tables do not assign the
intervals (7, 8) and (14, 15) years; the lower bound of each band is used as the cut
point, so those intervals take the points of the band below them. Eligibility requires
payback not longer than useful life and, for systems with storage, production not above
120% of pre-installation use. Other criteria are sampled from hypothetical
distributions and are identical under true and verified values. Selection: applications
of at most $20,000 are funded from a reserve in rank order; the rest compete generally,
with the top applications per State funded first and then all in rank order, stopping
at the first application that does not fit; minimum score 40. The rule does not state
how ties are broken or whether an application that exceeds remaining funds is skipped;
a fixed random key breaks ties.
