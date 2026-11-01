"""A write is saved before the client hears it worked: every route commits, then responds."""

import importlib
import os
import pkgutil

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from fastapi.routing import APIRoute

import app.routers
from app.database import get_db


def _db_dependencies(dependant):
    for dep in dependant.dependencies:
        if dep.call is get_db:
            yield dep
        yield from _db_dependencies(dep)


def test_every_route_commits_before_it_responds():
    deps = []
    for module in pkgutil.iter_modules(app.routers.__path__):
        router = getattr(importlib.import_module(f"app.routers.{module.name}"), "router", None)
        for route in getattr(router, "routes", []):
            if isinstance(route, APIRoute):
                deps += [(route.path, dep.scope) for dep in _db_dependencies(route.dependant)]
    assert deps
    assert [d for d in deps if d[1] != "function"] == []
