"""Base agent class — shared infrastructure for all LLM agents."""

from __future__ import annotations

import hashlib
import json
import logging
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

    async def call_llm(
        self, messages: list[dict[str, str]], response_format: type | None = None
    ) -> str:
        """Call the LLM with retry logic. Supports Anthropic Claude and OpenAI."""
        import os

        is_anthropic = self.model.startswith("claude")

        if is_anthropic:
            return await self._call_anthropic(messages, os.getenv("ANTHROPIC_API_KEY", ""))
        else:
            return await self._call_openai(messages, os.getenv("OPENAI_API_KEY", ""), response_format)

    async def _call_anthropic(self, messages: list[dict[str, str]], api_key: str) -> str:
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

        client = _anthropic.AsyncAnthropic(api_key=api_key)

        for attempt in range(1, self.max_retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.model,
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
    ) -> str:
        """Call OpenAI API."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.warning("OpenAI not installed — returning mock response")
            return json.dumps({"mock": True, "agent": self.name})

        client = AsyncOpenAI(api_key=api_key)

        for attempt in range(1, self.max_retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.model,
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

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        """Parse raw LLM response into structured output.

        Fail closed: malformed JSON raises a StructuredOutputError
        rather than silently degrading to raw_text.
        """
        # Strip markdown code fences if present
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json or ```) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise StructuredOutputError(
                f"Agent '{self.name}' returned malformed JSON: {exc}. "
                f"First 200 chars: {raw_response[:200]}"
            ) from exc
