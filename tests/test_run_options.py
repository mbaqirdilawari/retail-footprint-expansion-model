"""Command line options override the model settings for one run."""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
run_pipeline = importlib.import_module("run_pipeline")

from footprint import config, pipeline  # noqa: E402


@pytest.fixture
def restore_config():
    saved = (config.IDEAL_TP, config.IDEAL_PPO, config.NEW_OUTLET_TP_BASIS)
    yield
    config.IDEAL_TP, config.IDEAL_PPO, config.NEW_OUTLET_TP_BASIS = saved


def test_options_are_parsed_and_applied(restore_config):
    args = run_pipeline.parse_args(["--ideal-tp", "16", "--ideal-ppo", "900", "--basis", "district_tp"])
    run_pipeline.apply_settings(args)
    assert (config.IDEAL_TP, config.IDEAL_PPO, config.NEW_OUTLET_TP_BASIS) == (16.0, 900.0, "district_tp")


def test_no_options_keep_the_defaults(restore_config):
    before = (config.IDEAL_TP, config.IDEAL_PPO, config.NEW_OUTLET_TP_BASIS)
    run_pipeline.apply_settings(run_pipeline.parse_args([]))
    assert (config.IDEAL_TP, config.IDEAL_PPO, config.NEW_OUTLET_TP_BASIS) == before


def test_invalid_values_are_rejected():
    with pytest.raises(SystemExit):
        run_pipeline.parse_args(["--ideal-tp", "0"])
    with pytest.raises(SystemExit):
        run_pipeline.parse_args(["--basis", "something_else"])


def test_override_changes_the_plan_as_in_the_sensitivity_table(restore_config):
    run_pipeline.apply_settings(run_pipeline.parse_args(["--ideal-tp", "17"]))
    plan = pipeline.run(save=False)["plan"]
    expected = pd.read_csv(ROOT / "outputs" / "tables" / "ideal_tp_sensitivity.csv").set_index("ideal_tp").loc[17.0]
    assert len(plan) == expected["shortlisted_districts"]
    assert plan["final_new_outlets"].sum() == expected["final_new_outlets"]
