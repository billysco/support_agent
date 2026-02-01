"""
LLM client using OpenAI-compatible APIs.
"""

import json
import os
from typing import Any

from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

from .schemas import (
    TriageResult, ExtractedFields, ReplyDraft, GuardrailStatus, InputGuardrailStatus,
    Urgency, Category, Sentiment, SupportTicket
)


class OpenAIProvider:
    """Provider for OpenAI-compatible APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o-mini"
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.model = model

        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")

        from openai import OpenAI

        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        self.client = OpenAI(**client_kwargs)

    def complete(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3
        )
        return response.choices[0].message.content or ""

    def complete_json(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)


def get_llm_client() -> OpenAIProvider:
    """
    Factory function to get the OpenAI LLM client.
    Requires OPENAI_API_KEY environment variable.
    """
    return OpenAIProvider()
