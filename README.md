# IMAS ITER Mapping

File format and logic for mapping ITER CODAC signals to IMAS. 

## Development status

This project is in active development and may introduce breaking changes at any
moment.

## Project goals

The goal of this project is to provide a way to map diagnostic signals of the
[ITER tokamak](https://www.iter.org/) to the [IMAS data
standard](https://github.com/iterorganization/IMAS-Data-Dictionary).

This repository defines the YAML file format for specifying a data mapping, and
provides a Python package to validate and interpret the mapping files. Other
projects, such as `pon2imas` (not publicly accessible), perform the actual data
acquisition and transformation based on the logic provided here.

## Mapping file format

Mapping files are expressed in the [strictYAML
format](https://hitchdev.com/strictyaml/), which is a [restricted
subset](https://hitchdev.com/strictyaml/features-removed/) of YAML. An example
mapping is given below:

```yaml
description: Example mapping file for the README
data_dictionary_version: 4.0.0
machine_description_uri: iter_md_magnetics_150100_5.nc
target_ids: magnetics
signals:
  flux_loop:
  - name: 55.AD.00-MSA-1001
    flux/data: AAA-BBBB-CCCC-DDD-EEEE:FF1001-XI [Wb]
    voltage/data: AAA-BBBB-CCCC-DDD-EEEE:FF1001-XP [V]
  - name: 55.AD.00-MSA-1002
    flux/data: AAA-BBBB-CCCC-DDD-EEEE:FF1101-XI [Wb]
    voltage/data: AAA-BBBB-CCCC-DDD-EEEE:FF1101-XP [V]
```

Mapping file features:
- Map diagnostic signals to the [IMAS Data
  Dictionary](https://github.com/iterorganization/IMAS-Data-Dictionary).
- Each mapping file applies to a single diagnostic [IDS (Interface Data
  Structure)](https://imas-data-dictionary.readthedocs.io/en/latest/reference_ids.html).
- Static data, such as machine geometries, are provided in IDS format in a
  Machine Description IDS. This keeps the mapping files small and to-the-point.
- Indicate units of the source signals, to allow automatic conversion to the
  units specified in the IMAS Data Dictionary.

  **N.B.** Only 'linear' unit conversions are supported at this moment. It is
  not possible to convert logarithmic units (such as
  [`dBW`](https://en.wikipedia.org/wiki/Decibel_watt)) to their non-logarithmic
  counterparts (`W`, in this example) or vice versa.

More details about the mapping logic and file format can be found in
[docs/mapping.md](docs/mapping.md).

## Python package

You can install a development version of the python package from this repository
with `pip` as follows:

```bash
pip install 'imas-iter-mapping @ git+https://github.com/iterorganization/IMAS-ITER-Mapping.git'
```

### Command line tool

After installation, the `imas-iter-mapping` program should be available. This
program can validate a mapping file as follows:

```bash
# Validate the file 'mapping.yaml'
imas-iter-mapping validate mapping.yaml
# Or alternatively:
python -m imas_iter_mapping validate mapping.yaml
```

You can display some statistics of a mapping file and the associated machine
description with:

```bash
imas-iter-mapping describe mapping.yaml
```

You can learn more details with the `--help` option:

```bash
imas-iter-mapping --help
imas-iter-mapping validate --help
imas-iter-mapping describe --help
```



## Legal

Copyright 2025 ITER Organization. The code in this repository is licensed under
[LGPL-3.0](LICENSE.txt).
