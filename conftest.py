from pathlib import Path

import pytest


@pytest.fixture
def iter_md_magnetics_path():
    pth = Path(__file__).parent / "tests/iter_md_magnetics_150100_5.nc"
    if not pth.exists():
        raise ValueError("Test data is missing. Please run `prepare-test-data.sh`.")
    return pth
