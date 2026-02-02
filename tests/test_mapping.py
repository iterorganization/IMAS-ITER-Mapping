from io import StringIO

import pytest
from strictyaml.ruamel.error import YAMLError

from imas_iter_mapping import UNIT_REGISTRY, SignalMap, ValidationError


@pytest.fixture()
def mapping(iter_md_magnetics_path):
    return f"""\
description: Test mapping
data_dictionary_version: 4.0.0
machine_description_uri: {iter_md_magnetics_path}
target_ids: magnetics
signals:
  flux_loop:
  - name: 55.AD.00-MSA-1001
    flux/data: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI0 [Wb]
    voltage/data: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI1 [mV]
"""


def test_signal_map(mapping, iter_md_magnetics_path):
    mapping = SignalMap.from_yaml(mapping)
    assert mapping.description == "Test mapping"
    assert mapping.data_dictionary_version == "4.0.0"
    assert mapping.machine_description_uri == str(iter_md_magnetics_path)
    assert mapping.target_ids == "magnetics"

    assert mapping.signals.keys() == {"flux_loop"}
    channelmaps = mapping.signals["flux_loop"]
    assert len(channelmaps) == 1

    assert channelmaps[0].name == "55.AD.00-MSA-1001"
    assert len(channelmaps[0].signals) == 2
    assert channelmaps[0].signals[0].path == "flux/data"
    assert channelmaps[0].signals[0].signal == "CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI0"
    assert channelmaps[0].signals[0].source_units == UNIT_REGISTRY.Quantity("Wb")
    assert channelmaps[0].signals[0].dd_units == UNIT_REGISTRY.Unit("Wb")
    assert channelmaps[0].signals[0].get_unit_conversion() == (1, 0)
    assert channelmaps[0].signals[1].path == "voltage/data"
    assert channelmaps[0].signals[1].signal == "CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI1"
    assert channelmaps[0].signals[1].source_units == UNIT_REGISTRY.Quantity("mV")
    assert channelmaps[0].signals[1].dd_units == UNIT_REGISTRY.Unit("V")
    assert channelmaps[0].signals[1].get_unit_conversion() == (0.001, 0)


def test_mapping_invalid_yaml(mapping):
    # each of the first 7 lines is required for a valid mapping
    for i in range(7):
        lines = mapping.splitlines()
        del lines[i]
        with pytest.raises(YAMLError):
            SignalMap.from_yaml("\n".join(lines))


def test_mapping_dd3(mapping):
    with pytest.raises(ValidationError, match="3.x is not supported") as exc:
        SignalMap.from_yaml(mapping.replace("4.0.0", "3.38.1"))
    assert exc.match("line 2")
    assert exc.match("data_dictionary_version: 3.38.1")


def test_mapping_unknown_dd(mapping):
    with pytest.raises(ValidationError, match="version 'abc' cannot be found") as exc:
        SignalMap.from_yaml(mapping.replace("4.0.0", "abc"))
    assert exc.match("line 2")
    assert exc.match("data_dictionary_version: abc")


def test_mapping_invalid_ids_name(mapping):
    with pytest.raises(ValidationError, match="IDS 'xyz' does not exist") as exc:
        SignalMap.from_yaml(mapping.replace("target_ids: magnetics", "target_ids: xyz"))
    assert exc.match("line 4")
    assert exc.match("target_ids: xyz")


def test_mapping_ids_not_in_md(mapping, iter_md_magnetics_path):
    with pytest.raises(ValidationError) as exc:
        SignalMap.from_yaml(mapping.replace("target_ids: magnetics", "target_ids: mhd"))
    assert exc.match("line 3")
    assert exc.match(f"machine_description_uri: {iter_md_magnetics_path}")


def test_mapping_invalid_md_uri(mapping, iter_md_magnetics_path):
    with pytest.raises(ValidationError) as exc:
        SignalMap.from_yaml(mapping.replace(str(iter_md_magnetics_path), "asdf"))
    assert exc.match("line 3")
    assert exc.match("machine_description_uri: asdf")


