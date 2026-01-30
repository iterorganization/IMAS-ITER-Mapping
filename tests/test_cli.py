from pathlib import Path

import pytest
from click.testing import CliRunner

from imas_iter_mapping.cli import main


@pytest.fixture()
def mapping_file(iter_md_magnetics_path, tmp_path) -> Path:
    fname = tmp_path / "test.mapping.yaml"
    fname.write_text(f"""\
description: Test mapping
data_dictionary_version: 4.0.0
machine_description_uri: {iter_md_magnetics_path}
target_ids: magnetics
signals:
  flux_loop:
  - name: 55.AD.00-MSA-1001
    flux/data: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI0 [Wb]
""")
    return fname


def test_validate_success(mapping_file):
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(mapping_file)])
    assert result.exit_code == 0
    assert str(mapping_file) in result.output


def test_validate_yaml_error(mapping_file):
    mapping_file.write_text("asdf")
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(mapping_file)])
    assert result.exit_code == 2
    assert str(mapping_file) in result.output
    assert "line 1" in result.output


def test_validate_parsing_error(mapping_file):
    with open(mapping_file, "a") as f:
        f.write("  - name: xyz")
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(mapping_file)])
    assert result.exit_code == 3
    assert str(mapping_file) in result.output
    assert "line 9" in result.output


def test_validate_quiet(mapping_file):
    runner = CliRunner()
    result = runner.invoke(main, ["validate", "-q", str(mapping_file)])
    assert result.exit_code == 0
    assert result.output == ""


def test_describe(mapping_file):
    runner = CliRunner()
    result = runner.invoke(main, ["describe", str(mapping_file)])
    assert result.exit_code == 0
    assert result.output != ""
