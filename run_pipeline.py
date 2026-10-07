"""Run the full Retail Footprint Expansion Model.

    python run_pipeline.py            # use the simulated data already in data/simulated/
    python run_pipeline.py --simulate # regenerate the simulated data first
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from footprint import pipeline, simulate  # noqa: E402

if __name__ == "__main__":
    if "--simulate" in sys.argv:
        simulate.main()
    pipeline.main()
