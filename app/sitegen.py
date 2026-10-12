"""Landing page generator: two light, minimal layouts.

  card   - printed-menu-card layout (restaurants, salons)
  clinic - airy two-column layout (dentists, clinics, everything else)

Design rule: the page only states facts we actually have (name, category, rating, reviews,
address, phone). The LLM writes the short about-text only, and everything has a plain fallback,
so a Gemini outage never blocks the pipeline.
"""
import html
import json
import re
from string import Template
from urllib.parse import quote

from .config import settings
from .llm import LLMError, generate_text

# (keywords found in category/name, layout, palette, call-button text)
THEMES = [
    (("restaurant", "cafe", "café", "bakery", "dhaba", "sweet", "biryani", "kitchen", "pizza", "food", "eatery", "tiffin", "mess"),
     "card", dict(bg="#EEF3EC", paper="#FFFFFF", ink="#16281D", accent="#245C3A"), "Call to book a table"),
    (("salon", "spa", "beauty", "parlour", "parlor", "makeup", "barber", "hair", "nail"),
     "card", dict(bg="#F8EEEE", paper="#FFFFFF", ink="#34202A", accent="#9B4560"), "Call to book a visit"),
    (("dentist", "dental", "clinic", "doctor", "hospital", "physio", "pharmacy", "diagnostic", "ortho", "skin"),
     "clinic", dict(bg="#FFFFFF", tint="#E6F4F3", ink="#0F2F3A", muted="#47636B", accent="#0B7F86"), "Call to book an appointment"),
]
DEFAULT_THEME = ("clinic", dict(bg="#FFFFFF", tint="#EDF1F7", ink="#14233B", muted="#4B5B73", accent="#2F5D9B"), "Call us")

COPY_SYSTEM = """You write website copy for a demo landing page of a small local business.
Return ONLY valid JSON with exactly these keys: "tagline", "about".
Rules:
- tagline: max 9 words. about: exactly 2 sentences, max 40 words.
- Use ONLY the facts given. Never invent years in business, awards, prices, menu items, services, staff, owners, or claims like "best" or "number one".
- Warm, simple, plain English. No emojis."""


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len].strip("-")) or "business"


def pick_theme(lead: dict) -> dict:
    hay = f"{lead.get('category') or ''} {lead.get('name') or ''} ".lower()
    for keywords, layout, palette, cta in THEMES:
        if any(k in hay for k in keywords):
            return {"layout": layout, "cta": cta, **palette}
    layout, palette, cta = DEFAULT_THEME
    return {"layout": layout, "cta": cta, **palette}


def fallback_copy(lead: dict) -> dict:
    cat = (lead.get("category") or "local business").lower()
    city = lead.get("city") or "your city"
    about = f"{lead['name']} is a {cat} in {city}."
    if lead.get("review_count") and lead.get("rating"):
        about += f" Customers have rated it {lead['rating']} out of 5 across {lead['review_count']} Google reviews."
    return {"tagline": f"Your local {cat} in {city}", "about": about}


def _parse_copy(raw: str) -> dict | None:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if not all(isinstance(data.get(k), str) and data[k].strip() for k in ("tagline", "about")):
        return None
    if len(data["about"].split()) > 70 or len(data["tagline"].split()) > 14:
        return None
    return {k: data[k].strip() for k in ("tagline", "about")}


def generate_copy(lead: dict) -> dict:
    facts = [f"Name: {lead['name']}", f"Type: {lead.get('category') or 'local business'}", f"City: {lead.get('city')}"]
    if lead.get("review_count") and lead.get("rating"):
        facts.append(f"Google rating: {lead['rating']} from {lead['review_count']} reviews")
    try:
        parsed = _parse_copy(generate_text("\n".join(facts), system=COPY_SYSTEM, temperature=0.5))
    except LLMError:
        parsed = None
    return parsed or fallback_copy(lead)


