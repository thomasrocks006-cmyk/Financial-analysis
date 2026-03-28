"""Base agent class — shared infrastructure for all LLM agents."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, TypeVar, Generic

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    """Raised when an agent returns output that cannot be parsed into structured JSON."""
    pass


class AgentResult(BaseModel):
    """Standard result wrapper for any agent call."""
    agent_name: str
    run_id: str
    success: bool
    raw_response: str = ""
    parsed_output: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    # Field with default_factory so every instance gets its OWN timestamp;
    # a bare `= datetime.now(...)` would evaluate ONCE at class definition time.
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    prompt_hash: str = ""
    retries_used: int = 0


class BaseAgent(ABC):
    """Base class for all LLM reasoning agents.

    Each agent is a callable module with:
    - system prompt
    - input schema
    - output schema
    - retry / validation wrapper
    """

    # ACT-S10-3: subclasses may declare keys that must be present in parsed output
    _REQUIRED_OUTPUT_KEYS: list[str] = []

    def __init__(
        self,
        name: str,
        model: str = "claude-opus-4-6",
        temperature: float = 0.2,
        max_retries: int = 3,
        prompts_dir: Path | None = None,
    ):
        self.name = name
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self.prompts_dir = prompts_dir
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Load system prompt from file or use built-in."""
        if self.prompts_dir:
            prompt_file = self.prompts_dir / f"{self.name}.md"
            if prompt_file.exists():
                return prompt_file.read_text()
        return self.default_system_prompt()

    @abstractmethod
    def default_system_prompt(self) -> str:
        """Return the default system prompt for this agent."""
        ...

    @property
    def prompt_hash(self) -> str:
        return hashlib.sha256(self._system_prompt.encode()).hexdigest()[:16]

    @property
    def version(self) -> str:
        return f"v8.0-{self.prompt_hash[:8]}"

    # Phase 7.4 — Provider fallback chain.
    # Tried in order on RateLimitError/ServiceUnavailableError.
    _FALLBACK_CHAIN: list[str] = ["claude-opus-4-6", "gpt-4o", "gemini-1.5-pro"]

    async def call_llm(
        self, messages: list[dict[str, str]], response_format: type | None = None
    ) -> str:
        """Call the LLM with retry logic and provider fallback.

        Primary: configured model.
        Fallback chain (Phase 7.4): claude-opus-4-6 → gpt-4o → gemini-1.5-pro
        on rate-limit or quota errors only.  Other errors are NOT silently swallowed.
        """
        import os

        providers_to_try: list[tuple[str, str]] = []

        # Build the ordered list: primary model first, then fallbacks that differ
        primary = self.model
        models_order = [primary] + [m for m in self._FALLBACK_CHAIN if m != primary]

        for model in models_order:
            if model.startswith("claude"):
                providers_to_try.append((model, "anthropic"))
            elif model.startswith("gemini"):
                providers_to_try.append((model, "gemini"))
            else:
                providers_to_try.append((model, "openai"))

        last_exc: Exception | None = None

        for model_name, provider in providers_to_try:
            try:
                if provider == "anthropic":
                    result = await self._call_anthropic(
                        messages, os.getenv("ANTHROPIC_API_KEY", ""), model_override=model_name
                    )
                elif provider == "gemini":
                    result = await self._call_gemini(
                        messages, os.getenv("GOOGLE_API_KEY", ""), model_override=model_name
                    )
                else:
                    result = await self._call_openai(
                        messages,
                        os.getenv("OPENAI_API_KEY", ""),
                        response_format,
                        model_override=model_name,
                    )

                if model_name != primary:
                    logger.warning(
                        "%s: used fallback model '%s' (primary '%s' unavailable)",
                        self.name, model_name, primary,
                    )

                return result

            except Exception as exc:
                exc_str = str(exc).lower()
                # Only fall back for rate-limit / quota / service-unavailable errors
                is_retryable = any(kw in exc_str for kw in (
                    "rate limit", "rate_limit", "ratelimit",
                    "quota", "overloaded", "service unavailable",
                    "503", "529", "too many requests", "429",
                ))
                if is_retryable:
                    logger.warning(
                        "%s: provider '%s' / model '%s' rate-limited — trying next fallback: %s",
                        self.name, provider, model_name, exc,
                    )
                    last_exc = exc
                    continue
                # Non-retryable error — raise immediately, do not try fallbacks
                raise

        raise RuntimeError(
            f"{self.name}: all LLM fallback models exhausted. Last error: {last_exc}"
        )

    async def _call_anthropic(
        self,
        messages: list[dict[str, str]],
        api_key: str,
        model_override: str | None = None,
    ) -> str:
        """Call Anthropic Claude API."""
        try:
            import anthropic as _anthropic
        except ImportError:
            logger.warning("anthropic package not installed — returning mock response")
            return json.dumps({"mock": True, "agent": self.name})

        # Extract system prompt from messages if present
        system = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_messages.append(m)

        model = model_override or self.model
        client = _anthropic.AsyncAnthropic(api_key=api_key)

        for attempt in range(1, self.max_retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "max_tokens": 8192,
                    "messages": user_messages,
                    "temperature": self.temperature,
                }
                if system:
                    kwargs["system"] = system

                response = await client.messages.create(**kwargs)
                return response.content[0].text
            except Exception as exc:
                logger.warning(
                    "%s: Anthropic attempt %d failed: %s", self.name, attempt, exc
                )
                if attempt == self.max_retries:
                    raise

        return ""

    async def _call_openai(
        self,
        messages: list[dict[str, str]],
        api_key: str,
        response_format: type | None = None,
        model_override: str | None = None,
    ) -> str:
        """Call OpenAI API."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.warning("OpenAI not installed — returning mock response")
            return json.dumps({"mock": True, "agent": self.name})

        model = model_override or self.model
        client = AsyncOpenAI(api_key=api_key)

        for attempt in range(1, self.max_retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": self.temperature,
                }
                if response_format:
                    kwargs["response_format"] = response_format

                response = await client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            except Exception as exc:
                logger.warning(
                    "%s: OpenAI attempt %d failed: %s", self.name, attempt, exc
                )
                if attempt == self.max_retries:
                    raise

        return ""

    async def _call_gemini(
        self,
        messages: list[dict[str, str]],
        api_key: str,
        model_override: str | None = None,
    ) -> str:
        """Call Google Gemini API (Phase 7.4 fallback provider).

        Uses google-generativeai if installed; falls back to a REST call otherwise.
        """
        model = model_override or self.model
        try:
            import google.generativeai as genai  # type: ignore[import]
        except ImportError:
            # Fallback: raw REST with httpx / requests
            logger.warning("google-generativeai not installed — using REST fallback")
            return await self._call_gemini_rest(messages, api_key, model)

        genai.configure(api_key=api_key)
        g_model = genai.GenerativeModel(model)

        # Flatten messages to text prompt (Gemini basic API)
        text_parts = "\n".join(
            f"[{m['role'].upper()}]\n{m['content']}" for m in messages
        )

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await g_model.generate_content_async(text_parts)
                return response.text
            except Exception as exc:
                logger.warning(
                    "%s: Gemini attempt %d failed: %s", self.name, attempt, exc
                )
                if attempt == self.max_retries:
                    raise

        return ""

    async def _call_gemini_rest(
        self,
        messages: list[dict[str, str]],
        api_key: str,
        model: str,
    ) -> str:
        """Minimal Gemini REST fallback — no extra SDK required."""
        import asyncio
        import urllib.request
        import urllib.error

        text_parts = "\n".join(
            f"[{m['role'].upper()}]\n{m['content']}" for m in messages
        )
        payload = json.dumps({"contents": [{"parts": [{"text": text_parts}]}]}).encode()
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )

        def _blocking_request() -> str:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read())
                return body["candidates"][0]["content"]["parts"][0]["text"]

        return await asyncio.get_event_loop().run_in_executor(None, _blocking_request)

    def build_messages(self, user_content: str) -> list[dict[str, str]]:
        """Build standard message list with system prompt."""
        return [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_content},
        ]

    async def run(self, run_id: str, inputs: dict[str, Any]) -> AgentResult:
        """Execute the agent with structured output enforcement.

        Retries on StructuredOutputError up to max_retries times.
        """
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                user_content = self.format_input(inputs)
                messages = self.build_messages(user_content)
                raw = await self.call_llm(messages)
                parsed = self.parse_output(raw)
                return AgentResult(
                    agent_name=self.name,
                    run_id=run_id,
                    success=True,
                    raw_response=raw,
                    parsed_output=parsed,
                    prompt_hash=self.prompt_hash,
                    retries_used=attempt - 1,
                )
            except StructuredOutputError as exc:
                logger.warning(
                    "%s: structured output parse failed (attempt %d/%d): %s",
                    self.name, attempt, self.max_retries, exc,
                )
                last_error = str(exc)
                if attempt == self.max_retries:
                    return AgentResult(
                        agent_name=self.name,
                        run_id=run_id,
                        success=False,
                        error=f"Structured output failed after {self.max_retries} attempts: {last_error}",
                        prompt_hash=self.prompt_hash,
                        retries_used=attempt,
                    )
            except Exception as exc:
                logger.error("%s failed: %s", self.name, exc)
                return AgentResult(
                    agent_name=self.name,
                    run_id=run_id,
                    success=False,
                    error=str(exc),
                    prompt_hash=self.prompt_hash,
                    retries_used=attempt - 1,
                )
        # Should not reach here, but safety net
        return AgentResult(
            agent_name=self.name,
            run_id=run_id,
            success=False,
            error=f"Exhausted retries: {last_error}",
            prompt_hash=self.prompt_hash,
        )

    def format_input(self, inputs: dict[str, Any]) -> str:
        """Format structured inputs into the user message. Override as needed."""
        return json.dumps(inputs, indent=2, default=str)

    def _validate_output_quality(self, result: dict) -> list[str]:  # ACT-S10-3
        """Warn (non-fatal) if any *_REQUIRED_OUTPUT_KEYS* are missing or empty.

        Returns a list of warning strings; an empty list means all keys are
        present and non-empty.  Never raises.
        """
        warnings_list: list[str] = []
        for key in self._REQUIRED_OUTPUT_KEYS:
            val = result.get(key)
            if val is None or val == "" or val == [] or val == {}:
                msg = (
                    f"Agent '{self.name}' output missing/empty required key: '{key}'"
                )
                warnings_list.append(msg)
                logger.warning(msg)
        return warnings_list

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        """Parse raw LLM response into structured output.

        Fail closed: malformed JSON raises a StructuredOutputError.

        Strategies attempted in order:
        1. Extract JSON from a markdown ```json ... ``` fence (anywhere in response,
           handles models that add a preamble before the code block).
        2. Direct ``json.loads`` on the full response (already bare JSON).
        3. Locate the first ``{`` or ``[`` and use ``raw_decode`` to skip LLM
           preamble text.  Raises StructuredOutputError on all failures.
        """
        cleaned = raw_response.strip()

        # Strategy 1: markdown code fence (handles preamble + fence)
        fence_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)```", cleaned)
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                _parsed = json.loads(candidate)
                if isinstance(_parsed, dict):
                    self._validate_output_quality(_parsed)  # ACT-S10-3
                return _parsed
            except json.JSONDecodeError:
                pass  # fence present but content malformed — fall through

        # Strategy 2: bare JSON (full response is already valid JSON)
        try:
            _parsed = json.loads(cleaned)
            if isinstance(_parsed, dict):
                self._validate_output_quality(_parsed)  # ACT-S10-3
            return _parsed
        except json.JSONDecodeError:
            pass

        # Strategy 3: find first '{' or '[' and raw_decode (skips LLM preamble)
        _decoder = json.JSONDecoder()
        for start_char in ("{", "["):
            idx = cleaned.find(start_char)
            if idx != -1:
                try:
                    obj, _ = _decoder.raw_decode(cleaned, idx)
                    if isinstance(obj, (dict, list)):
                        logger.warning(
                            "%s: stripped %d-char LLM preamble before JSON",
                            self.name, idx,
                        )
                        if isinstance(obj, dict):
                            self._validate_output_quality(obj)  # ACT-S10-3
                        return obj
                except json.JSONDecodeError:
                    pass

        raise StructuredOutputError(
            f"Agent '{self.name}' returned malformed JSON: no valid JSON found. "
            f"First 200 chars: {raw_response[:200]}"
        )
