import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.template_service import TemplateService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationTemplate, Notification


@pytest.fixture
def template():
    t = NotificationTemplate()
    t.id = "tmpl-1"
    t.name = "welcome"
    t.channel = "in_app"
    t.subject_template = "Welcome {{ name }}!"
    t.body_template = "Hello {{ name }}, welcome to Alakh!"
    t.variables = '["name"]'
    t.is_active = True
    return t


def test_render_template(template):
    svc = TemplateService()
    result = svc.render_template(template, {"name": "Alice"})
    assert "Alice" in result["body"]
    assert "Alice" in result["title"]


def test_validate_template_variables_missing(template):
    svc = TemplateService()
    missing = svc.validate_template_variables(template, {})
    assert "name" in missing


def test_validate_template_variables_ok(template):
    svc = TemplateService()
    missing = svc.validate_template_variables(template, {"name": "Bob"})
    assert missing == []


@pytest.mark.asyncio
async def test_get_unread_count():
    svc = NotificationService()
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)
    count = await svc.get_unread_count(db, "user-1")
    assert count == 5
