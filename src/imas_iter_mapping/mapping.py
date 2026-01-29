from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Self, TextIO

import imas
import pint
import strictyaml
from imas.ids_metadata import IDSMetadata
from strictyaml import Map, MapCombined, MapPattern, Seq, Str
from strictyaml.representation import YAML

from imas_iter_mapping.units import UNIT_REGISTRY, UnitConversion
from imas_iter_mapping.util import load_machine_description_ids

SCHEMA = Map(
    {
        "description": Str(),
        "data_dictionary_version": Str(),
        "machine_description_uri": Str(),
        "target_ids": Str(),
        "signals": MapPattern(
            Str(),
            Seq(
                MapCombined(
                    {"name": Str()},  # name is a required key
                    Str(),  # Allow any IDS path as valid key
                    Str(),  # Signal expression as value
                )
            ),
        ),
    }
)
"""StrictYAML schema for IMAS ITER Mapping"""


class ValidationError(ValueError):
    """Custom error class that keeps of the position in the yaml document"""

    def __init__(self, msg: str, yaml_path: tuple) -> None:
        """Create a new ValidationError

        Args:
            msg: Error message
            yaml_path: Path inside the parsed yaml document, for example:
                ``("signals", "flux_loop", 1)``
        """
        super().__init__(msg)
        self.yaml_path = yaml_path
        self._full_message = [f"ValidationError: {msg}"]

    def set_yaml_and_label(self, yaml: YAML, label: str) -> None:
        """Enrich the error message by providing the parsed yaml and filename label"""
        # Traverse YAML path to find the problematic YAML item
        for item in self.yaml_path:
            yaml = yaml[item]
        # Extract line number and text on that line
        startline = yaml.start_line
        lines = yaml.lines()
        if lines:
            line = lines.splitlines()[0]
        else:  # This happens for string values inside lowlevel Channel Mappings :/
            startline -= 1
            line = yaml.lines_before(1)
        # And add to the error message text
        self._full_message.append(f'  in "{label}", line {yaml.start_line}:')
        self._full_message.append(f"    {line}")

    def __str__(self) -> str:
        return "\n".join(self._full_message)


@contextmanager
def _as_validation_error(yaml_path: tuple, msg: str = "") -> Iterator[None]:
    """Helper context manager to raise a ValidationError from any exception."""
    try:
        yield
    except Exception as exc:
        msg = str(exc) if not msg else f"{msg}: {exc}"
        raise ValidationError(msg, yaml_path) from exc


