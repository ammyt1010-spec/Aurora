from app.api.v1.dashboard_preferences import DashboardPreferences, WIDGET_IDS
from app.core.exceptions import ValidationDomainError
from pydantic import ValidationError
import pytest


def test_default_layout_is_safe():
    layout = DashboardPreferences()
    assert len(layout.widgets) == len(set(layout.widgets))
    assert set(layout.widgets) <= WIDGET_IDS


@pytest.mark.parametrize("ids", [["summary", "summary"], ["external"]])
def test_invalid_widget_list(ids):
    with pytest.raises(ValidationDomainError):
        DashboardPreferences.normalized(DashboardPreferences(widgets=ids))


def test_preferences_cannot_store_employee_data():
    with pytest.raises(ValidationError):
        DashboardPreferences(widgets=["summary"], employee_data={"name": "X"})
