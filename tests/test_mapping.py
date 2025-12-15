import pytest

from imas_iter_mapping import UNIT_REGISTRY, SignalMap


@pytest.fixture()
def mapping():
    mapping = """\
description: Test mapping
data_dictionary_version: 4.0.0
machine_description_uri: imas:hdf5?path=/work/imas/shared/imasdb/ITER_MD/4/150100/5

target_ids: magnetics
signals:
  flux_loop:
  - name: 55.AD.00-MSA-1001
    flux/data: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI0 [Wb]
    voltage/data: CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI1 [mV]
"""
    return SignalMap.from_yaml(mapping)


def test_signal_map(mapping):
    assert mapping.description == "Test mapping"
    assert mapping.data_dictionary_version == "4.0.0"
    assert (
        mapping.machine_description_uri
        == "imas:hdf5?path=/work/imas/shared/imasdb/ITER_MD/4/150100/5"
    )
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
    assert channelmaps[0].signals[1].path == "voltage/data"
    assert channelmaps[0].signals[1].signal == "CWS-SCSU-CC2A-WCC-WPU1:PT1002-XI1"
    assert channelmaps[0].signals[1].source_units == UNIT_REGISTRY.Quantity("mV")
    assert channelmaps[0].signals[1].dd_units == UNIT_REGISTRY.Unit("V")
