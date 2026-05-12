import time
import json
import logging
import os
from dataclasses import dataclass, field
from threading import Lock
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cerebras Free-Tier limits (llama3.1-8b)
# ---------------------------------------------------------------------------
CEREBRAS_LIMITS = {
    "rpm": 30,
    "tpm": 60_000,
    "daily_tokens": 1_000_000,
}

# ---------------------------------------------------------------------------
# Configurable daily budget (default = full free tier)
# ---------------------------------------------------------------------------
DAILY_BUDGET = int(os.getenv("LLM_DAILY_TOKEN_BUDGET", CEREBRAS_LIMITS["daily_tokens"]))
THROTTLE_AT_PCT = int(os.getenv("LLM_THROTTLE_AT_PCT", 80))
BLOCK_AT_PCT = int(os.getenv("LLM_BLOCK_AT_PCT", 95))

# ---------------------------------------------------------------------------
# Persistent daily usage file (survives server restarts)
# ---------------------------------------------------------------------------
_USAGE_FILE = Path(".cache/daily_usage.json")
Path(".cache").mkdir(exist_ok=True)

def _load_daily_state() -> tuple[int, float]:
    """Return (daily_total, day_start) from disk."""
    if _USAGE_FILE.exists():
        try:
            data = json.loads(_USAGE_FILE.read_text())
            return data.get("daily_total", 0), data.get("day_start", time.time())
        except Exception:
            pass
    return 0, time.time()

def _save_daily_state(daily_total: int, day_start: float) -> None:
    try:
        _USAGE_FILE.write_text(json.dumps({"daily_total": daily_total, "day_start": day_start}))
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Sliding-window tracker
# ---------------------------------------------------------------------------
@dataclass
class _WindowEntry:
    ts: float
    prompt_tokens: int
    completion_tokens: int

_lock = Lock()
_entries: list[_WindowEntry] = []
_daily_total, _day_start = _load_daily_state()

def _prune(now: float) -> None:
    """Drop entries older than 60 s and reset daily counter after 24 h."""
    global _daily_total, _day_start
    cutoff = now - 60
    while _entries and _entries[0].ts < cutoff:
        _entries.pop(0)
    if now - _day_start > 86_400:
        _daily_total = 0
        _day_start = now
        _save_daily_state(0, _day_start)
        logger.info("LLM_BUDGET: Daily token counter reset.")

def _check_budget() -> dict:
    """Return throttle/block status based on current daily usage."""
    pct = (_daily_total / DAILY_BUDGET * 100) if DAILY_BUDGET > 0 else 0
    blocked = pct >= BLOCK_AT_PCT
    throttled = pct >= THROTTLE_AT_PCT
    return {
        "budget_pct": round(pct, 1),
        "budget_remaining": max(0, DAILY_BUDGET - _daily_total),
        "throttled": throttled,
        "blocked": blocked,
        "throttle_delay": 5 if throttled and not blocked else 0,
    }

def track_request(prompt_tokens: int = 0, completion_tokens: int = 0) -> dict:
    """Record one completed LLM call and return current usage snapshot."""
    global _daily_total
    now = time.time()
    with _lock:
        _entries.append(_WindowEntry(now, prompt_tokens, completion_tokens))
        _daily_total += prompt_tokens + completion_tokens
        _prune(now)
        _save_daily_state(_daily_total, _day_start)
        rpm = len(_entries)
        tpm = sum(e.prompt_tokens + e.completion_tokens for e in _entries)
        budget = _check_budget()
        return {
            "rpm": rpm,
            "tpm": tpm,
            "daily_tokens": _daily_total,
            "rpm_limit": CEREBRAS_LIMITS["rpm"],
            "tpm_limit": CEREBRAS_LIMITS["tpm"],
            "daily_limit": DAILY_BUDGET,
            "rpm_pct": round(rpm / CEREBRAS_LIMITS["rpm"] * 100, 1),
            "tpm_pct": round(tpm / CEREBRAS_LIMITS["tpm"] * 100, 1),
            "daily_pct": round(_daily_total / DAILY_BUDGET * 100, 1) if DAILY_BUDGET > 0 else 0,
            **budget,
        }

