import datetime
import random

import imas.util
import pytest
from imas.ids_defs import IDS_TIME_MODE_HOMOGENEOUS

from imas_iter_mapping import SignalMap
from imas_iter_mapping.util import (
    calculate_streaming_metadata,
    load_machine_description_ids,
)


@pytest.fixture(params=[False, True])
def shuffle_flux_loops(request):
    return request.param


@pytest.fixture
def full_flux_loop_mapping(iter_md_magnetics_path, shuffle_flux_loops):
    mag = load_machine_description_ids(iter_md_magnetics_path, "4.0.0", "magnetics")

    flux_loops = list(mag.flux_loop)
    if shuffle_flux_loops:
        random.shuffle(flux_loops)

    mapping = f"""\
description: Test mapping
data_dictionary_version: 4.0.0
machine_description_uri: {iter_md_magnetics_path}

target_ids: magnetics
signals:
  flux_loop:
""" + "".join(
        f"""\
  - name: {loop.name}
    flux/data: flux-{i}
    voltage/data: voltage-{i}
"""
        for i, loop in enumerate(flux_loops)
    )

    return SignalMap.from_yaml(mapping)


@pytest.fixture
def small_mapping(iter_md_magnetics_path):
    mag = load_machine_description_ids(iter_md_magnetics_path, "4.0.0", "magnetics")
    mapping = f"""\
description: Test mapping
data_dictionary_version: 4.0.0
machine_description_uri: {iter_md_magnetics_path}

target_ids: magnetics
signals:
  flux_loop:
  - name: {mag.flux_loop[0].name}
    flux/data: flux-0
    voltage/data: voltage-0
  - name: {mag.flux_loop[3].name}
    flux/data: flux-3
  - name: {mag.flux_loop[5].name}
    voltage/data: voltage-5
  b_field_pol_probe:
  - name: {mag.b_field_pol_probe[10].name}
    field/data: field-10
  - name: {mag.b_field_pol_probe[11].name}
    field/data: field-11
"""
    return SignalMap.from_yaml(mapping)


def test_mapping_to_streaming_metadata(iter_md_magnetics_path, full_flux_loop_mapping):
    metadata, signals = calculate_streaming_metadata(full_flux_loop_mapping)
    ids = metadata.static_data

    mag = load_machine_description_ids(iter_md_magnetics_path, "4.0.0", "magnetics")
    # Check that all flux loops are still here and in the same order (regardless of
    # shuffled mapping)
    for md_loop, stream_loop in zip(mag.flux_loop, ids.flux_loop, strict=True):
        # The two loop structures should be identical, but not the same object:
        assert md_loop is not stream_loop
        assert md_loop.name == stream_loop.name
        assert list(imas.util.idsdiffgen(md_loop, stream_loop)) == []

    # Check that channels without mapping are removed
    assert len(ids.b_field_pol_probe) == 0
    assert len(ids.b_field_phi_probe) == 0
    assert len(ids.rogowski_coil) == 0
    assert len(ids.shunt) == 0

    # Check signals
    assert len(signals) == 2 * len(mag.flux_loop)


def test_small_mapping(iter_md_magnetics_path, small_mapping):
    metadata, signals = calculate_streaming_metadata(small_mapping)
    ids = metadata.static_data

    mag = load_machine_description_ids(iter_md_magnetics_path, "4.0.0", "magnetics")

    assert len(ids.flux_loop) == 3  # Only flux loops with mapping should be retained
    assert ids.flux_loop[0].name == mag.flux_loop[0].name
    assert ids.flux_loop[1].name == mag.flux_loop[3].name
    assert ids.flux_loop[2].name == mag.flux_loop[5].name

    assert len(ids.b_field_pol_probe) == 2  # Idem for b_field_pol_probe
    assert ids.b_field_pol_probe[0].name == mag.b_field_pol_probe[10].name
    assert ids.b_field_pol_probe[1].name == mag.b_field_pol_probe[11].name

    # No mapping for other channels
    assert len(ids.b_field_phi_probe) == 0
    assert len(ids.rogowski_coil) == 0
    assert len(ids.shunt) == 0

    # 6 mapped signals:
    assert len(signals) == 6
    assert len(metadata.dynamic_data) == 7  # Includes time as well


def test_ids_properties_and_code(iter_md_magnetics_path, small_mapping):
    metadata, signals = calculate_streaming_metadata(small_mapping)
    ids = metadata.static_data

    assert ids.ids_properties.homogeneous_time == IDS_TIME_MODE_HOMOGENEOUS
    assert ids.ids_properties.comment
    # Check we can parse the ISO formatted date:
    datetime.datetime.fromisoformat(str(ids.ids_properties.creation_date))
    assert ids.ids_properties.provenance.node[0].reference[0].name == str(
        iter_md_magnetics_path
    )

    # Check library metadata
    assert len(ids.code.library) >= 2
    assert ids.code.library[-1].name.lower() == "imas-iter-mapping"
    assert ids.code.library[-2].name.lower() == "imas-streams"
    for lib in ids.code.library.value[-2:]:
        assert lib.description
        assert lib.version
        assert lib.repository
