"""Compatibility alias for canonical services.llm_question_generator module."""

from __future__ import annotations

import sys

from services import llm_question_generator as _impl

sys.modules[__name__] = _impl
