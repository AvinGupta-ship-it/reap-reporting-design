"""Unit handling at input boundaries.

Quantities entering the library are parsed with ``pint`` from the UCUM codes used
by the schema and converted to the internal units (kWh for energy, kW for power).
Numerical kernels operate on plain arrays in those units.
"""

from __future__ import annotations

import pint

ureg: pint.UnitRegistry = pint.UnitRegistry()

# UCUM code -> pint unit expression
_ENERGY_UNITS = {
    "kW.h": "kilowatt_hour",
    "MW.h": "megawatt_hour",
    "[Btu_IT]": "Btu",
    "k[Btu_IT]": "kiloBtu",
    "M[Btu_IT]": "megaBtu",
    "[therm_us]": "thm",
}
_POWER_UNITS = {"kW": "kilowatt", "MW": "megawatt"}

ureg.define("kiloBtu = 1000 * Btu")
ureg.define("megaBtu = 1000000 * Btu")

BTU_PER_KWH: float = float((1.0 * ureg.kilowatt_hour).to("Btu").magnitude)


def energy_to_kwh(value: float, ucum_code: str) -> float:
    """Convert an energy value with a UCUM unit code to kWh."""
    if ucum_code not in _ENERGY_UNITS:
        raise ValueError(f"unsupported energy unit: {ucum_code!r}")
    return float((value * ureg(_ENERGY_UNITS[ucum_code])).to("kilowatt_hour").magnitude)


def power_to_kw(value: float, ucum_code: str) -> float:
    """Convert a power value with a UCUM unit code to kW."""
    if ucum_code not in _POWER_UNITS:
        raise ValueError(f"unsupported power unit: {ucum_code!r}")
    return float((value * ureg(_POWER_UNITS[ucum_code])).to("kilowatt").magnitude)


def kwh_to_btu(value: float) -> float:
    return value * BTU_PER_KWH


def fahrenheit_to_celsius(value: float) -> float:
    return float(ureg.Quantity(value, ureg.degF).to("degC").magnitude)
