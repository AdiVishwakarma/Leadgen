"""Thin Gemini client over REST."""
import time

import httpx

from .config import settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(RuntimeError):
    pass


def generate_text(prompt: str, system: str | None = None, temperature: float = 0.7, retries: int = 3) -> str:
    if not settings.gemini_api_key:
        raise LLMError("GEMINI_API_KEY is not set")

    gen_config: dict = {"temperature": temperature, "maxOutputTokens": 1024}
    model = settings.gemini_model
    # 2.5-flash burns output tokens on hidden "thinking" and truncates the answer.
    if "2.5" in model and "pro" not in model:
        gen_config["thinkingConfig"] = {"thinkingBudget": 0}

    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": gen_config,
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    url = GEMINI_URL.format(model=model)
    headers = {"x-goog-api-key": settings.gemini_api_key}

    last_err = "unknown error"
    for attempt in range(retries):
        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=30)
        except httpx.HTTPError as exc:
            last_err = f"network error: {type(exc).__name__}"
            time.sleep(2**attempt)
            continue

        if resp.status_code in (429, 503):
            last_err = f"rate limited / overloaded ({resp.status_code})"
            time.sleep(4 * (attempt + 1))
            continue
        if resp.status_code != 200:
            raise LLMError(f"Gemini returned {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        try:
            cand = data["candidates"][0]
            parts = cand["content"]["parts"]
        except (KeyError, IndexError):
            raise LLMError(f"Unexpected Gemini response (blocked or empty): {str(data)[:300]}")

        finish = cand.get("finishReason", "STOP")
        if finish != "STOP":
            raise LLMError(f"Gemini stopped early (finishReason={finish})")

        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
        if not text:
            raise LLMError("Gemini returned empty text")
        return text

    raise LLMError(f"Gemini failed after {retries} attempts: {last_err}")