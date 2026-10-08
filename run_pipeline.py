"""Run the full Retail Footprint Expansion Model.

    python run_pipeline.py                     # default settings from src/footprint/config.py
    python run_pipeline.py --simulate          # regenerate the simulated data first
    python run_pipeline.py --ideal-tp 16       # try a different Ideal TP for this run only
    python run_pipeline.py --ideal-ppo 900 --basis district_tp

Options change the settings for one run only. Every output (tables, charts, map
and Excel model) is rebuilt with them, so run again without options to go back
to the default results.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from footprint import config, pipeline, simulate  # noqa: E402


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Retail Footprint Expansion Model.")
    parser.add_argument("--simulate", action="store_true", help="regenerate the simulated data first")
    parser.add_argument("--ideal-tp", type=float, help=f"Ideal TP in liters per freezer per week (default {config.IDEAL_TP:g})")
    parser.add_argument("--ideal-ppo", type=float, help=f"Ideal PPO, target people per outlet (default {config.IDEAL_PPO})")
    parser.add_argument("--basis", choices=["ni_tp", "district_tp"],
                        help=f"TP assumed for each new outlet (default {config.NEW_OUTLET_TP_BASIS})")
    args = parser.parse_args(argv)
    for name in ("ideal_tp", "ideal_ppo"):
        value = getattr(args, name)
        if value is not None and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be greater than zero")
    return args


def apply_settings(args: argparse.Namespace) -> None:
    """Override the config values for this run."""
    if args.ideal_tp is not None:
        config.IDEAL_TP = args.ideal_tp
    if args.ideal_ppo is not None:
        config.IDEAL_PPO = args.ideal_ppo
    if args.basis is not None:
        config.NEW_OUTLET_TP_BASIS = args.basis


if __name__ == "__main__":
    args = parse_args()
    apply_settings(args)
    print(f"Settings: Ideal TP {config.IDEAL_TP:g}, Ideal PPO {config.IDEAL_PPO:g}, new outlet TP basis {config.NEW_OUTLET_TP_BASIS}")
    if args.simulate:
        simulate.main()
    pipeline.main()
