"""Tests for the Phase 1 demand model."""
import math

import pandas as pd

from footprint import config, model


def test_no_new_outlets_when_tp_is_already_below_ideal():
    # 100 outlets selling 10 liters per week each: TP 10 is below the ideal of 15
    n, why = model.outlets_to_add(outlets=100, volume=100 * 10 * 52, target_population=1_000_000, outlet_tp=8)
    assert n == 0
    assert why == "TP already at or below ideal"


def test_no_new_outlets_when_ppo_is_already_below_ideal():
    n, why = model.outlets_to_add(outlets=1000, volume=1000 * 20 * 52, target_population=500_000, outlet_tp=12)
    assert n == 0
    assert why == "PPO already at or below ideal"


def test_tp_limit_matches_the_formula():
    outlets, volume, tp_new = 1000, 1000 * 20 * 52, 10
    n, why = model.outlets_to_add(outlets, volume, target_population=10_000_000, outlet_tp=tp_new)
    # Solve by hand: volume + n*(52*10 + 80) = 15*52*(1000 + n)
    exact = (volume - 15 * 52 * outlets) / (15 * 52 - (52 * tp_new + 80))
    assert n == math.floor(exact)
    assert why == "Stopped by TP reaching ideal"
    # One more outlet would push TP below the ideal
    curve = model.tp_curve(outlets, volume, 10_000_000, tp_new, max_new=n + 1)
    assert curve["tp"].iloc[n] >= config.IDEAL_TP > curve["tp"].iloc[n + 1]


def test_ppo_limit_when_new_outlets_sell_well():
    # New outlets sell above the ideal TP, so TP never falls: PPO is the limit
    n, why = model.outlets_to_add(outlets=100, volume=100 * 20 * 52, target_population=300_000, outlet_tp=18)
    assert n == 300_000 // 750 - 100
    assert why == "Stopped by PPO reaching ideal"


def test_closed_form_equals_one_at_a_time_search(results):
    """The VBA macro adds outlets one at a time. Python solves it directly. They must agree."""
    m = results["district_model"]
    for r in m.itertuples(index=False):
        n = 0
        outlets, vol, pop, tp = r.retailers_2024, r.volume_2024, r.target_population_2024, r.new_outlet_tp
        if outlets > 0 and vol / outlets / 52 > config.IDEAL_TP and pop / outlets > config.IDEAL_PPO:
            while True:
                next_tp = (vol + (n + 1) * (52 * tp + config.FIRST_FILL_LITERS)) / (outlets + n + 1) / 52
                if next_tp < config.IDEAL_TP or pop / (outlets + n + 1) < config.IDEAL_PPO:
                    break
                n += 1
        assert n == r.recommended_new_outlets, r.district


def test_metrics_follow_their_definitions(results):
    m = results["district_model"]
    big = m[m["retailers_2024"] > 0]
    pd.testing.assert_series_equal(big["pcc_2024"], big["volume_2024"] / big["target_population_2024"], check_names=False)
    pd.testing.assert_series_equal(big["ppo_2024"], big["target_population_2024"] / big["retailers_2024"], check_names=False)
    pd.testing.assert_series_equal(big["tp_2024"], big["volume_2024"] / big["retailers_2024"] / 52, check_names=False)


def test_new_tp_never_below_ideal_after_expansion(results):
    m = results["district_model"]
    grown = m[m["recommended_new_outlets"] > 0]
    assert (grown["new_tp"] >= config.IDEAL_TP - 1e-9).all()
    assert (grown["new_ppo"] >= config.IDEAL_PPO - 1e-9).all()


def test_shortlist_respects_expansion_waves(results):
    plan = results["plan"]
    assert len(plan) <= config.TOP_N_DISTRICTS
    assert plan["expansion_wave"].is_monotonic_increasing
    assert (plan["recommended_new_outlets"] > 0).all()