@dataclass
class SignalMap:
    """Map of CODAC signals to the IMAS Data Dictionary."""

    description: str
    """Free-format description of the mapping file."""
    data_dictionary_version: str
    """Version of the Data Dictionary that the mapping applies to."""
    machine_description_uri: str
    """(IMAS) URI of a dataset containing machine description data."""
    target_ids: str
    """IDS name that all signals map to."""
    signals: dict[str, list["ChannelMap"]]

    @classmethod
    def from_yaml(cls, yaml: str | TextIO) -> Self:
        """Create a Signal Map from the provided yaml string."""
        if isinstance(yaml, str):
            yaml_string, label = yaml, "<unicode string>"
        else:
            yaml_string, label = yaml.read(), yaml.name
        parsed_yaml = strictyaml.load(yaml_string, schema=SCHEMA, label=label)
        try:
            return cls(**parsed_yaml.data)
        except ValidationError as exc:
            exc.set_yaml_and_label(parsed_yaml, label)
            raise exc

    def __post_init__(self):
        """Transform signals from YAML format and validate data"""
        # Data dictionary validation
        if self.data_dictionary_version.startswith("3."):
            raise ValidationError(
                "Data Dictionary 3.x is not supported.", ("data_dictionary_version",)
            )
        with _as_validation_error(("data_dictionary_version",)):
            # Will raise a ValueError when DD version is unknown:
            factory = imas.IDSFactory(self.data_dictionary_version)

        # Check that the IDS name is valid
        with _as_validation_error(("target_ids",)):
            # Will raise a ValueError when IDS name does not exist
            factory.new(self.target_ids)
        # Load Machine Description
        with _as_validation_error(("machine_description_uri",)):
            self._machine_description = load_machine_description_ids(
                self.machine_description_uri,
                self.data_dictionary_version,
                self.target_ids,
            )

        # Parse signals
        signalnames = []  # To detect duplicate signal names
        for ids_path, channels in self.signals.items():
            yaml_path = ("signals", ids_path)
            # Check that the ids_path is valid
            with _as_validation_error(yaml_path, "Unknown or invalid IDS path"):
                aosmeta = self._machine_description[ids_path].metadata
            # Check if channels are already channelmaps, and create otherwise:
            channels = [
                channel
                if isinstance(channel, ChannelMap)
                else ChannelMap._from_yaml(channel, yaml_path + (i,), aosmeta)
                for i, channel in enumerate(channels)
            ]
            self.signals[ids_path] = channels
            self._validate_channels(ids_path, signalnames, yaml_path)

    def _validate_channels(
        self, ids_path: str, signalnames: list[str], yaml_path: tuple
    ) -> None:
        """Validation rules for channels"""
        # Available channel names in the machine description
        md_channelnames = [
            str(channel.name) for channel in self._machine_description[ids_path]
        ]
        # Names of channels already processed (to detect duplicates)
        channelnames = []

        for i, ch in enumerate(self.signals[ids_path]):
            # Check that channel name exists in the Machine Description
            if ch.name not in md_channelnames:
                raise ValidationError(
                    f"Channel {ch.name} not found in the Machine Description",
                    yaml_path + (i, "name"),
                )
            # Check for duplicate IMAS channel names
            if ch.name in channelnames:
                raise ValidationError(
                    f"Duplicate channel name {ch.name}",
                    yaml_path + (i, "name"),
                )
            channelnames.append(ch.name)
            # Check for duplicate signal names
            for signal in ch.signals:
                if signal.signal in signalnames:
                    raise ValidationError(
                        f"Duplicate signal name {signal.signal}",
                        yaml_path + (i, signal.path),
                    )
                signalnames.append(signal.signal)


@dataclass
class ChannelMap:
    """Configures signal mapping for a single channel in an IDS."""

    name: str
    """Name of the channel: used to match against Machine Description data."""
    signals: list["ChannelSignal"]
    """List of signals within this channel."""

    @classmethod
    def _from_yaml(
        cls, data: dict[str, str], yaml_path: tuple, aosmeta: IDSMetadata
    ) -> Self:
        name = data.pop("name")
        signals = [
            ChannelSignal._from_yaml(path, signal, yaml_path + (path,), aosmeta)
            for path, signal in data.items()
        ]
        return cls(name, signals)


@dataclass
class ChannelSignal:
    """Mapping details for a single CODAC signal"""

    path: str
    """Path inside the IDS channel. For example, "flux/value" of a flux_loop channel in
    the magnetics IDS."""
    signal: str
    """Signal name in the data source."""
    source_units: pint.Quantity
    """Units of the source signal."""
    dd_units: pint.Unit
    """Target units following the IMAS Data Dictionary."""

    @classmethod
    def _from_yaml(
        cls, path: str, signal: str, yaml_path: tuple, aosmeta: IDSMetadata
    ) -> Self:
        with _as_validation_error(yaml_path, "Unknown IDS path"):
            metadata = aosmeta[path]
        dd_units = UNIT_REGISTRY.Unit(metadata.units)

        # Parse signal expression
        signal, bracket, unit_with_bracket = signal.partition("[")
        if not bracket:
            raise ValidationError("Missing unit in signal mapping", yaml_path)
        if not unit_with_bracket.endswith("]"):
            raise ValidationError("Was expecting a closing ']'", yaml_path)
        unit_str = unit_with_bracket.removesuffix("]")
        with _as_validation_error(yaml_path, f"Invalid unit [{unit_str}]"):
            source_units = UNIT_REGISTRY.Quantity(unit_str)

        # Check compatibility of units
        if not source_units.check(dd_units):
            raise ValidationError(
                f"Unit [{unit_str}] is incompatible with the IMAS "
                f"Data Dictionary units [{metadata.units}]",
                yaml_path,
            )

        return cls(path, signal.strip(), source_units, dd_units)

    def get_unit_conversion(self) -> UnitConversion:
        """Get the linear coefficients for converting from source to DD units."""
        return UnitConversion.calculate(self.source_units, self.dd_units)
