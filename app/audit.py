"""Website audit: fetch a URL and extract objective quality signals."""
import time
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

# Sites that are not a real website of the business itself.
SOCIAL_HOSTS = (
    "facebook.com",
    "instagram.com",
    "linktr.ee",
    "wa.me",
    "whatsapp.com",
    "justdial.com",
    "indiamart.com",
    "youtube.com",
    "twitter.com",
    "x.com",
)

UA = "Mozilla/5.0 (compatible; LeadAuditBot/0.1)"


def is_social_only(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return any(host == h or host.endswith("." + h) for h in SOCIAL_HOSTS)


def extract_signals(html: str) -> dict:
    """Pure function: HTML -> signals. Easy to unit test."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    viewport = soup.find("meta", attrs={"name": "viewport"})
    text = soup.get_text(" ", strip=True)
    links = [a.get("href", "") for a in soup.find_all("a")]

    return {
        "has_title": bool(title),
        "has_meta_description": bool(meta_desc and meta_desc.get("content", "").strip()),
        "has_viewport": viewport is not None,
        "text_length": len(text),
        "image_count": len(soup.find_all("img")),
        "has_contact_link": any(("tel:" in l or "mailto:" in l or "wa.me" in l) for l in links),
        "has_form": soup.find("form") is not None,
    }


def audit_website(url: str | None) -> dict:
    """Fetch the site and return signals. Never raises; failures become signals."""
    if not url:
        return {"has_website": False}
    if is_social_only(url):
        return {"has_website": False, "social_only": True}

    signals: dict = {"has_website": True, "https": url.lower().startswith("https://")}
    try:
        start = time.perf_counter()
        with httpx.Client(follow_redirects=True, timeout=15, headers={"User-Agent": UA}) as client:
            resp = client.get(url)
        signals["load_seconds"] = round(time.perf_counter() - start, 2)
        signals["status_code"] = resp.status_code
        signals["final_https"] = str(resp.url).startswith("https://")
        if resp.status_code < 400:
            signals.update(extract_signals(resp.text))
        else:
            signals["unreachable"] = True
    except Exception as exc:  # noqa: BLE001 - audit must never crash the pipeline
        signals["unreachable"] = True
        signals["error"] = type(exc).__name__
    return signals
