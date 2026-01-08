import copy
import datetime
from collections.abc import Sequence
from functools import cache
from importlib.metadata import distribution
from typing import TYPE_CHECKING

import imas
import numpy as np
from imas.ids_data_type import IDSDataType
from imas.ids_defs import IDS_TIME_MODE_HOMOGENEOUS
from imas.ids_metadata import IDSMetadata
from imas.ids_toplevel import IDSToplevel
from imas_streams import DynamicData, StreamingIMASMetadata

if TYPE_CHECKING:
    from imas_iter_mapping.mapping import ChannelSignal, SignalMap


@cache
def load_machine_description_ids(
    md_uri: str, dd_version: str, ids_name: str
) -> IDSToplevel:
    """Load machine description IDS. The result is cached and shouldn't be modified."""
    with imas.DBEntry(md_uri, "r", dd_version=dd_version) as entry:
        # Assume MD is small enough to do a full get
        return entry.get(ids_name)


def _dynamicdata_from_ids(item) -> DynamicData:
    """Construct DynamicData for the provided data item in an IDS"""
    metadata: IDSMetadata = item.metadata
    if metadata.ndim > 1:
        raise NotImplementedError(
            "Streaming data with more than 1 dimension is not implemented."
        )
    if metadata.data_type != IDSDataType.FLT:
        raise NotImplementedError(f"Unsupported data type: {metadata.data_type}")
    return DynamicData(
        path=imas.util.get_full_path(item),
        shape=(1,) * metadata.ndim,
        data_type="f64",
    )


def add_library_metadata(code, libraries: Sequence[str]) -> None:
    """Fill library metadata in the code structure of an IDS.

    Args:
        code: Code structure inside an IDS.
        libraries: Sequence of Python libraries to add metadata for. The metadata is
            obtained through ``importlib.metadata`` from the Python standard library.

    Example:
        .. code-block::

            ids = imas.IDSFactory("4.0.0").magnetics()
            add_library_metadata(ids.code, ("imas-streams", "imas-iter-mapping"))
    """
    library = code.library
    n_libs = len(library)
    code.library.resize(n_libs + len(libraries), keep=True)
    for i, distname in enumerate(libraries, start=n_libs):
        dist = distribution(distname)
        meta = dist.metadata

        library[i].name = dist.name
        library[i].description = meta.get("summary", "")
        library[i].version = dist.version
        library[i].repository = meta.get("project-url", "")


def calculate_streaming_metadata(
    signalmap: "SignalMap",
) -> tuple[StreamingIMASMetadata, list["ChannelSignal"]]:
    """Calculate streaming metadata and corresponding signals from the mapping.

    Note that the ChannelSignal list has one item less than the dynamic data in the
    StreamingIMASMetadata: the time variable is not explicitly mapped, while being
    explicitly mentioned in the metadata.
    """
    machine_description = load_machine_description_ids(
        signalmap.machine_description_uri,
        signalmap.data_dictionary_version,
        signalmap.target_ids,
    )
    static_data = copy.deepcopy(machine_description)
    static_data.time = np.array([np.nan])

    # List of dynamic data and corresponding list of PON signals:
    dynamic_data: list[DynamicData] = [_dynamicdata_from_ids(static_data.time)]
    signals: list[ChannelSignal] = []

    # Fill IDS
    properties = static_data.ids_properties
    properties.homogeneous_time = IDS_TIME_MODE_HOMOGENEOUS
    properties.comment = "Streaming IMAS data from ITER Diagnostics"
    now = datetime.datetime.now(datetime.UTC)
    properties.creation_date = now.isoformat(timespec="seconds")
    properties.provenance.node.resize(1)
    properties.provenance.node[0].path = ""  # whole IDS
    properties.provenance.node[0].reference.resize(1)
    properties.provenance.node[0].reference[0].name = signalmap.machine_description_uri
    add_library_metadata(static_data.code, ("imas-streams", "imas-iter-mapping"))

    # Populate paths relevant for the mapping
    for item in static_data:
        # Loop over all filled AoS in the IDS root and filter based on channel name
        if item.metadata.data_type is not IDSDataType.STRUCT_ARRAY or not len(item):
            continue

        if item.metadata.name in signalmap.signals:
            # We have a mapping for this array of structures:
            channels = signalmap.signals[item.metadata.name]
            channelmap = {channel.name: channel for channel in channels}
            # Only keep items in the array of structures for which we map data:
            mapped_children = [c for c in item if str(c.name) in channelmap]
            item.value = mapped_children
            # Populate dynamic data
            for child in mapped_children:
                channel = channelmap[str(child.name)]
                for channel_signal in channel.signals:
                    ids_item = child[channel_signal.path]
                    dynamic_data.append(_dynamicdata_from_ids(ids_item))
                    signals.append(channel_signal)

        else:
            # Clear unmapped diagnostic channels:
            item.resize(0)

    # Double check that we have everything
    num_expected_fields = 1 + sum(
        len(channel.signals)
        for channels in signalmap.signals.values()
        for channel in channels
    )
    assert num_expected_fields == len(dynamic_data)

    return (
        StreamingIMASMetadata(
            data_dictionary_version=signalmap.data_dictionary_version,
            ids_name=signalmap.target_ids,
            static_data=static_data,
            dynamic_data=dynamic_data,
        ),
        signals,
    )
