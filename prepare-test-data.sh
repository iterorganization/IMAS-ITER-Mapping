#!/bin/bash
# Download ITER magnetics Machine Description from Zenodo and store in the test folder

curl -o tests/iter_md_magnetics_150100_5.nc \
    "https://zenodo.org/records/17113713/files/iter_md_magnetics_150100_5.nc?download=1"
