"""LLM provider abstraction for AI-powered cluster diagnosis."""

import abc
import os

import httpx

_SYSTEM_PROMPT = """\
You are an expert Kubernetes Site Reliability Engineer.
You will be given a JSON snapshot of a Kubernetes cluster's current state,
including pods, events, detected anomalies, and resource usage.

Respond ONLY with a valid JSON object (no markdown fences) with exactly these keys:
{
  "summary":         "<one-paragraph plain-English overview of cluster health>",
  "rootCause":       "<most likely root cause of the most critical issue, or 'No issues detected' if healthy>",
  "kubectlCommands": ["<cmd1>", "<cmd2>", "<cmd3>"]
}

Rules:
- kubectlCommands must contain exactly 3 actionable kubectl commands relevant to the issues found.
- If no issues are detected, provide 3 useful diagnostic/inspection commands anyway.
- Do not include any text outside the JSON object.
"""


class BaseLLMProvider(abc.ABC):
    @abc.abstractmethod
    async def diagnose(self, prompt: str) -> str: ...

    @abc.abstractmethod
    async def complete(self, system: str, messages: list[dict]) -> str: ...

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def model(self) -> str: ...


class AnthropicProvider(BaseLLMProvider):
    _model = "claude-sonnet-4-20250514"

    @property
    def name(self) -> str:
        return "claude"

    @property
    def model(self) -> str:
        return self._model

    async def diagnose(self, prompt: str) -> str:
        return await self._call(_SYSTEM_PROMPT, [{"role": "user", "content": prompt}], 1024)

    async def complete(self, system: str, messages: list[dict]) -> str:
        return await self._call(system, messages, 2048)

    async def _call(self, system: str, messages: list[dict], max_tokens: int) -> str:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": messages,
                },
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]


class OpenAIProvider(BaseLLMProvider):
    _model = "gpt-4o"

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    async def diagnose(self, prompt: str) -> str:
        return await self.complete(_SYSTEM_PROMPT, [{"role": "user", "content": prompt}])

    async def complete(self, system: str, messages: list[dict]) -> str:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        full_messages = [{"role": "system", "content": system}, *messages]
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": full_messages,
                    "max_tokens": 2048,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


class GeminiProvider(BaseLLMProvider):
    _model = "gemini-1.5-pro"

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model

    async def diagnose(self, prompt: str) -> str:
        return await self.complete(_SYSTEM_PROMPT, [{"role": "user", "content": prompt}])

    async def complete(self, system: str, messages: list[dict]) -> str:
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-1.5-pro:generateContent?key={api_key}"
        )
        contents = [
            {
                "role": "user" if m["role"] == "user" else "model",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
        ]
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": contents,
                    "generationConfig": {"maxOutputTokens": 2048},
                },
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


class OllamaProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self._base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self._model_name = os.environ.get("OLLAMA_MODEL", "llama3")

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model_name

    async def diagnose(self, prompt: str) -> str:
        return await self.complete(_SYSTEM_PROMPT, [{"role": "user", "content": prompt}])

    async def complete(self, system: str, messages: list[dict]) -> str:
        full_messages = [{"role": "system", "content": system}, *messages]
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                headers={"Content-Type": "application/json"},
                json={
                    "model": self._model_name,
                    "messages": full_messages,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]


class AzureOpenAIProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self._deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    @property
    def name(self) -> str:
        return "azure"

    @property
    def model(self) -> str:
        return self._deployment

    async def diagnose(self, prompt: str) -> str:
        return await self.complete(_SYSTEM_PROMPT, [{"role": "user", "content": prompt}])

    async def complete(self, system: str, messages: list[dict]) -> str:
        api_key = os.environ.get("AZURE_OPENAI_KEY", "")
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        url = (
            f"{endpoint}/openai/deployments/{self._deployment}"
            f"/chat/completions?api-version=2024-02-01"
        )
        full_messages = [{"role": "system", "content": system}, *messages]
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                headers={
                    "api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._deployment,
                    "messages": full_messages,
                    "max_tokens": 2048,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


def get_llm_provider() -> BaseLLMProvider:
    provider = os.environ.get("LLM_PROVIDER", "claude").lower()
    if provider == "claude":
        return AnthropicProvider()
    if provider == "openai":
        return OpenAIProvider()
    if provider == "gemini":
        return GeminiProvider()
    if provider == "ollama":
        return OllamaProvider()
    if provider == "azure":
        return AzureOpenAIProvider()
    raise ValueError(
        f"Unknown LLM provider '{provider}'. "
        "Set LLM_PROVIDER to one of: claude, openai, gemini, ollama, azure"
    )
