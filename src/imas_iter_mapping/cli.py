import logging
import os
import sys
from typing import TextIO

import click
from imas.ids_struct_array import IDSStructArray
from strictyaml.ruamel.error import YAMLError

from imas_iter_mapping import SignalMap, ValidationError


@click.group(invoke_without_command=True, no_args_is_help=True)
def main() -> None:
    # Suppress IMAS-Python INFO messages by default
    if "IMAS_LOGLEVEL" not in os.environ:
        logging.getLogger("imas").setLevel(logging.WARNING)


def try_parse(mapping_file: TextIO) -> SignalMap:
    """Try to parse a mapping file, and display an error message if that fails."""
    try:
        return SignalMap.from_yaml(mapping_file)
    except YAMLError as exc:
        # YAML or StrictYAML error
        click.echo("File contains invalid (strict) YAML:")
        click.echo(exc)
        sys.exit(2)
    except ValidationError as exc:
        # Validation error
        click.echo(exc)
        sys.exit(3)


@main.command("validate")
@click.argument("mapping_file", type=click.File())
@click.option("-q", "--quiet", is_flag=True, help="Silence some output.")
def validate(mapping_file: TextIO, quiet: bool) -> None:
    """Validate a data mapping YAML file.

    \b
    Exit codes:
        0       The mapping file is valid.
        1       An internal error occurred, this is likely a bug.
        2       The mapping file is not valid YAML, or does not adhere to the expected
                data format (for example: missing mandatory items).
        3       The data in the mapping file is not valid.

    \b
    Arguments:
        MAPPING_FILE: Mapping file to validate (or '-' to read from stdin).
    """
    if not quiet:
        click.echo(f'Validating "{mapping_file.name}" ...')
    try_parse(mapping_file)
    if not quiet:
        click.echo(f"Success: {mapping_file.name} is a valid IMAS ITER Mapping file")


@main.command("describe")
@click.argument("mapping_file", type=click.File())
def describe(mapping_file: TextIO) -> None:
    """Display statistics about the mapping file and associated machine description"""
    map = try_parse(mapping_file)

    click.echo(
        f'IMAS-ITER-Mapping file "{mapping_file.name}" maps '
        f"{map.num_signals} signals to the {map.target_ids} IDS."
    )
    click.echo()

    # Print some statistics related to the Machine Description
    ids = map.machine_description
    # Find nonempty, toplevel, arrays of structures that have a name attribute:
    aos = [
        node
        for node in ids.iter_nonempty_()
        if isinstance(node, IDSStructArray) and hasattr(node[0], "name")
    ]
    click.echo(f"The Machine Description contains {len(aos)} channel types:")
    for node in aos:
        ids_path = node.metadata.name
        channels = map.signals.get(ids_path, [])
        click.echo(
            f"- '{ids_path}' has {len(node)} elements, of which "
            f"{len(channels)} ({len(channels) / len(node):.0%}) have mapped signals."
        )
        if len(channels) != 0:
            num_signals = sum(len(channel.signals) for channel in channels)
            avg_mapped = num_signals / len(channels)
            click.echo(
                f"  {num_signals} signals are mapped. That is, on average, "
                f"{avg_mapped:.3g} signals per element."
            )

            # unit conversions
            num_unit_conversions = sum(
                1
                for channel in channels
                for signal in channel.signals
                if signal.get_unit_conversion() != (1, 0)
            )
            click.echo(
                f"  {num_unit_conversions} signals "
                f"({num_unit_conversions / num_signals:.0%}) have a unit that "
                "differs from the IMAS Data Dictionary (but can be transformed)."
            )
