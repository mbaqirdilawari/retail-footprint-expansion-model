import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(scope="session")
def districts():
    from footprint import geo

    return geo.load_districts()


@pytest.fixture(scope="session")
def results():
    from footprint import pipeline

    return pipeline.run(save=False)
