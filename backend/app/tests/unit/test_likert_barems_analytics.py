from types import SimpleNamespace

import pytest

from app.analytics.normality import compute_normality
from app.core.exceptions import ValidationDomainError
from app.schemas.censopas import BaremBandInput
from app.services.censopas_service import CensopasScoringService
from app.services.scoring_service import ScoringService


def test_normality_reports_inconclusive_for_small_sample() -> None:
    result = compute_normality([10.0, 20.0])

    assert result["status"] == "INCONCLUSO"
    assert result["test"] is None
    assert result["n"] == 2
    assert result["warnings"]


def test_normality_includes_histogram_and_descriptive_context() -> None:
    result = compute_normality([10, 11, 12, 13, 14, 15, 16, 17], histogram_bins=5)

    assert result["test"] == "SHAPIRO_WILK"
    assert result["mean"] == pytest.approx(13.5)
    assert sum(item["n"] for item in result["histogram"]) == 8
    assert result["status"] in {"COMPATIBLE_CON_NORMALIDAD", "NO_NORMAL"}


def test_barem_bands_must_cover_full_scale_without_gaps() -> None:
    valid = [
        BaremBandInput(
            construct_id=1,
            code="BAJO",
            label="Bajo",
            min_value=0,
            max_value=50,
            severity_order=1,
        ),
        BaremBandInput(
            construct_id=1,
            code="ALTO",
            label="Alto",
            min_value=50,
            max_value=100,
            severity_order=2,
        ),
    ]
    CensopasScoringService._validate_bands(valid)

    invalid = [valid[0], valid[1].model_copy(update={"min_value": 55})]
    with pytest.raises(ValidationDomainError, match="huecos"):
        CensopasScoringService._validate_bands(invalid)


def test_likert_item_is_normalized_and_reverse_oriented() -> None:
    options = [
        SimpleNamespace(is_active=True, numeric_value=value, raw_code=str(value))
        for value in range(1, 6)
    ]
    question = SimpleNamespace(
        is_scored=True,
        question_type="LIKERT",
        option_set=SimpleNamespace(options=options),
    )
    response = SimpleNamespace(is_missing=False, numeric_value=2, raw_code="2")
    direct_link = SimpleNamespace(question=question, scoring_direction="DIRECT")
    reverse_link = SimpleNamespace(question=question, scoring_direction="REVERSE")

    assert ScoringService._item_values(response, direct_link, None) == pytest.approx((2, 25))
    assert ScoringService._item_values(response, reverse_link, None) == pytest.approx((4, 75))


def test_censopas_risk_map_is_used_for_scoring() -> None:
    question = SimpleNamespace(
        is_scored=True,
        question_type="LIKERT",
        option_set=None,
    )
    response = SimpleNamespace(is_missing=False, numeric_value=None, raw_code="4")
    link = SimpleNamespace(question=question, scoring_direction="DIRECT")
    rule = SimpleNamespace(parameters={"risk_map": {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5}})

    assert ScoringService._item_values(response, link, rule) == pytest.approx((4, 75))


def test_missing_policy_is_configurable() -> None:
    assert ScoringService._meets_missing_policy(3, 5, {"missing_policy": "ALLOW_PARTIAL"})
    assert not ScoringService._meets_missing_policy(3, 5, {"missing_policy": "STRICT_COMPLETE"})
    assert ScoringService._meets_missing_policy(
        4, 5, {"missing_policy": "PRORATE_IF_THRESHOLD_MET", "min_completion_percent": 80}
    )
