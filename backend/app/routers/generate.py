"""Canonical import surface for the test case generation API route.

The generation endpoint's implementation lives in
:mod:`app.routers.generation` (mirroring the ``app.models.generation`` /
``app.models.schemas`` split). This module re-exports the same
:class:`~fastapi.APIRouter` instance under the ``app.routers.generate``
name so both the endpoint's descriptive module name and a short,
task/spec-aligned alias ("generate") are available to importers without
ever constructing — and therefore registering — a second router.

``app.main`` mounts :data:`app.routers.generation.router` directly; this
module is provided purely for naming convenience and must not be included
a second time via :meth:`fastapi.FastAPI.include_router`, or the
``/api/generate/test-cases`` route would be registered twice.
"""

from __future__ import annotations

from app.routers.generation import (
    generate_test_cases_endpoint,
    router,
)

__all__ = ["router", "generate_test_cases_endpoint"]