# ------------------------------------------------------------------ layout 1: card
CARD = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>$name</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:wght@400;500;600&family=Figtree:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root { --bg: $bg; --paper: $paper; --ink: $ink; --accent: $accent; }
  * { box-sizing: border-box; margin: 0; }
  html { -webkit-text-size-adjust: 100%; }
  body { font-family: 'Figtree', system-ui, sans-serif; background: var(--bg); color: var(--ink); line-height: 1.6; }
  a:focus-visible { outline: 3px solid var(--accent); outline-offset: 3px; }
  .demo { font-size: 13px; line-height: 1.4; padding: 10px 16px; text-align: center; background: var(--ink); color: #fff; }
  .card { max-width: 660px; margin: clamp(20px, 5vw, 56px) auto; padding: clamp(40px, 8vw, 72px) clamp(24px, 6vw, 56px);
          background: var(--paper); border: 1px solid var(--accent); position: relative; text-align: center; }
  .card::before { content: ""; position: absolute; inset: 8px; border: 1px solid var(--accent); opacity: .3; pointer-events: none; }
  h1 { font-family: 'Newsreader', Georgia, serif; font-weight: 500; font-size: clamp(2.6rem, 10vw, 4.4rem); line-height: 1.05; letter-spacing: -.01em; overflow-wrap: anywhere; }
  .cat { margin-top: 12px; font-size: 1.05rem; opacity: .75; }
  .orn { display: flex; align-items: center; gap: 14px; margin: 26px auto; max-width: 240px; color: var(--accent); }
  .orn::before, .orn::after { content: ""; flex: 1; height: 1px; background: currentColor; opacity: .6; }
  .orn i { width: 7px; height: 7px; background: currentColor; transform: rotate(45deg); }
  .about { max-width: 30rem; margin: 0 auto; font-size: 1.08rem; opacity: .88; }
  dl { margin: 34px 0 8px; text-align: left; }
  dl div { display: flex; align-items: baseline; gap: 10px; padding: 9px 0; }
  dt { font-weight: 500; }
  dl i { flex: 1; border-bottom: 2px dotted var(--accent); opacity: .45; transform: translateY(-4px); }
  dd { font-family: 'Newsreader', Georgia, serif; font-size: 1.35rem; font-weight: 500; color: var(--accent); }
  address { font-style: normal; margin: 22px auto 0; opacity: .8; max-width: 28rem; }
  .row { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-top: 30px; }
  .btn { display: inline-block; padding: 14px 26px; font-weight: 600; text-decoration: none; border: 1.5px solid var(--accent); color: var(--accent); border-radius: 2px; }
  .btn.fill { background: var(--accent); color: #fff; }
  .note { margin-top: 34px; font-size: 13px; opacity: .55; }
</style>
</head>
<body>
<div class="demo">Demo preview by $sender, freelance web developer. This is not the official website of $name.</div>
<main class="card">
  <h1>$name</h1>
  <p class="cat">$category$city_suffix</p>
  <div class="orn"><i></i></div>
  <p class="about">$about</p>
  $facts
  $address_block
  <div class="row">$call_btn<a class="btn" href="$maps_url" target="_blank" rel="noopener">Get directions</a></div>
  <p class="note">Demo layout. Menu, photos and booking can be added in the full site.</p>
</main>
</body>
</html>
""")

# ------------------------------------------------------------------ layout 2: clinic
CLINIC = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>$name</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root { --bg: $bg; --tint: $tint; --ink: $ink; --muted: $muted; --accent: $accent; }
  * { box-sizing: border-box; margin: 0; }
  html { -webkit-text-size-adjust: 100%; }
  body { font-family: 'Plus Jakarta Sans', system-ui, sans-serif; background: var(--bg); color: var(--ink); line-height: 1.65; }
  a:focus-visible { outline: 3px solid var(--accent); outline-offset: 3px; }
  .demo { font-size: 13px; line-height: 1.4; padding: 10px 16px; text-align: center; background: var(--ink); color: #fff; }
  .bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px clamp(20px, 5vw, 64px); border-bottom: 1px solid var(--tint); }
  .brand { font-weight: 700; letter-spacing: -.01em; }
  .btn { display: inline-block; padding: 13px 22px; border-radius: 999px; font-weight: 600; text-decoration: none; border: 1.5px solid var(--accent); color: var(--accent); }
  .btn.fill { background: var(--accent); color: #fff; }
  .btn.small { padding: 9px 16px; font-size: .92rem; }
  .wrap { max-width: 1040px; margin: 0 auto; padding: 0 clamp(20px, 5vw, 40px); }
  .hero { display: grid; grid-template-columns: 1.25fr .75fr; gap: clamp(28px, 6vw, 72px); align-items: center; padding: clamp(40px, 8vw, 96px) 0 clamp(32px, 6vw, 64px); }
  h1 { font-weight: 700; font-size: clamp(2.2rem, 5.6vw, 4rem); line-height: 1.08; letter-spacing: -.03em; overflow-wrap: anywhere; }
  .kind { margin-top: 14px; font-size: 1.15rem; color: var(--muted); font-weight: 500; }
  .about { margin-top: 22px; max-width: 32rem; color: var(--muted); font-size: 1.08rem; }
  .row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 30px; }
  .visit { background: var(--tint); border-radius: 22px; padding: clamp(24px, 4vw, 36px); }
  .visit h2 { font-size: 1.05rem; font-weight: 700; }
  .visit address { font-style: normal; margin-top: 10px; color: var(--muted); }
  .visit .tel { display: block; margin-top: 18px; font-size: 1.5rem; font-weight: 700; letter-spacing: -.01em; color: var(--ink); text-decoration: none; }
  .visit .maps { display: inline-block; margin-top: 16px; font-weight: 600; color: var(--accent); }
  .stats { display: flex; flex-wrap: wrap; border-top: 1px solid var(--tint); border-bottom: 1px solid var(--tint); }
  .stats div { flex: 1 1 180px; padding: 26px 0 26px clamp(0px, 3vw, 28px); }
  .stats div + div { border-left: 1px solid var(--tint); }
  .stats b { display: block; font-size: 1.9rem; font-weight: 700; letter-spacing: -.02em; color: var(--accent); line-height: 1.2; }
  .stats span { color: var(--muted); font-size: .95rem; }
  .note { padding: 28px 0 48px; font-size: 13px; color: var(--muted); }
  @media (max-width: 780px) {
    .hero { grid-template-columns: 1fr; }
    .stats div + div { border-left: 0; border-top: 1px solid var(--tint); padding-left: 0; }
    .stats div { padding-left: 0; }
  }
</style>
</head>
<body>
<div class="demo">Demo preview by $sender, freelance web developer. This is not the official website of $name.</div>
<header class="bar"><span class="brand">$name</span>$bar_call</header>
<main class="wrap">
  <section class="hero">
    <div>
      <h1>$name</h1>
      <p class="kind">$category$city_suffix</p>
      <p class="about">$about</p>
      <div class="row">$call_btn<a class="btn" href="$maps_url" target="_blank" rel="noopener">Get directions</a></div>
    </div>
    <aside class="visit">
      <h2>Visit us</h2>
      $address_block
      $tel_block
      <a class="maps" href="$maps_url" target="_blank" rel="noopener">Open in Maps</a>
    </aside>
  </section>
  $stats
  <p class="note">Demo layout. Photos, services and online booking can be added in the full site.</p>
</main>
</body>
</html>
""")


def render_site(lead: dict, copy: dict) -> str:
    e = lambda v: html.escape(str(v or ""), quote=True)  # noqa: E731 - everything user/LLM-derived is escaped
    theme = pick_theme(lead)

    phone = lead.get("phone")
    tel = re.sub(r"[^\d+]", "", phone or "")
    city_suffix = f", {e(lead['city'])}" if lead.get("city") else ""

    maps_q = quote(f"{lead['name']} {lead.get('address') or lead.get('city') or ''}")
    maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_q}"
    if lead.get("place_id"):
        maps_url += f"&query_place_id={quote(lead['place_id'])}"

    common = dict(
        name=e(lead["name"]),
        category=e(lead.get("category") or "Local business"),
        city_suffix=city_suffix,
        about=e(copy["about"]),
        sender=e(settings.sender_name),
        maps_url=e(maps_url),
        bg=theme["bg"],
        ink=theme["ink"],
        accent=theme["accent"],
    )
    address_block = f"<address>{e(lead['address'])}</address>" if lead.get("address") else ""
    call_btn = f'<a class="btn fill" href="tel:{e(tel)}">{e(theme["cta"])}</a>' if tel else ""

    if theme["layout"] == "card":
        rows = []
        if lead.get("rating"):
            rows.append(("Rating", f"{lead['rating']} of 5"))
        if lead.get("review_count"):
            rows.append(("Google reviews", lead["review_count"]))
        if lead.get("city"):
            rows.append(("Find us in", lead["city"]))
        if phone:
            rows.append(("Call", phone))
        facts = "<dl>" + "".join(f"<div><dt>{e(k)}</dt><i></i><dd>{e(v)}</dd></div>" for k, v in rows) + "</dl>" if rows else ""
        return CARD.substitute(**common, paper=theme["paper"], facts=facts, address_block=address_block, call_btn=call_btn)

    stats = []
    if lead.get("rating"):
        stats.append(f"<div><b>{e(lead['rating'])} / 5</b><span>Rating on Google</span></div>")
    if lead.get("review_count"):
        stats.append(f"<div><b>{e(lead['review_count'])}</b><span>Reviews on Google</span></div>")
    if lead.get("city"):
        stats.append(f"<div><b>{e(lead['city'])}</b><span>Find us here</span></div>")
    return CLINIC.substitute(
        **common,
        tint=theme["tint"],
        muted=theme["muted"],
        address_block=address_block,
        tel_block=f'<a class="tel" href="tel:{e(tel)}">{e(phone)}</a>' if tel else "",
        call_btn=call_btn,
        bar_call=f'<a class="btn fill small" href="tel:{e(tel)}">Call</a>' if tel else "",
        stats=f'<section class="stats">{"".join(stats)}</section>' if stats else "",
    )


def build_site(lead: dict) -> str:
    return render_site(lead, generate_copy(lead))