def parse_rate_limit_headers(headers: dict) -> dict:
    """Extract Cerebras rate-limit headers into a readable dict."""
    return {
        "remaining_requests_day": headers.get("x-ratelimit-remaining-requests-day"),
        "remaining_tokens_minute": headers.get("x-ratelimit-remaining-tokens-minute"),
        "reset_requests_day_s": headers.get("x-ratelimit-reset-requests-day"),
        "reset_tokens_minute_s": headers.get("x-ratelimit-reset-tokens-minute"),
    }

def get_snapshot() -> dict:
    """Return current usage without adding a new entry."""
    now = time.time()
    with _lock:
        _prune(now)
        rpm = len(_entries)
        tpm = sum(e.prompt_tokens + e.completion_tokens for e in _entries)
        budget = _check_budget()
        return {
            "rpm": rpm,
            "tpm": tpm,
            "daily_tokens": _daily_total,
            "rpm_limit": CEREBRAS_LIMITS["rpm"],
            "tpm_limit": CEREBRAS_LIMITS["tpm"],
            "daily_limit": DAILY_BUDGET,
            "rpm_pct": round(rpm / CEREBRAS_LIMITS["rpm"] * 100, 1),
            "tpm_pct": round(tpm / CEREBRAS_LIMITS["tpm"] * 100, 1),
            "daily_pct": round(_daily_total / DAILY_BUDGET * 100, 1) if DAILY_BUDGET > 0 else 0,
            **budget,
        }

def estimate_tokens(text: str) -> int:
    """Rough estimate: 4 chars ≈ 1 token (fallback only)."""
    if not text:
        return 0
    return max(1, len(text) // 4)

def log_token_usage(
    prompt: str = "",
    response: str = "",
    model: str = "",
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    rate_headers: dict | None = None,
) -> int:
    """Log actual token usage and current RPM/TPM.

    If prompt_tokens / completion_tokens are supplied (from the API response
    ``usage`` field), they are used directly.  Otherwise falls back to
    estimate_tokens().
    """
    pt = prompt_tokens if prompt_tokens is not None else estimate_tokens(prompt)
    ct = completion_tokens if completion_tokens is not None else estimate_tokens(response)
    total = pt + ct

    usage = track_request(pt, ct)

    header_info = ""
    if rate_headers:
        rh = parse_rate_limit_headers(rate_headers)
        header_info = (
            f" | remaining_req_day={rh['remaining_requests_day']}"
            f" | remaining_tok_min={rh['remaining_tokens_minute']}"
        )

    logger.info(
        f"LLM_TOKEN_LOG: model={model} "
        f"| prompt_tokens={pt} | completion_tokens={ct} | total={total}"
        f" | rpm={usage['rpm']}/{usage['rpm_limit']} ({usage['rpm_pct']}%)"
        f" | tpm={usage['tpm']}/{usage['tpm_limit']} ({usage['tpm_pct']}%)"
        f" | daily={usage['daily_tokens']}/{usage['daily_limit']} ({usage['daily_pct']}%)"
        f" | budget_remaining={usage['budget_remaining']}"
        f"{header_info}"
    )

    if usage.get("blocked"):
        logger.error("LLM_BUDGET_BLOCKED: Daily usage at %s%% — requests should be rejected!", usage["budget_pct"])
    elif usage.get("throttled"):
        logger.warning("LLM_BUDGET_THROTTLED: Daily usage at %s%% — adding delay to requests.", usage["budget_pct"])
    elif usage["rpm_pct"] >= 80:
        logger.warning("LLM_RATE_WARN: RPM at %s%% of limit!", usage["rpm_pct"])
    elif usage["tpm_pct"] >= 80:
        logger.warning("LLM_RATE_WARN: TPM at %s%% of limit!", usage["tpm_pct"])
    elif usage["daily_pct"] >= 80:
        logger.warning("LLM_RATE_WARN: Daily token usage at %s%% of limit!", usage["daily_pct"])

    return total
