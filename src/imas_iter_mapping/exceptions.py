from collections.abc import Iterator
from contextlib import contextmanager

from strictyaml.representation import YAML


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
        else:  # This happens for string values inside Channel Mappings :/
            startline -= 1
            line = yaml.lines_before(1)
        # And add to the error message text
        self._full_message.append(f'  in "{label}", line {startline}:')
        self._full_message.append(f"    {line}")

    def __str__(self) -> str:
        return "\n".join(self._full_message)


@contextmanager
def as_validation_error(yaml_path: tuple, msg: str = "") -> Iterator[None]:
    """Helper context manager to raise a ValidationError from any exception."""
    try:
        yield
    except Exception as exc:
        msg = str(exc) if not msg else f"{msg}: {exc}"
        raise ValidationError(msg, yaml_path) from exc
