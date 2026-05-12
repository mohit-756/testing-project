"""LLM client helpers used strictly by .env configuration."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from functools import lru_cache
from types import SimpleNamespace
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
from utils.token_utils import log_token_usage
from core.config import config

CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_FILE = CACHE_DIR / "llm_cache.json"

def _load_cache():
    if not CACHE_FILE.exists(): return {}
    try: return json.loads(CACHE_FILE.read_text()) or {}
    except: return {}

def _save_cache(data: dict):
    try: CACHE_FILE.write_text(json.dumps(data, indent=2))
    except: pass

_llm_cache: dict[str, str] = _load_cache()

logger = logging.getLogger(__name__)

def _clean_json(raw: str) -> str:
    raw = str(raw or "").strip()
    # Try to find JSON within markdown block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        raw = match.group(1).strip()
    
    # Try to find JSON object or array as fallback
    if not raw.startswith("{") and not raw.startswith("["):
        obj_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
        if obj_match:
            raw = obj_match.group(1).strip()
    
    return raw

@lru_cache(maxsize=1)
def _resolve_llm_config() -> dict[str, Any]:
    """Single source of truth for LLM configuration from global config."""
    provider = config.LLM_PROVIDER
    
    # Values from global config
    api_key = config.LLM_API_KEY
    base_url = config.LLM_BASE_URL
    primary_model = config.LLM_MODEL_PRIMARY
    fallback_model = config.LLM_MODEL_FALLBACK
    
    # Provider-specific defaults if not provided in config
    if not primary_model:
        if provider == "cerebras": primary_model = "qwen-3-235b-a22b-instruct-2507"
        elif provider == "groq": primary_model = "llama-3.1-8b-instant"
        elif provider == "ollama": primary_model = "qwen2.5-coder:3b"
        elif provider == "openai": primary_model = "gpt-4o"
        elif provider == "gemini": primary_model = "gemini-1.5-flash"
        else: primary_model = "llama3.1-8b"

    if not fallback_model:
        fallback_model = primary_model

    if not base_url:
        if provider == "cerebras": base_url = "https://api.cerebras.ai/v1"
        elif provider == "groq": base_url = "https://api.groq.com/openai/v1"
        elif provider == "ollama": base_url = "http://localhost:11434/v1"
        elif provider == "openai": base_url = "https://api.openai.com/v1"

    return {
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "primary_model": primary_model,
        "fallback_model": fallback_model,
    }

def _build_session() -> requests.Session:
    """Create a requests.Session with connection pooling and automatic retries."""
    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    adapter = HTTPAdapter(
        pool_connections=4,
        pool_maxsize=8,
        max_retries=retry,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

_session = _build_session()

class OpenAIAdapter:
    """Generic adapter for any OpenAI-compatible API (Cerebras, Groq, Ollama, OpenAI)."""
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def create(self, messages: list[dict[str, Any]], temperature: float, max_tokens: int, **kwargs):
        model = kwargs.get("model") or self.model
        response_format = kwargs.get("response_format")
        
        # Caching logic
        cache_key = f"{model}_{temperature}_{json.dumps(messages)}_{json.dumps(response_format, sort_keys=True) if response_format else 'none'}"
        if cache_key in _llm_cache:
            logger.info(f"CACHE_HIT: model={model}")
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=_llm_cache[cache_key]))])

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens)
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        prompt_text = "\n".join([m.get("content", "") for m in messages])
        
        try:
            resp = _session.post(url, json=payload, headers=headers, timeout=120)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 30))
                logger.warning("Rate limited (429). Retrying after %ds...", retry_after)
                time.sleep(retry_after)
                resp = _session.post(url, json=payload, headers=headers, timeout=120)

            if resp.status_code != 200:
                logger.error(f"LLM API Error ({resp.status_code}): {resp.text[:500] if resp.text else 'empty response'}")
                resp.raise_for_status()

            # Check for empty response
            if not resp.text or not resp.text.strip():
                logger.error("LLM API returned empty response")
                raise ValueError("Empty response from LLM API")

            try:
                data = resp.json()
            except json.JSONDecodeError as e:
                logger.error(f"LLM API returned invalid JSON: {e}, response: {resp.text[:200]}")
                raise ValueError(f"Invalid JSON from LLM API: {e}")

            if not data or "choices" not in data:
                logger.error(f"LLM API response missing choices: {data}")
                raise ValueError(f"Invalid LLM API response: {data}")

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Extract actual token counts from API response
            usage = data.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")

            # Extract rate-limit headers from Cerebras/Groq
            rate_headers = {k: v for k, v in resp.headers.items() if k.startswith("x-ratelimit")}

            # Log token usage (actual if available, else estimate)
            log_token_usage(
                prompt=prompt_text,
                response=content,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                rate_headers=rate_headers if rate_headers else None,
            )

            # Save to cache
            _llm_cache[cache_key] = content
            _save_cache(_llm_cache)

            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise

class GeminiAdapter:
    """Specialized adapter for Google Gemini API."""
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def create(self, messages: list[dict[str, Any]], temperature: float, max_tokens: int, **kwargs):
        model = kwargs.get("model") or self.model
        if model.startswith("models/"): model = model[len("models/"):]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        
        # Simple prompt concatenation for now, as per original code
        prompt = "\n".join([m['content'] for m in messages])
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
        }
        
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

class LLMClient:
    def __init__(self):
        config = _resolve_llm_config()
        self.provider = config["provider"]
        self.primary_model = config["primary_model"]
        
        if self.provider == "gemini":
            self.adapter = GeminiAdapter(config["api_key"], self.primary_model)
        else:
            self.adapter = OpenAIAdapter(config["base_url"], config["api_key"], self.primary_model)

        # Compatibility layer for old OpenAI-style calls (.chat.completions.create)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        return self.adapter.create(
            messages=kwargs.get("messages", []),
            temperature=kwargs.get("temperature", 0.2),
            max_tokens=kwargs.get("max_tokens", 800),
            model=kwargs.get("model"),
            response_format=kwargs.get("response_format")
        )

@lru_cache(maxsize=1)
def _get_client() -> LLMClient:
    return LLMClient()

def _llm_provider() -> str: return _resolve_llm_config()["provider"]
def _llm_model() -> str: return _resolve_llm_config()["primary_model"]
def _llm_premium_model() -> str: return _resolve_llm_config()["primary_model"] # Default to primary

def extract_skills(jd_text: str) -> dict[str, int]:
    prompt = (
        "Extract ONLY core technical skills (programming languages, frameworks, libraries, "
        "databases, cloud platforms, DevOps tools, infrastructure technologies) from the job "
        "description below. Return a JSON dictionary in the exact format {\"skill\": weight} "
        "where weight is an integer from 1-10 based on how prominently the skill appears.\n\n"
        "STRICT RULES:\n"
        "- Include ONLY hard technical skills.\n"
        "- Completely ignore soft skills (e.g. Communication, Teamwork, Leadership, Problem Solving).\n"
        "- Completely ignore methodologies (e.g. Agile, Scrum, Kanban, TDD, CI/CD as a concept).\n"
        "- Completely ignore company descriptions, benefits, or cultural statements.\n"
        "- Do NOT include generic terms like 'Computer Science', 'Engineering', 'Technology'.\n"
        "- Return ONLY the JSON dictionary, no explanation.\n\n"
        f"Job Description:\n{jd_text[:4000]}"
    )
    try:
        resp = _get_client().create(messages=[{"role": "user", "content": prompt}], temperature=0.1, max_tokens=300)
        return json.loads(_clean_json(resp.choices[0].message.content))
    except Exception as e:
        logger.error(f"extract_skills failed: {e}")
        return {}

def evaluate_answer_detailed(**kwargs) -> dict[str, Any]:
    prompt = f"Evaluate answer for question: {kwargs.get('question')}\nAnswer: {kwargs.get('answer')}\nReturn JSON with score (0-100) and feedback."
    try:
        resp = _get_client().create(messages=[{"role": "user", "content": prompt}], temperature=0.2, max_tokens=500)
        return json.loads(_clean_json(resp.choices[0].message.content))
    except Exception as e:
        logger.error(f"evaluation failed: {e}")
        return {"score": 50, "feedback": "Evaluation failed."}

def extract_jd_requirements(jd_text: str) -> dict[str, Any]:
    """Extract structured requirements from JD text: skills + education + experience + min academic %."""
    prompt = (
        "Analyze the job description below and extract structured requirements. "
        "Return ONLY a JSON object with these exact keys:\n\n"
        "1. 'skills': Object with skill names as keys and importance weight (1-10) as values. "
        "   Include ONLY hard technical skills (languages, frameworks, databases, cloud, DevOps). "
        "   Ignore soft skills, methodologies, company info.\n\n"
        "2. 'education_requirement': String - one of: 'bachelor', 'master', 'phd', or null if not specified.\n\n"
        "3. 'experience_requirement': Integer - minimum years of experience or 0 if not specified.\n\n"
        "4. 'min_academic_percent': Integer - minimum academic percentage or 0 if not specified.\n\n"
        "RULES:\n"
        "- For education: look for 'B.Tech', 'BE', 'Bachelor', 'B.Sc' = 'bachelor'. "
        "'M.Tech', 'Master', 'M.Sc' = 'master'. 'PhD', 'doctorate' = 'phd'. Otherwise null.\n"
        "- For experience: look for patterns like '3+ years', '3 years', 'minimum 5 years'. Extract the number.\n"
        "- For min %: look for patterns like 'minimum 60%', '65% aggregate', '60 percent'. Extract the number.\n"
        "- If any field is not clearly stated, use null for education or 0 for numbers.\n\n"
        f"Job Description:\n{jd_text[:4000]}"
    )
    try:
        resp = _get_client().create(messages=[{"role": "user", "content": prompt}], temperature=0.1, max_tokens=500)
        result = json.loads(_clean_json(resp.choices[0].message.content))
        return {
            "skills": result.get("skills", {}),
            "education_requirement": result.get("education_requirement"),
            "experience_requirement": result.get("experience_requirement", 0),
            "min_academic_percent": result.get("min_academic_percent", 0),
        }
    except Exception as e:
        logger.error(f"extract_jd_requirements failed: {e}")
        return {"skills": {}, "education_requirement": None, "experience_requirement": 0, "min_academic_percent": 0}


def score_answer(question: str, answer: str) -> dict[str, Any]:
    eval_res = evaluate_answer_detailed(question=question, answer=answer)
    return {"score": eval_res.get("score", 0), "feedback": eval_res.get("feedback", "")}
