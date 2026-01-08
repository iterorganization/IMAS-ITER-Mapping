from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Any, Self

import imas
import numpy as np
import pint
import strictyaml
from imas.ids_data_type import IDSDataType
from imas.ids_metadata import IDSMetadata
from pydantic import (
    BaseModel,
    ConfigDict,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from imas_iter_mapping.units import UNIT_REGISTRY, UnitConversion
from imas_iter_mapping.util import load_machine_description_ids


@contextmanager
def _as_value_error(err_msg) -> Iterator[None]:
    """Helper context manager to raise a ValueError from any exception.

    Pydantic validators are required to raise a ValueError (or AssertionError or
    PydanticCustomError) when data is not valid. See:
    https://docs.pydantic.dev/latest/concepts/validators/#raising-validation-errors
    """
    try:
        yield
    except Exception as exc:
        raise ValueError(f"{err_msg} ({exc})") from exc


def _raise_if_duplicate(values: Iterable, error_message: str) -> None:
    """Helper function to raise a ValueError if duplicates are found."""
    unique_elements, counts = np.unique(list(values), return_counts=True)
    duplicates = unique_elements[counts > 1]
    if len(duplicates) > 0:
        duplicate_str = ", ".join(duplicates)
        raise ValueError(error_message.format(duplicate_str))


class ChannelSignal(BaseModel):
    path: str
    """Path inside the IDS channel. For example, "flux/value" of a flux_loop channel in
    the magnetics IDS."""
    signal: str
    """Signal name in the data source."""
    source_units: pint.Quantity
    """Optional unit of the source signal."""
    dd_units: pint.Unit | None = None  # N.B. will be None until validation completes
    """Target unit following the IMAS Data Dictionary."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @model_validator(mode="before")
    @classmethod
    def parse_signal_expression(cls, data: Any) -> Self:
        """Parse optional units when reading a mapping file."""
        if not isinstance(data, dict):
            raise ValueError("Expecting a dictionary")
        signal, bracket, unit_with_bracket = data["signal"].partition("[")
        if bracket:
            if not unit_with_bracket.endswith("]"):
                raise ValueError(f"Was expecting a closing ']' in '{data['signal']}'")
            unit_str = unit_with_bracket.removesuffix("]")
            try:
                unit = UNIT_REGISTRY.Quantity(unit_str)
            except pint.UndefinedUnitError as exc:
                raise ValueError(f"Error parsing unit [{unit_str}]: {exc}") from None
        else:
            raise ValueError(f"Missing unit in mapping for signal '{signal}'")
        data["signal"] = signal.strip()
        data["source_units"] = unit
        return data

    def get_unit_conversion(self) -> UnitConversion:
        """Get the linear coefficients for converting from source to DD units."""
        assert self.dd_units is not None
        return UnitConversion.calculate(self.source_units, self.dd_units)

    @model_serializer(mode="plain")
    def serialize_model(self) -> dict:
        """Serialize back into mapping format."""
        return {"path": self.path, "signal": f"{self.signal} [{self.source_units}]"}

    def validate_imas_paths_and_units(self, idsmeta: IDSMetadata) -> None:
        """Check that the IMAS path exist and its units are compatible."""
        with _as_value_error("Unknown IDS path"):
            meta = idsmeta[self.path]
        self.dd_units = UNIT_REGISTRY.Unit(meta.units)
        if not self.source_units.check(self.dd_units):
            raise ValueError(
                f"Unit [{self.source_units}] is incompatible with the IMAS "
                f"Data Dictionary units [{meta.units}]"
            )
        # TODO: check that this is mapped to a dynamic FLT 0D/1D signal


class ChannelMap(BaseModel):
    """Configures signal mapping for a single channel in an IDS."""

    name: str
    """Name of the channel: used to match against Machine Description data."""
    signals: list[ChannelSignal]
    """List of signals within this channel."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def parse_yaml(cls, data: Any) -> Any:
        """Parse yaml dictionary to the internal representation."""
        if not isinstance(data, dict):
            raise ValueError("Expecting a dictionary")
        if "name" not in data:
            raise ValueError("Missing channel name")
        return {
            "name": data["name"],
            "signals": [
                {"path": key, "signal": value}
                for key, value in data.items()
                if key != "name"
            ],
        }

    @model_serializer(mode="wrap")
    def serialize_model(self, handler: SerializerFunctionWrapHandler) -> dict:
        """Serialize back into the mapping format."""
        serialized = handler(self)
        signals = serialized.pop("signals")
        for signal in signals:
            serialized[signal["path"]] = signal["signal"]
        return serialized

    def validate_imas_paths_and_units(self, idsmeta: IDSMetadata) -> None:
        """Check per signal that the IMAS path exist and its units are compatible."""
        for signal in self.signals:
            signal.validate_imas_paths_and_units(idsmeta)


class SignalMap(BaseModel):
    """Map of CODAC signals to the IMAS Data Dictionary."""

    description: str
    """Free-format description of the mapping file."""
    data_dictionary_version: str
    """Version of the Data Dictionary that the mapping is validated for."""
    machine_description_uri: str
    """(IMAS) URI of a dataset containing machine description data."""
    target_ids: str
    """IDS name that all signals map to."""
    signals: dict[str, list[ChannelMap]]
    """List of channel maps per IDS path"""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_imas_metadata(self) -> Self:
        """Validator for the IMAS metadata: DD version and IDS paths."""
        # Will raise a ValueError if the data dictionary version is unknown/incorrect:
        factory = imas.IDSFactory(self.data_dictionary_version)
        if self.data_dictionary_version.startswith("3."):
            raise ValueError("Data Dictionary 3.x is not supported.")
        # Will raise a ValueError if self.target_ids is not a valid IDS:
        idsmeta = factory.new(self.target_ids).metadata
        # Validate channel AoS
        for ids_path, items in self.signals.items():
            with _as_value_error("Unknown IDS path"):
                aosmeta = idsmeta[ids_path]
            if aosmeta.data_type is not IDSDataType.STRUCT_ARRAY:
                raise ValueError(f"{ids_path} is not an array of structures")
            for channelmap in items:
                channelmap.validate_imas_paths_and_units(aosmeta)
        return self

    @model_validator(mode="after")
    def validate_unique_dan_channels(self) -> Self:
        """Validator for the DAN channel names.

        The DAN channel names should be globally unique.
        """
        all_signal_names = []
        for signal in self.signals.values():
            for channelmap in signal:
                all_signal_names.extend(s.signal for s in channelmap.signals)
        _raise_if_duplicate(
            all_signal_names, "Duplicate signal name in channel mapping: {}."
        )
        return self

    @model_validator(mode="after")
    def validate_unique_imas_channels(self) -> Self:
        """Validator for the IMAS channel names.

        The IMAS channel names should be globally unique.
        """
        all_imas_channel_names = []
        for signal in self.signals.values():
            all_imas_channel_names.extend(channelmap.name for channelmap in signal)
        _raise_if_duplicate(
            all_imas_channel_names, "Duplicate IMAS name in channel mapping: {}."
        )
        return self

    @model_validator(mode="after")
    def validate_machine_description(self) -> Self:
        """Validator for the Machine Description data."""
        # Try to load Machine Description IDS
        with _as_value_error("Could not load Machine Description"):
            ids = load_machine_description_ids(
                self.machine_description_uri,
                self.data_dictionary_version,
                self.target_ids,
            )
        # Check if all names are present in the Machine Description
        for path, channels in self.signals.items():
            all_names = {str(channel.name) for channel in ids[path]}
            for channel in channels:
                if channel.name not in all_names:
                    raise ValueError(
                        f"Channel name {channel.name} not found in Machine Description"
                    )
        return self

    @classmethod
    def from_yaml(cls, yaml_string) -> "SignalMap":
        """Create a Signal Map from the provided yaml string."""
        parsed_yaml = strictyaml.load(yaml_string)
        yaml_dict = parsed_yaml.as_marked_up()
        # TODO: proper error message when yaml_dict is not an actual dictionary (list,
        # str, etc.)
        return cls(**yaml_dict)

    def to_yaml(self) -> str:
        """Convert the Signal Map into the yaml format."""
        dct = self.model_dump()
        yaml = strictyaml.as_document(dct)
        return yaml.as_yaml()
