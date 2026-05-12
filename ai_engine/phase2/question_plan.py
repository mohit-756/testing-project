"""Compatibility alias for canonical services.question_plan module."""

from __future__ import annotations

import sys

from services import question_plan as _impl

sys.modules[__name__] = _impl
