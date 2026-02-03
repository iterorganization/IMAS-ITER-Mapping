import numpy as np
import pytest

from imas_iter_mapping import (
    UNIT_REGISTRY,
    ChannelSignal,
    UnitConversion,
    get_unit_conversion_arrays,
)

Q = UNIT_REGISTRY.Quantity
U = UNIT_REGISTRY.Unit


def test_unit_conversions():
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


def test_unit_conversion_arrays():
    signals = [
        ChannelSignal("N/A", "N/A", Q("m"), U("m")),
        ChannelSignal("N/A", "N/A", Q("mm"), U("m")),
        ChannelSignal("N/A", "N/A", Q("1e2 mm"), U("m")),
        ChannelSignal("N/A", "N/A", Q("mV.s"), U("Wb")),
        ChannelSignal("N/A", "N/A", Q("degC"), U("K")),
        ChannelSignal("N/A", "N/A", Q("degF"), U("K")),
    ]

    scale, offset = get_unit_conversion_arrays(signals)
    assert isinstance(scale, np.ndarray)
    assert isinstance(offset, np.ndarray)
    assert np.allclose(scale, [1, 1e-3, 0.1, 1e-3, 1, 5 / 9], rtol=1e-10)
    assert np.allclose(offset, [0, 0, 0, 0, 273.15, 255.37222222222222], rtol=1e-10)
