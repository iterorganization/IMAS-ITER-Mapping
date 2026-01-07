import pytest

from imas_iter_mapping import UNIT_REGISTRY, UnitConversion


def test_unit_conversions():
    Q = UNIT_REGISTRY.Quantity
    U = UNIT_REGISTRY.Unit

    # Source and target are identical
    conversion = UnitConversion.calculate(Q("m"), U("m"))
    assert conversion == (1, 0)

    # Source and target are with different SI prefixes
    conversion = UnitConversion.calculate(Q("mm"), U("m"))
    assert conversion == (1e-3, 0)

    # Numerical prefixes
    conversion = UnitConversion.calculate(Q("1e2 mm"), U("m"))
    assert conversion == (0.1, 0)

    # Compound units
    conversion = UnitConversion.calculate(Q("mV.s"), U("Wb"))
    assert conversion == (1e-3, 0)

    # Offsets for temperatures
    conversion = UnitConversion.calculate(Q("degC"), U("K"))
    assert conversion == (1, 273.15)

    conversion = UnitConversion.calculate(Q("degF"), U("K"))
    assert conversion == pytest.approx((5 / 9, 255.37222222222222), rel=1e-10)
