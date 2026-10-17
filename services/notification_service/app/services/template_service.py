from typing import List

import structlog
from jinja2 import BaseLoader, TemplateError
from jinja2.sandbox import ImmutableSandboxedEnvironment

from app.models.notification import NotificationTemplate

log = structlog.get_logger()

# Templates are authored through the API, so they must not reach Python internals
# (e.g. ``cycler.__init__.__globals__.os``); the sandbox raises SecurityError instead.
jinja_env = ImmutableSandboxedEnvironment(loader=BaseLoader(), autoescape=True)


class TemplateService:
    def check_syntax(self, source: str) -> None:
        try:
            jinja_env.parse(source)
        except TemplateError as e:
            raise ValueError(f"Template syntax error: {e}") from e

    def render_template(self, template: NotificationTemplate, variables: dict) -> dict:
        try:
            body_tmpl = jinja_env.from_string(template.body_template)
            rendered_body = body_tmpl.render(**variables)
            rendered_subject = ""
            if template.subject_template:
                subj_tmpl = jinja_env.from_string(template.subject_template)
                rendered_subject = subj_tmpl.render(**variables)
            return {"title": rendered_subject, "body": rendered_body}
        except TemplateError as e:
            log.error("template_render_failed", template=template.name, error=str(e))
            raise ValueError(f"Template render error: {e}") from e

    def validate_template_variables(self, template: NotificationTemplate, variables: dict) -> List[str]:
        import json

        required: List[str] = []
        if template.variables:
            try:
                required = json.loads(template.variables)
            except Exception:
                pass
        missing = [v for v in required if v not in variables]
        return missing


template_service = TemplateService()
