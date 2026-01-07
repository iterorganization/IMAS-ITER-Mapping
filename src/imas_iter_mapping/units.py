from typing import NamedTuple, Self

import pint

UNIT_REGISTRY = pint.UnitRegistry()


class UnitConversion(NamedTuple):
    """Conversion factors when going from CODAC units to DD units.

    This assumes units can be converted as a simple linear transformation::

        qty_in_dd_units = qty_in_codac_units * scale + offset

    This is true for most units available in the default ``pint``, except for
    logarithmic units.
    """

    scale: float
    offset: float

    @classmethod
    def calculate(cls, source: pint.Quantity, target: pint.Unit) -> Self:
        """Calculate the required unit conversion."""
        zero = UNIT_REGISTRY.Quantity(0, source.units)
        offset = zero.to(target).magnitude
        scale = source.to(target).magnitude - offset
        return cls(float(scale), float(offset))
