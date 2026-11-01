"""The simulator runs the real engine over simulated shop days; a few seeded days keep it honest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import queue_sim  # noqa: E402


def test_the_default_shop_predicts_most_waits_within_ten_minutes():
    s = queue_sim.simulate(queue_sim.Scenario(), days=8).summary()
    assert s["customers"] > 300 and s["served"] >= s["customers"]
    assert s["mae_min"] < 10 and s["within_10_min"] > 0.65 and s["in_shown_range"] > 0.65
    assert abs(s["bias_min"]) < 4  # neither too hopeful nor too gloomy


def test_runs_are_repeatable():
    a = queue_sim.simulate(queue_sim.Scenario(), days=2, seed=3).summary()
    b = queue_sim.simulate(queue_sim.Scenario(), days=2, seed=3).summary()
    assert a == b


def test_edge_cases_run_and_an_empty_shop_is_exact():
    for name, sc in queue_sim.EDGE.items():
        s = queue_sim.simulate(sc, days=3).summary()
        assert s["customers"] > 0, name
    empty = queue_sim.simulate(queue_sim.EDGE["empty shop"], days=10).summary()
    assert empty["mae_min"] < 1 and empty["avg_wait_min"] < 10
