"""Hand-calculated method benchmarks; not official instrument certification."""
import pytest

from app.analytics.censopas.scoring import (
    aggregate_construct_score, apply_direction, derive_item_values,
)
from app.analytics.reliability import compute_cronbach_alpha, compute_reliability
from app.analytics.normality import compute_normality


def test_cronbach_alpha_perfect_parallel_items():
    data = [[1, 2, 3], [2, 3, 4], [3, 4, 5], [4, 5, 6]]
    assert compute_cronbach_alpha(data) == pytest.approx(1.0)
    result = compute_reliability(data)
    assert result["omega_method"] == "PCA_UNIFACTORIAL_APPROXIMATION"


def test_legacy_100_scale_interior_value_is_not_ordinal_five():
    options = {"a": 0, "b": 5, "c": 25, "d": 75, "e": 100}
    risk_value, score_0_100 = derive_item_values("b", options, direction=None)
    assert risk_value == pytest.approx(1.2)
    assert score_0_100 == pytest.approx(5.0)


def test_censopas_ordinal_reverse_and_weighted_mean():
    options = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
    risk_value, score = derive_item_values("a", options, direction="REVERSE")
    assert risk_value == pytest.approx(5.0)
    assert score == pytest.approx(100)
    assert apply_direction(25, "REVERSE") == 75
    assert aggregate_construct_score([(20, 1, None), (80, 3, None)]) == pytest.approx(65)


def test_normality_not_claimed_for_insufficient_sample():
    result = compute_normality([2.0, 3.0])
    assert result["p_value"] is None
    assert result["status"] == "INCONCLUSO"
