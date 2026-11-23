"""PV model verification against an independent PVWatts v8 run on identical weather."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pvlib
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from reapschema.data.fetch import RAW
from reapschema.synth.pv import pvwatts_ac

REFERENCE = RAW / "pvwatts" / "pvwatts_v8_reference.json"
ANNUAL_TOLERANCE = 0.03
MONTHLY_TOLERANCE = 0.06


def reference_inputs():
    data = json.loads(REFERENCE.read_text())
    out, inp, info = data["outputs"], data["inputs"], data["station_info"]
    index = pd.date_range("2019-01-01 00:30", periods=8760, freq="h",
                          tz=f"Etc/GMT{-int(info['tz']):+d}")
    solpos = pvlib.solarposition.get_solarposition(index, float(inp["lat"]), float(inp["lon"]))
    zenith = solpos["apparent_zenith"].to_numpy()
    dn, df = np.asarray(out["dn"], float), np.asarray(out["df"], float)
    kwargs = dict(
        ghi=dn * np.maximum(np.cos(np.radians(zenith)), 0) + df, dni=dn, dhi=df,
        temp_air=np.asarray(out["tamb"], float), wind=np.asarray(out["wspd"], float),
        zenith=zenith, azimuth=solpos["azimuth"].to_numpy(),
        dni_extra=pvlib.irradiance.get_extra_radiation(index).to_numpy(),
        capacity_kw=float(inp["system_capacity"]), tilt=float(inp["tilt"]),
        surface_azimuth=float(inp["azimuth"]), dc_ac_ratio=1.2, inverter_efficiency=0.96,
        system_losses=float(inp["losses"]) / 100.0, temperature_coefficient=-0.0037,
    )
    return kwargs, np.asarray(out["ac"], float) / 1000.0, index


def test_matches_pvwatts_reference_within_tolerance():
    kwargs, reference, index = reference_inputs()
    ours = pvwatts_ac(**kwargs)
    assert ours.sum() == pytest.approx(reference.sum(), rel=ANNUAL_TOLERANCE)
    assert np.corrcoef(ours, reference)[0, 1] > 0.995
    monthly = pd.Series(ours, index=index).groupby(index.month).sum().to_numpy()
    ref_monthly = pd.Series(reference, index=index).groupby(index.month).sum().to_numpy()
    assert np.max(np.abs(monthly / ref_monthly - 1)) < MONTHLY_TOLERANCE


@settings(max_examples=15, deadline=None)
@given(capacity=st.floats(1.0, 500.0), tilt=st.floats(0.0, 60.0),
       azimuth=st.floats(90.0, 270.0))
def test_output_is_nonnegative_bounded_and_linear_in_capacity(capacity, tilt, azimuth):
    kwargs, _, _ = reference_inputs()
    kwargs.update(tilt=tilt, surface_azimuth=azimuth)
    kwargs["capacity_kw"] = capacity
    a = pvwatts_ac(**kwargs)
    kwargs["capacity_kw"] = 2 * capacity
    b = pvwatts_ac(**kwargs)
    assert np.all(a >= 0)
    assert a.max() <= capacity / 1.2 + 1e-9  # clipped at the inverter rating
    assert b.sum() == pytest.approx(2 * a.sum(), rel=1e-9)
