"""Utility billing: read cycles, estimated reads and netting of exports."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from reapschema.config import BillingConfig


@dataclass(frozen=True)
class Bills:
    """Billing-period records of one service point.

    ``start`` and ``end`` are inclusive day indices. ``delivered`` and ``export``
    are register differences in kWh; ``basis`` states whether the quantity printed
    on the bill (``printed``) is delivered energy or delivered minus exported.
    ``n_accounts`` is the number of utility accounts combined in each record.
    """

    start: np.ndarray
    end: np.ndarray
    delivered: np.ndarray
    export: np.ndarray
    estimated: np.ndarray
    demand: np.ndarray
    charge: np.ndarray
    n_accounts: np.ndarray
    basis: str = "delivered_only"

    @property
    def days(self) -> np.ndarray:
        return np.asarray(self.end - self.start + 1)

    @property
    def printed(self) -> np.ndarray:
        if self.basis == "net_of_exports":
            return np.asarray(self.delivered - self.export)
        return np.asarray(self.delivered)

    def __len__(self) -> int:
        return int(self.start.size)

    def take(self, idx: np.ndarray | slice) -> Bills:
        return replace(
            self, start=self.start[idx], end=self.end[idx], delivered=self.delivered[idx],
            export=self.export[idx], estimated=self.estimated[idx], demand=self.demand[idx],
            charge=self.charge[idx], n_accounts=self.n_accounts[idx],
        )


def read_days(rng: np.random.Generator, first_day: int, last_day: int,
              cycle_mean_days: float, jitter_days: int) -> np.ndarray:
    """Meter-read day indices: a read on day ``r`` closes the period ending on ``r - 1``.

    Reads follow a regular schedule with independent jitter, so the length of a
    single period varies by a few days while twelve periods span close to a year.
    """
    offset = float(rng.uniform(jitter_days, jitter_days + cycle_mean_days))
    n = int((last_day + 1 - first_day - offset - jitter_days) // cycle_mean_days) + 1
    schedule = first_day + offset + cycle_mean_days * np.arange(n)
    jitter = rng.integers(-jitter_days, jitter_days + 1, n) if jitter_days > 0 else 0
    reads = np.round(schedule).astype(int) + jitter
    return np.asarray(reads[reads <= last_day + 1], dtype=int)


def make_bills(rng: np.random.Generator, daily_delivered: np.ndarray, daily_export: np.ndarray,
               daily_peak: np.ndarray, first_day: int, reads: np.ndarray, cfg: BillingConfig,
               price: float, basis: str, estimated_prob: float | None = None) -> Bills:
    """Aggregate daily energy into bills, with estimated reads trued up at the next read.

    ``daily_*`` arrays start at day index ``first_day``. An estimated read replaces
    the register reading by the previous reading plus the prior period's average
    daily use times the number of days (with noise); the following actual read
    restores the true register, so energy is conserved across the two periods.
    """
    p_est = cfg.estimated_read_prob if estimated_prob is None else estimated_prob
    offset = reads - first_day
    cum_d = np.concatenate([[0.0], np.cumsum(daily_delivered)])
    cum_e = np.concatenate([[0.0], np.cumsum(daily_export)])
    true_d = cum_d[offset]
    true_e = cum_e[offset]
    n = reads.size - 1
    reg_d = true_d.copy()
    reg_e = true_e.copy()
    est_read = np.zeros(reads.size, dtype=bool)
    for i in range(2, reads.size - 1):
        if not est_read[i - 1] and rng.random() < p_est:
            est_read[i] = True
            days_prev = reads[i - 1] - reads[i - 2]
            days_cur = reads[i] - reads[i - 1]
            noise = 1.0 + rng.normal(0.0, cfg.estimate_noise_sd)
            use_prev = reg_d[i - 1] - reg_d[i - 2]
            # an estimate cannot exceed the register at the next actual read
            reg_d[i] = min(reg_d[i - 1] + max(use_prev / days_prev * days_cur * noise, 0.0),
                           true_d[i + 1])
            exp_prev = reg_e[i - 1] - reg_e[i - 2]
            reg_e[i] = min(reg_e[i - 1] + max(exp_prev / days_prev * days_cur * noise, 0.0),
                           true_e[i + 1])
    delivered = np.diff(reg_d)
    export = np.diff(reg_e)
    demand = np.array([daily_peak[offset[i]:offset[i + 1]].max() for i in range(n)])
    charge = price * delivered * (1.0 + rng.normal(0.0, 0.03, n))
    return Bills(
        start=reads[:-1].copy(), end=reads[1:] - 1, delivered=delivered, export=export,
        estimated=est_read[1:], demand=demand, charge=np.maximum(charge, 0.0),
        n_accounts=np.ones(n, dtype=int), basis=basis,
    )


def select_periods(bills: Bills, in_service_day: int, n: int = 12
                   ) -> tuple[Bills, Bills, Bills]:
    """Pre-installation, post-installation and earlier-year sets of ``n`` bills.

    The pre-installation set is the last ``n`` bills ending before the in-service
    day; the post-installation set is the first ``n`` bills starting on or after
    it. The bill that straddles the in-service day belongs to neither.
    """
    pre_idx = np.flatnonzero(bills.end < in_service_day)
    post_idx = np.flatnonzero(bills.start >= in_service_day)
    if pre_idx.size < 2 * n or post_idx.size < n:
        raise ValueError("billing history too short around the in-service date")
    return (bills.take(pre_idx[-n:]), bills.take(post_idx[:n]),
            bills.take(pre_idx[-2 * n:-n]))
