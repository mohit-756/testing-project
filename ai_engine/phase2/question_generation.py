"""Compatibility alias for canonical services.question_generation module."""

from __future__ import annotations

import sys

from services import question_generation as _impl

sys.modules[__name__] = _impl
