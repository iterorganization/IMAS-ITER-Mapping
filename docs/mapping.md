# Mapping file format

IMAS-ITER-Mapping files consist of a short header, followed by the mapping of
signals to the IMAS Data Dictionary.

## File header

The file header consists of the following (meta)data:

- `description`: A free-format text field to describe the mapping file.
- `data_dictionary_version`: The version of the IMAS Data Dictionary that the
  mapping file applies to.
- `machine_description_uri`: The IMAS URI or path to the IMAS netCDF file of the
  dataset that contains the machine description for the mapping. The machine
  description contains relevant static data, such as the geometries of
  diagnostics. 
- `target_ids`: The name of the [IDS (Interface Data
  Structure)](https://imas-data-dictionary.readthedocs.io/en/latest/reference_ids.html)
  that the mapping applies to.

## Signal mapping

The signal mapping is defined in the `signals:` section of the YAML file.
Inside, you can give a mapping for one or more _diagnostic channels_ inside the
target IDS. _diagnostic channels_ are [Array of
Structures](https://imas-data-dictionary.readthedocs.io/en/latest/data_types.html#AoS)
elements in the IDS, for example:

- [`beam`](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/ec_launchers.html#ec_launchers-beam)
  in the `ec_launchers` IDS.
- [`channel`](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/ece.html#ece-channel)
  in the `ece` IDS.
- [`antenna`](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/ic_antennas.html#ic_antennas-antenna)
  in the `ic_antennas` IDS.
- [`flux_loop`](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/magnetics.html#magnetics-flux_loop)
  or
  [`b_field_pol_probe`](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/magnetics.html#magnetics-b_field_pol_probe)
  in the `magnetics` IDS.
- [`coil`](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/pf_active.html#pf_active-coil)
  in the `pf_active` IDS.
- [`channel`](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/polarimeter.html#polarimeter-channel)
  in the `polarimeter` IDS.

Each element of a _diagnostic channel_ in the IDS is uniquely identified by
their `name` attribute, and therefore this `name` is special in the mapping file
as well.

Let's take a look at an example signal mapping for the `magnetics` IDS and break
down the meaning of each line.

```yaml
signals:
  flux_loop:
  - name: 55.AD.00-MSA-1001
    flux/data: AAA-BBBB-CCCC-DDD-EEEE:FF1001-XI [Wb]
    voltage/data: AAA-BBBB-CCCC-DDD-EEEE:FF1001-XP [V]
```

The snippet above maps two signals for a single flux loop. The signals are
mapped to the
[`flux_loop`](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/magnetics.html#magnetics-flux_loop)
whose
[`name`](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/magnetics.html#magnetics-flux_loop-name)
is equal to `55.AD.00-MSA-1001`. A flux loop with this name must be available in
the corresponding machine description IDS, which describes the
[geometry](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/magnetics.html#magnetics-flux_loop-position)
and
[type](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/magnetics.html#magnetics-flux_loop-type)
of the flux loop.

The flux measured by this flux loop is given by the diagnostic signal
`AAA-BBBB-CCCC-DDD-EEEE:FF1001-XI` with units `Wb`. The data will be stored in
the
[`flux/data`](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/magnetics.html#magnetics-flux_loop-flux-data)
child element of the `flux_loop` Array of Structures.

Similarly, the voltage measured between the loop terminals is given by the
diagnostic signal `AAA-BBBB-CCCC-DDD-EEEE:FF1001-XP` with units `V`. The data
will be stored in the
[`voltage/data`](https://imas-data-dictionary.readthedocs.io/en/stable/generated/ids/magnetics.html#magnetics-flux_loop-voltage-data)
child element of the `flux_loop` Array of Structures.

## Mapping file validation rules

The mapping file is validated before it can be used. This section details the
various checks that are performed.

### Validation rules for the file header

- All elements of the [header](#file-header) must be present.
- `data_dictionary_version` must be 4.0.0 or later: the requirement that `name`
  is a uniquely identifying value was introduced with version 4.0.0 of the IMAS
  Data Dictionary.
- `data_dictionary_version` must be a valid version of the IMAS Data Dictionary.

  **N.B.** if you get an error that the Data Dictionary version cannot be found,
  you may need to update the [`imas-data-dictionaries` Python
  package](https://pypi.org/project/imas-data-dictionaries/) which provides the
  Data Dictionary definitions.
- `target_ids` must be a valid IDS name that exists in the specified version of
  the IMAS Data Dictionary.
- The `machine_description_uri` must be valid, and must have data for the
  `target_ids` IDS.

### Validation rules for the signal mapping

- A `signals:` element must be present in the file.
- Every key in the `signals` element (e.g. `flux_loop` in the example above)
  must correspond to an Array of Structures in the target IDS. This must
  furthermore consist of a list of the following structure:

  ```yaml
  - name: <name>
    <idspath1>: <signal1> [<unit1>]
    ...
  ```

  Further validation checks are performed on this data:

  - The `name` key must be present, and its value (`<name>`) must correspond to
    a name in the Machine Description IDS.
  - Each `name` in the mapping must be unique.
  - The `<idspath1>` must exist as a child element in the IDS.
  - `<signal1>` is the name of the diagnostic signal, which name must be unique
    in the mapping file.
  - `<unit1>` is mandatory to provide, it must parse correctly and be compatible
    with the units in the Data Dictionary.
    
    For example, it is not valid if the source signal has units `m` (meter), but
    the Data Dictionary expects data with units `V` (volt). However, a signal
    with units `degC` (degrees Celsius) is compatible when the Data Dictionary
    expects data with units `K` (kelvin).
