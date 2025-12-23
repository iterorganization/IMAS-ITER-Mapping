import random

import pytest

from imas_iter_mapping import SignalMap
from imas_iter_mapping.util import (
    calculate_streaming_metadata,
    load_machine_description_ids,
)


@pytest.fixture(params=[False, True])
def shuffle_flux_loops(request):
    return request.param


@pytest.fixture
def flux_loop_mapping(iter_md_magnetics_path, shuffle_flux_loops):
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


def test_mapping_to_streaming_metadata(iter_md_magnetics_path, flux_loop_mapping):
    metadata, signals = calculate_streaming_metadata(flux_loop_mapping)
    static_data = metadata.static_data

    mag = load_machine_description_ids(iter_md_magnetics_path, "4.0.0", "magnetics")
    # Check that all flux loops are still here and in the same order (regardless of
    # shuffled mapping)
    for md_loop, stream_loop in zip(mag.flux_loop, static_data.flux_loop, strict=True):
        assert md_loop.name == stream_loop.name

    # Check that channels without mapping are removed
    assert len(static_data.b_field_pol_probe) == 0
    assert len(static_data.b_field_phi_probe) == 0
    assert len(static_data.rogowski_coil) == 0
    assert len(static_data.shunt) == 0

    # Check signals
    assert len(signals) == 2 * len(mag.flux_loop)
