import logging
import os
import sys
from typing import TextIO

import click
from strictyaml.ruamel.error import YAMLError

from imas_iter_mapping import SignalMap, ValidationError


@click.group(invoke_without_command=True, no_args_is_help=True)
def main() -> None:
    # Suppress IMAS-Python INFO messages by default
    if "IMAS_LOGLEVEL" not in os.environ:
        logging.getLogger("imas").setLevel(logging.WARNING)


@main.command("validate")
@click.argument("mapping_file", type=click.File())
@click.option("-q", "--quiet", is_flag=True, help="Silence some output")
def validate(mapping_file: TextIO, quiet: bool) -> None:
    """Validate a data mapping YAML file."""
    if not quiet:
        click.echo(f'Validating "{mapping_file.name}" ...')
    try:
        SignalMap.from_yaml(mapping_file)
    except YAMLError as exc:
        # YAML or StrictYAML error
        click.echo("File contains invalid (strict) YAML:")
        click.echo(exc)
        sys.exit(2)
    except ValidationError as exc:
        # Validation error
        click.echo(exc)
        sys.exit(3)

    if not quiet:
        click.echo(f"Success: {mapping_file.name} is a valid IMAS ITER Mapping file")
