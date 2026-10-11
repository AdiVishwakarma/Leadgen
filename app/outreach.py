"""Outreach message generation. The LLM writes copy only; facts come from our audit data."""
from .config import settings
from .llm import LLMError, generate_text

SYSTEM = """You write short, honest first-contact messages from a freelance web developer to a local business owner.
Rules:
- Use ONLY the facts provided. Never invent details about the business, its customers, or its website.
- Mention at most TWO website issues, in plain non-technical words (no jargon like "viewport" or "meta tags").
- If the business has no website, say that customers searching for them online can't find a site to visit.
- 50 to 80 words. No emojis. No exaggerated claims, no fake urgency, no made-up discounts or statistics.
- - Introduce the sender by first name AND state that they are a freelance web developer, in the first sentence. Do not pretend to be a big company.
- End with one low-pressure question, offering to share a free preview.
- Last line must be: "If this isn't relevant, just tell me and I won't message again."
- Output ONLY the message text. No subject line, no quotes, no explanations."""

LANG_HINT = {
    "english": "Write in simple, polite English.",
    "hinglish": "Write in natural Hinglish (Hindi in Roman script mixed with simple English), polite and respectful.",
}


def clean_reasons(reasons: list[str]) -> list[str]:
    """'+20 not mobile-friendly' -> 'not mobile-friendly'. Drops zero-point filler."""
    out = []
    for r in reasons:
        if r.startswith("+0"):
            continue
        parts = r.split(" ", 1)
        out.append(parts[1] if len(parts) == 2 and parts[0].startswith("+") else r)
    return out


def build_prompt(lead: dict, reasons: list[str], language: str = "english") -> str:
    facts = [
        f"Business name: {lead['name']}",
        f"Type: {lead.get('category') or 'local business'}",
        f"City: {lead.get('city') or 'unknown'}",
        f"Website: {lead.get('website') or 'none found'}",
    ]
    if lead.get("review_count"):
        facts.append(f"Google reviews: {lead['review_count']} (rating {lead.get('rating')})")
    issues = clean_reasons(reasons)
    facts.append("Findings from our automated check: " + ("; ".join(issues) if issues else "none"))

    return (
        f"Sender first name: {settings.sender_name}\n"
        + "\n".join(facts)
        + f"\n\n{LANG_HINT.get(language, LANG_HINT['english'])}\nWrite the message now."
    )


OPT_OUT_MARKER = "won't message again"


def validate_message(text: str) -> str | None:
    words = len(text.split())
    if words < 30:
        return f"too short ({words} words)"
    if words > 130:
        return f"too long ({words} words)"
    if settings.sender_name.lower() not in text.lower():
        return "sender name missing"
    if OPT_OUT_MARKER not in text.lower().replace("\u2019", "'"):
        return "opt-out line missing"
    return None


def generate_message(lead: dict, reasons: list[str], language: str = "english", attempts: int = 3) -> str:
    prompt = build_prompt(lead, reasons, language)
    problem = "no attempt made"
    for _ in range(attempts):
        text = generate_text(prompt, system=SYSTEM, temperature=0.6).strip().strip('"').strip()
        problem = validate_message(text) or ""
        if not problem:
            return text
    raise LLMError(f"Gemini produced an unusable draft after {attempts} tries: {problem}")