def test_mapping_invalid_channel_path(mapping):
    with pytest.raises(ValidationError, match="Unknown or invalid IDS path") as exc:
        SignalMap.from_yaml(mapping.replace("flux_loop", "flux_loop_abcd"))
    assert exc.match("line 6")
    assert exc.match("flux_loop_abcd:")


def test_mapping_channel_path_not_an_aos(mapping):
    with pytest.raises(ValidationError, match="IDS path 'code' is not") as exc:
        SignalMap.from_yaml(mapping.replace("flux_loop", "code"))
    assert exc.match("line 6")
    assert exc.match("code:")


def test_mapping_invalid_signal_path(mapping):
    with pytest.raises(ValidationError, match="Invalid path 'xyz'") as exc:
        SignalMap.from_yaml(mapping.replace("flux/data", "xyz"))
    assert exc.match("line 8")
    assert exc.match("xyz: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI0")


def test_mapping_channelname_not_in_md(mapping):
    with pytest.raises(ValidationError, match="Channel 'x' not found") as exc:
        SignalMap.from_yaml(mapping.replace("55.AD.00-MSA-1001", "x"))
    assert exc.match("line 7")
    assert exc.match("- name: x")


def test_mapping_duplicate_channelname(mapping):
    with pytest.raises(ValidationError, match="Duplicate channel name") as exc:
        SignalMap.from_yaml(mapping + "  - name: 55.AD.00-MSA-1001")
    assert exc.match("line 10")
    assert exc.match("- name: 55.AD.00-MSA-1001")


def test_mapping_duplicate_signalname(mapping):
    # Duplicate signal name in the same channel type (flux_loop)
    with pytest.raises(ValidationError, match="Duplicate signal name") as exc:
        SignalMap.from_yaml(mapping.replace("-XI1", "-XI0"))
    assert exc.match("line 9")
    assert exc.match("voltage/data: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI0")

    # Duplicate signal name in different channel types (flux_loop and rogowski_coil)
    with pytest.raises(ValidationError, match="Duplicate signal name") as exc:
        SignalMap.from_yaml(
            mapping
            + """  rogowski_coil:
                   - name: 55.AP.00-MRG-1217
                     current/data: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI0 [A]"""
        )
    assert exc.match("line 12")
    assert exc.match("current/data: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI0")


def test_mapping_no_units(mapping):
    with pytest.raises(ValidationError, match="Missing unit") as exc:
        SignalMap.from_yaml(mapping.replace("[Wb]", ""))
    assert exc.match("line 8")
    assert exc.match("flux/data: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI0")

    with pytest.raises(ValidationError, match="Was expecting a closing ']'") as exc:
        SignalMap.from_yaml(mapping.replace("[Wb]", "[Wb"))
    assert exc.match("line 8")
    assert exc.match("flux/data: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI0")


def test_mapping_invalid_units(mapping):
    with pytest.raises(ValidationError, match="Invalid unit") as exc:
        SignalMap.from_yaml(mapping.replace("[Wb]", "[-]"))
    assert exc.match("line 8")
    assert exc.match("flux/data: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI0")


def test_mapping_incompatible_units(mapping):
    with pytest.raises(ValidationError, match="incompatible with the IMAS Data") as exc:
        SignalMap.from_yaml(mapping.replace("[Wb]", "[A.m]"))
    assert exc.match("line 8")
    assert exc.match("flux/data: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI0")


def test_filename_label(mapping):
    filelike = StringIO(mapping + "abc")
    filelike.name = "mapping.yaml"
    with pytest.raises(YAMLError, match='in "mapping.yaml"'):
        SignalMap.from_yaml(filelike)

    filelike = StringIO(mapping.replace("4.0.0", "3.38.1"))
    filelike.name = "mapping.yaml"
    with pytest.raises(ValidationError, match='in "mapping.yaml"'):
        SignalMap.from_yaml(filelike)
