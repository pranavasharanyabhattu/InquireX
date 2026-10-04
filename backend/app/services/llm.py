import json
import re
import time

from .. import config

_gemini_client = None
_anthropic_client = None


def available() -> bool:
    key = config.GEMINI_API_KEY if config.LLM_PROVIDER == "gemini" else config.ANTHROPIC_API_KEY
    return bool(key)


def _call_gemini(system: str, user: str) -> str:
    global _gemini_client
    from google import genai
    from google.genai import types
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
    resp = _gemini_client.models.generate_content(
        model=config.LLM_MODEL,
        contents=user,
        config=types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json"),
    )
    return resp.text or ""


def _call_anthropic(system: str, user: str) -> str:
    global _anthropic_client
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise ImportError(
            "Anthropic SDK is not installed. Run `python -m pip install anthropic` to use Anthropic as your LLM provider."
        ) from exc
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = _anthropic_client.messages.create(
        model=config.LLM_MODEL, max_tokens=1200, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text or ""


def complete_json(system: str, user: str) -> tuple[dict | None, str | None]:
    """Ask the model for JSON and return a safe diagnostic when generation fails."""
    if not available():
        return None, "No API key is configured for the selected model provider."
    call = _call_gemini if config.LLM_PROVIDER == "gemini" else _call_anthropic
    for attempt in range(3):
        try:
            text = call(system, user)
            break
        except Exception as e:
            raw_reason = str(e)
            lower_reason = raw_reason.lower()
            quota_exhausted = any(phrase in lower_reason for phrase in (
                "exceeded your current quota",
                "quota_exceeded",
                "check your plan and billing",
                "daily quota has been exceeded",
            ))
            transient = not quota_exhausted and any(code in raw_reason for code in (
                "503", "UNAVAILABLE", "502", "504", "INTERNAL", "429", "RESOURCE_EXHAUSTED", "RATE_LIMIT",
            ))
            if transient and attempt < 2:
                delay = 1.0 * (2 ** attempt)
                print(f"[llm] temporary provider error; retrying in {delay:.0f}s ({attempt + 1}/2)")
                time.sleep(delay)
                continue
            if isinstance(e, ImportError):
                reason = str(e)
            elif "API key not valid" in raw_reason or "API_KEY_INVALID" in raw_reason:
                reason = "Gemini rejected the configured API key. Create a new key in Google AI Studio and replace GEMINI_API_KEY in backend/.env, then restart InquireX."
            elif "401" in raw_reason or "authentication_error" in lower_reason or "invalid_api_key" in lower_reason:
                provider_title = "Gemini" if config.LLM_PROVIDER == "gemini" else "Anthropic"
                key_var = "GEMINI_API_KEY" if config.LLM_PROVIDER == "gemini" else "ANTHROPIC_API_KEY"
                reason = f"{provider_title} rejected the configured API key. Check {key_var} in backend/.env, then restart InquireX."
            elif "no longer available" in raw_reason.lower() or "model not found" in raw_reason.lower() or "not_found_error" in lower_reason:
                provider_title = "Gemini" if config.LLM_PROVIDER == "gemini" else "Anthropic"
                reason = f"The configured model {config.LLM_MODEL} is unavailable. Set LLM_MODEL to a currently supported {provider_title} model in backend/.env and restart InquireX."
            elif quota_exhausted:
                provider_name = "Gemini" if config.LLM_PROVIDER == "gemini" else "The configured model provider"
                reason = (
                    f"{provider_name} reports that this project's API quota is exhausted. Check project usage and model limits "
                    "in Google AI Studio. If you reached a daily limit, wait for its reset; otherwise review the "
                    "project plan, billing status, or model quota. Document search and cited source excerpts still work."
                )
            elif transient:
                reason = f"The model stayed temporarily unavailable or rate-limited after 3 attempts: {type(e).__name__}: {raw_reason}"[:300]
            else:
                reason = f"{type(e).__name__}: {raw_reason}"[:240]
            if config.GEMINI_API_KEY:
                reason = reason.replace(config.GEMINI_API_KEY, "[redacted]")
            if config.ANTHROPIC_API_KEY:
                reason = reason.replace(config.ANTHROPIC_API_KEY, "[redacted]")
            print(f"[llm] {config.LLM_PROVIDER} call failed: {reason}")
            return None, reason
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    text = cleaned.strip()
    if not text:
        return None, "The model returned an empty response."
    try:
        result = json.loads(text)
        return (result, None) if isinstance(result, dict) else (None, "The model response was not a JSON object.")
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                result = json.loads(text[start:end + 1])
                if isinstance(result, dict):
                    return result, None
            except json.JSONDecodeError:
                pass
        return None, "The model response could not be parsed as JSON."
