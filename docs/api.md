# IMAS-ITER-Mapping Python API examples

This page lists a couple of code examples for using the IMAS-ITER-Mapping Python
API. More detailed descriptions of the methods and classes shown are available
as Python docstrings (which your IDE should be able to show you).

## Parsing a mapping file

The following code will parse the YAML in the mapping file. This will raise an
exception when the mapping is invalid (see [mapping.md](mapping.md)).

```python
from imas_iter_mapping import SignalMap

fname = "mapping.yml"
with open(fname, "r") as file:
    signalmap = SignalMap.from_yaml(file)
```

Alternatively, `SignalMap.from_yaml` also accepts strings as input. However,
this will give less clear error messages for your users, as the filename is then
not available to the YAML parsing code.

## Unit conversions

Each mapped signal (`ChannelSignal` class) can calculate the required scale and
offset to convert the signal's units to the units expected by the IMAS Data
Dictionary. To obtain the right value according to the IMAS standard, we need to
calculate:

```python
value_for_imas = value_from_signal * scale + offset
```

See below example script. Note that this requires the
`iter_md_magnetics_150100_5.nc` file which can be downloaded from Zenodo (see
[`prepare-test-data.sh`](../prepare-test-data.sh)).

```python
from imas_iter_mapping import SignalMap

signal_map = SignalMap.from_yaml("""\
description: Example mapping file for unit transformations
data_dictionary_version: 4.0.0
machine_description_uri: tests/iter_md_magnetics_150100_5.nc
target_ids: magnetics
signals:
  flux_loop:
  - name: 55.AD.00-MSA-1001
    flux/data: test1 [Wb]
    voltage/data: test2 [mV]
""")
channel = signal_map.signals["flux_loop"][0]
print(channel.name)  # 55.AD.00-MSA-1001
for signal in channel.signals:
    print(signal.signal, signal.get_unit_conversion())
# Will print:
# test1 UnitConversion(scale=1.0, offset=0.0)
# test2 UnitConversion(scale=0.001, offset=0.0)
```

The signal `test1` has data with units `Wb` which is the same as the Data
Dictionary units. The `UnitConversion` indicates that the scale is 1.0 and
offset is 0.0.

The signal `test1` has data with units `mV`, while the Data Dictionary requires
units of `V`. The `UnitConversion` indicates that we need to scale the signal
by `0.001` and add zero offset to go from millivolt to volt, as expected.

## Integration with [IMAS-Streams](https://github.com/iterorganization/IMAS-Streams)

The following example shows how to apply the data mapping and publish data as an
IMAS Stream over Kafka:

```python
import numpy as np
from imas_iter_mapping import (
    SignalMap,
    calculate_streaming_metadata,
    get_unit_conversion_arrays,
)
from imas_streams.kafka import KafkaProducer, KafkaSettings

# Read and parse the user-provided mapping file
fname = "mapping.yml"
with open(fname, "r") as file:
    signalmap = SignalMap.from_yaml(file)

# Extract Streaming IMAS Metadata and a list of signals
metadata, signals = calculate_streaming_metadata(signalmap)
# Scale and offset for unit conversions of all signals
scale, offset = get_unit_conversion_arrays(signals)

# Setup Kafka streaming IMAS producer
kafka_settings = KafkaSettings(
    host="localhost:9092",
    topic_name="test_topic",
)
kafka_producer = KafkaProducer(kafka_settings, metadata)

# Time loop
t = 0.0
t_end = 10.0
dt = 1.0
while t < t_end:
    # Initialize the data array:
    # - The time goes as first item (which is not in the signal list)
    # - The remaining elements correspond to a mapped signal
    data = np.zeros(len(signals) + 1, dtype="<f8")
    data[0] = t
    for i, signal in enumerate(signals, start=1):
        # read_signal should return the value of the signal at time t
        data[i] = read_signal(signal.signal, t)
    # Unit conversions
    data[1:] *= scale
    data[1:] += offset
    # Send data to kafka topic
    kafka_producer.send(data.tobytes())
    # Increment time
    t += dt
```
