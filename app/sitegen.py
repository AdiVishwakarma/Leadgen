"""Landing page generator: two light layouts, one per kind of business.

  card   - restaurants, cafes, salons: big serif name + a round "plate" with the Google rating
  clinic - dentists, clinics, everything else: calm hero with a smile-curve edge + appointment card

Design rule: the page only states facts we actually have (name, category, rating, reviews,
address, phone). The LLM writes the short tagline/about text only, and everything has a plain
fallback, so a Gemini outage never blocks the pipeline.
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
     "card", dict(bg="#FFFDF9", tint="#EFF4E9", ink="#17301F", accent="#B3261E", star="#E9A93B", plate="#FFF1D2"), "Call to book a table"),
    (("salon", "spa", "beauty", "parlour", "parlor", "makeup", "barber", "hair", "nail"),
     "card", dict(bg="#FFFCFC", tint="#F8ECEF", ink="#3A2230", accent="#A23B5C", star="#D9A441", plate="#F9E3E9"), "Call to book a visit"),
    (("dentist", "dental", "clinic", "doctor", "hospital", "physio", "pharmacy", "diagnostic", "ortho", "skin"),
     "clinic", dict(bg="#FFFFFF", tint="#E6F4F3", ink="#0F2F3A", muted="#47636B", accent="#0B7F86", star="#F0A71F"), "Call to book an appointment"),
]
DEFAULT_THEME = ("clinic", dict(bg="#FFFFFF", tint="#EDF1F7", ink="#14233B", muted="#4B5B73", accent="#2F5D9B", star="#F0A71F"), "Call us")

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


# Shared CSS for the rating stars (grey stars with a coloured copy clipped to rating/5 on top)
STARS_CSS = """
  .stars { position: relative; display: inline-block; width: 6em; height: 1.2em; line-height: 0; vertical-align: middle; }
  .stars svg { display: block; width: 6em; height: 1.2em; }
  .stars .fill { position: absolute; left: 0; top: 0; width: var(--r); overflow: hidden; color: var(--star); font-style: normal; }
"""

# ------------------------------------------------------------------ layout 1: card (restaurants, salons)
CARD = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>$name</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;1,9..144,400&display=swap" rel="stylesheet">
<style>
  :root { --bg: $bg; --tint: $tint; --ink: $ink; --accent: $accent; --star: $star; --plate: $plate_bg; }
  * { box-sizing: border-box; margin: 0; }
  html { -webkit-text-size-adjust: 100%; scroll-behavior: smooth; }
  body { font-family: 'DM Sans', system-ui, sans-serif; background: var(--bg); color: var(--ink); line-height: 1.6; padding-bottom: var(--dock-pad, 0); }
  a:focus-visible { outline: 3px solid var(--accent); outline-offset: 3px; }
  .demo { font-size: 13px; line-height: 1.4; padding: 10px 16px; text-align: center; background: var(--ink); color: #fff; }
  .serif { font-family: 'Fraunces', Georgia, serif; }
  $stars_css
  .hero { max-width: 1100px; margin: 0 auto; display: grid; grid-template-columns: 1.1fr .9fr; gap: clamp(24px, 5vw, 72px); align-items: center;
          padding: clamp(40px, 8vw, 96px) clamp(20px, 5vw, 40px) clamp(48px, 8vw, 88px); }
  .hero.solo { grid-template-columns: 1fr; max-width: 760px; }
  .pill { display: inline-block; padding: 6px 15px; border: 1px solid var(--accent); color: var(--accent); border-radius: 999px; font-weight: 500; font-size: .95rem; }
  h1 { font-family: 'Fraunces', Georgia, serif; font-weight: 600; font-size: clamp(2.9rem, 8.4vw, 5.9rem); line-height: .98; letter-spacing: -.025em; margin-top: 22px; overflow-wrap: anywhere; }
  .tag { font-family: 'Fraunces', Georgia, serif; font-style: italic; font-weight: 400; font-size: clamp(1.3rem, 2.8vw, 1.75rem); line-height: 1.3; margin-top: 20px; max-width: 26rem; }
  .about { margin-top: 18px; max-width: 30rem; font-size: 1.08rem; color: rgba(0,0,0,.68); }
  .row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 30px; }
  .btn { display: inline-block; padding: 14px 26px; border-radius: 999px; font-weight: 700; text-decoration: none; border: 1.5px solid var(--accent); color: var(--accent); background: transparent; }
  .btn.fill { background: var(--accent); color: #fff; }
  .plate-wrap { padding: 32px; }
  .plate { position: relative; aspect-ratio: 1; width: 100%; max-width: 400px; margin: 0 auto; border-radius: 50%; background: var(--plate);
           display: grid; place-content: center; text-align: center; padding: 10%;
           outline: 1.5px solid var(--accent); outline-offset: 12px; }
  .plate::after { content: ""; position: absolute; inset: -28px; border-radius: 50%; border: 1.5px dotted var(--accent); opacity: .5; pointer-events: none; }
  .plate .small { font-size: 1rem; font-weight: 500; }
  .score { font-family: 'Fraunces', Georgia, serif; font-weight: 600; font-size: clamp(4.2rem, 13vw, 6.6rem); line-height: 1; letter-spacing: -.03em; color: var(--accent); margin: 4px 0 8px; }
  .plate .stars { font-size: 1.6rem; margin-bottom: 12px; justify-self: center; }
  .city { font-family: 'Fraunces', Georgia, serif; font-weight: 600; font-size: clamp(2rem, 7vw, 3.2rem); line-height: 1.05; color: var(--accent); margin-top: 6px; overflow-wrap: anywhere; }
  .find { background: var(--tint); }
  .find .in { max-width: 1100px; margin: 0 auto; display: grid; grid-template-columns: .8fr 1.2fr; gap: clamp(24px, 5vw, 64px); padding: clamp(40px, 7vw, 80px) clamp(20px, 5vw, 40px); align-items: start; }
  .find h2 { font-family: 'Fraunces', Georgia, serif; font-weight: 600; font-size: clamp(1.9rem, 4.6vw, 2.8rem); line-height: 1.05; letter-spacing: -.02em; }
  .find address { font-style: normal; margin-top: 16px; font-size: 1.05rem; color: rgba(0,0,0,.7); }
  .find .tel { display: block; margin-top: 18px; font-family: 'Fraunces', Georgia, serif; font-weight: 600; font-size: 1.7rem; color: var(--accent); text-decoration: none; }
  .map { width: 100%; height: 340px; border: 0; border-radius: 18px; background: #fff; }
  .note { max-width: 1100px; margin: 0 auto; padding: 24px clamp(20px, 5vw, 40px) 40px; font-size: 13px; color: rgba(0,0,0,.55); }
  .dock { display: none; }
  @media (max-width: 800px) {
    :root { --dock-pad: 76px; }
    .hero, .find .in { grid-template-columns: 1fr; }
    .hero .row { display: none; }
    .plate-wrap { order: -1; padding: 28px 28px 8px; }
    .plate { max-width: 300px; }
    .dock { display: flex; gap: 10px; position: fixed; left: 0; right: 0; bottom: 0; padding: 12px 16px; background: var(--bg); border-top: 1px solid rgba(0,0,0,.1); z-index: 5; }
    .dock .btn { flex: 1; text-align: center; padding: 13px 10px; }
  }
</style>
</head>
<body>
<div class="demo">Demo preview by $sender, freelance web developer. This is not the official website of $name.</div>
<main>
  <section class="hero$solo">
    <div>
      <span class="pill">$category$city_suffix</span>
      <h1>$name</h1>
      <p class="tag">$tagline</p>
      <p class="about">$about</p>
      <div class="row">$call_btn<a class="btn" href="$maps_url" target="_blank" rel="noopener">Get directions</a></div>
    </div>
    $plate
  </section>
  <section class="find">
    <div class="in">
      <div>
        <h2>Find us</h2>
        $address_block
        $tel_block
      </div>
      $map_block
    </div>
  </section>
  <p class="note">Demo layout. Menu, photos and table booking can be added in the full site.</p>
</main>
<nav class="dock" aria-label="Quick actions">$dock</nav>
</body>
</html>
""")

# ------------------------------------------------------------------ layout 2: clinic (dentists, clinics, default)
CLINIC = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>$name</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root { --bg: $bg; --tint: $tint; --ink: $ink; --muted: $muted; --accent: $accent; --star: $star; }
  * { box-sizing: border-box; margin: 0; }
  html { -webkit-text-size-adjust: 100%; scroll-behavior: smooth; }
  body { font-family: 'Plus Jakarta Sans', system-ui, sans-serif; background: var(--bg); color: var(--ink); line-height: 1.65; padding-bottom: var(--dock-pad, 0); }
  a:focus-visible { outline: 3px solid var(--accent); outline-offset: 3px; }
  .demo { font-size: 13px; line-height: 1.4; padding: 10px 16px; text-align: center; background: var(--ink); color: #fff; }
  $stars_css
  .top { background: var(--tint); border-radius: 0 0 50% 50% / 0 0 clamp(32px, 6vw, 80px) clamp(32px, 6vw, 80px); }
  .wrap { max-width: 1060px; margin: 0 auto; padding: 0 clamp(20px, 5vw, 40px); }
  .bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 20px 0; }
  .brand { font-weight: 800; letter-spacing: -.01em; overflow-wrap: anywhere; }
  .btn { display: inline-block; padding: 13px 24px; border-radius: 999px; font-weight: 700; text-decoration: none; border: 1.5px solid var(--accent); color: var(--accent); background: transparent; text-align: center; }
  .btn.fill { background: var(--accent); color: #fff; }
  .btn.small { padding: 9px 18px; font-size: .92rem; }
  .hero { display: grid; grid-template-columns: 1.15fr .85fr; gap: clamp(28px, 6vw, 72px); align-items: center; padding: clamp(24px, 5vw, 56px) 0 clamp(64px, 9vw, 112px); }
  .pill { display: inline-block; padding: 6px 15px; background: #fff; color: var(--accent); border-radius: 999px; font-weight: 600; font-size: .95rem; }
  h1 { font-weight: 800; font-size: clamp(2.3rem, 5.8vw, 4.2rem); line-height: 1.04; letter-spacing: -.035em; margin-top: 20px; overflow-wrap: anywhere; }
  .tag { margin-top: 16px; font-size: clamp(1.1rem, 2.4vw, 1.35rem); font-weight: 600; color: var(--accent); line-height: 1.35; max-width: 28rem; }
  .about { margin-top: 14px; max-width: 32rem; color: var(--muted); font-size: 1.06rem; }
  .row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 28px; }
  .visit { background: #fff; border-radius: 26px; padding: clamp(24px, 4vw, 36px); box-shadow: 0 24px 60px -30px rgba(15, 47, 58, .45); }
  .visit h2 { font-size: 1.15rem; font-weight: 800; letter-spacing: -.01em; }
  .visit .tel { display: block; margin-top: 14px; font-size: clamp(1.5rem, 3.4vw, 1.9rem); font-weight: 800; letter-spacing: -.02em; color: var(--ink); text-decoration: none; }
  .visit address { font-style: normal; margin-top: 12px; color: var(--muted); font-size: .98rem; }
  .visit .btn { display: block; margin-top: 20px; }
  .visit .maps { display: block; margin-top: 14px; text-align: center; font-weight: 600; color: var(--accent); }
  .stats { display: flex; flex-wrap: wrap; margin-top: clamp(40px, 7vw, 72px); border-top: 1px solid var(--tint); border-bottom: 1px solid var(--tint); }
  .stats div { flex: 1 1 200px; padding: 28px 0 28px clamp(0px, 3vw, 28px); }
  .stats div + div { border-left: 1px solid var(--tint); }
  .stats b { display: block; font-size: 2.1rem; font-weight: 800; letter-spacing: -.03em; color: var(--ink); line-height: 1.2; }
  .stats .stars { font-size: 1.3rem; margin: 8px 0 4px; }
  .stats .stars { display: block; }
  .stats span { color: var(--muted); font-size: .95rem; }
  .where { padding: clamp(40px, 7vw, 72px) 0 8px; }
  .where h2 { font-size: clamp(1.6rem, 3.6vw, 2.2rem); font-weight: 800; letter-spacing: -.025em; }
  .where address { font-style: normal; margin: 8px 0 20px; color: var(--muted); }
  .map { width: 100%; height: 340px; border: 0; border-radius: 22px; background: var(--tint); }
  .note { padding: 24px 0 40px; font-size: 13px; color: var(--muted); }
  .dock { display: none; }
  @media (max-width: 800px) {
    :root { --dock-pad: 76px; }
    .hero { grid-template-columns: 1fr; }
    .stats div + div { border-left: 0; border-top: 1px solid var(--tint); }
    .stats div { padding-left: 0; }
    .bar .btn, .hero .row { display: none; }
    .dock { display: flex; gap: 10px; position: fixed; left: 0; right: 0; bottom: 0; padding: 12px 16px; background: #fff; border-top: 1px solid var(--tint); z-index: 5; }
    .dock .btn { flex: 1; padding: 13px 10px; }
  }
</style>
</head>
<body>
<div class="demo">Demo preview by $sender, freelance web developer. This is not the official website of $name.</div>
<div class="top">
  <div class="wrap">
    <header class="bar"><span class="brand">$name</span>$bar_call</header>
    <section class="hero">
      <div>
        <span class="pill">$category$city_suffix</span>
        <h1>$name</h1>
        <p class="tag">$tagline</p>
        <p class="about">$about</p>
        <div class="row">$call_btn<a class="btn" href="$maps_url" target="_blank" rel="noopener">Get directions</a></div>
      </div>
      <aside class="visit">
        <h2>Visit us</h2>
        $tel_block
        $address_block
        <a class="maps" href="$maps_url" target="_blank" rel="noopener">Open in Maps</a>
      </aside>
    </section>
  </div>
</div>
<main class="wrap">
  $stats
  $where
  <p class="note">Demo layout. Photos, services and online booking can be added in the full site.</p>
</main>
<nav class="dock" aria-label="Quick actions">$dock</nav>
</body>
</html>
""")


_STAR_POLYS = "<polygon points=\"10.0,1.0 12.2,7.3 18.9,7.5 13.6,11.6 15.5,18.0 10.0,14.2 4.5,18.0 6.4,11.6 1.1,7.5 7.8,7.3\"/><polygon points=\"30.0,1.0 32.2,7.3 38.9,7.5 33.6,11.6 35.5,18.0 30.0,14.2 24.5,18.0 26.4,11.6 21.1,7.5 27.8,7.3\"/><polygon points=\"50.0,1.0 52.2,7.3 58.9,7.5 53.6,11.6 55.5,18.0 50.0,14.2 44.5,18.0 46.4,11.6 41.1,7.5 47.8,7.3\"/><polygon points=\"70.0,1.0 72.2,7.3 78.9,7.5 73.6,11.6 75.5,18.0 70.0,14.2 64.5,18.0 66.4,11.6 61.1,7.5 67.8,7.3\"/><polygon points=\"90.0,1.0 92.2,7.3 98.9,7.5 93.6,11.6 95.5,18.0 90.0,14.2 84.5,18.0 86.4,11.6 81.1,7.5 87.8,7.3\"/>"


def _stars(rating) -> str:
    try:
        value = max(0.0, min(5.0, float(rating)))
    except (TypeError, ValueError):
        return ""
    svg = lambda fill: f'<svg viewBox="0 0 100 20" aria-hidden="true" fill="{fill}">{_STAR_POLYS}</svg>'  # noqa: E731
    return (
        f'<span class="stars" style="--r:{value / 5 * 100:.0f}%" role="img" aria-label="{value:.1f} out of 5">'
        f'{svg("rgba(0,0,0,.16)")}<i class="fill">{svg("currentColor")}</i></span>'
    )


def render_site(lead: dict, copy: dict) -> str:
    e = lambda v: html.escape(str(v or ""), quote=True)  # noqa: E731 - everything user/LLM-derived is escaped
    theme = pick_theme(lead)

    phone = lead.get("phone")
    tel = re.sub(r"[^\d+]", "", phone or "")
    city_suffix = f", {e(lead['city'])}" if lead.get("city") else ""

    where = lead.get("address") or lead.get("city") or ""
    maps_q = quote(f"{lead['name']} {where}")
    maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_q}"
    if lead.get("place_id"):
        maps_url += f"&query_place_id={quote(lead['place_id'])}"
    map_block = (
        f'<iframe class="map" title="Map of {e(lead["name"])}" loading="lazy" referrerpolicy="no-referrer-when-downgrade" '
        f'src="{e("https://www.google.com/maps?q=" + maps_q + "&output=embed")}"></iframe>'
        if where
        else ""
    )

    address_block = f"<address>{e(lead['address'])}</address>" if lead.get("address") else ""
    tel_block = f'<a class="tel" href="tel:{e(tel)}">{e(phone)}</a>' if tel else ""
    call_btn = f'<a class="btn fill" href="tel:{e(tel)}">{e(theme["cta"])}</a>' if tel else ""
    dock = (f'<a class="btn fill" href="tel:{e(tel)}">Call</a>' if tel else "") + (
        f'<a class="btn" href="{e(maps_url)}" target="_blank" rel="noopener">Directions</a>'
    )

    common = dict(
        name=e(lead["name"]),
        category=e(lead.get("category") or "Local business"),
        city_suffix=city_suffix,
        tagline=e(copy["tagline"]),
        about=e(copy["about"]),
        sender=e(settings.sender_name),
        maps_url=e(maps_url),
        bg=theme["bg"],
        tint=theme["tint"],
        ink=theme["ink"],
        accent=theme["accent"],
        star=theme["star"],
        muted=theme.get("muted", "#555555"),
        plate_bg=theme.get("plate", "#FFFFFF"),
        stars_css=STARS_CSS,
        address_block=address_block,
        tel_block=tel_block,
        call_btn=call_btn,
        dock=dock,
    )

    rating, reviews = lead.get("rating"), lead.get("review_count")

    if theme["layout"] == "card":
        if rating:
            reviews_line = f"from {e(reviews)} reviews on Google" if reviews else "on Google"
            plate_inner = f'<div class="small">Rated</div><div class="score">{e(rating)}</div>{_stars(rating)}<div class="small">{reviews_line}</div>'
        elif lead.get("city"):
            plate_inner = f'<div class="small">Find us in</div><div class="city">{e(lead["city"])}</div>'
        else:
            plate_inner = ""
        plate = f'<div class="plate-wrap"><div class="plate">{plate_inner}</div></div>' if plate_inner else ""
        return CARD.substitute(**common, plate=plate, solo="" if plate else " solo", map_block=map_block)

    stats = []
    if rating:
        stats.append(f"<div><b>{e(rating)} out of 5</b>{_stars(rating)}<span>Rating on Google</span></div>")
    if reviews:
        stats.append(f"<div><b>{e(reviews)}</b><span>Reviews on Google</span></div>")
    if lead.get("city"):
        stats.append(f"<div><b>{e(lead['city'])}</b><span>Find us here</span></div>")
    where_block = (
        f'<section class="where"><h2>Find us</h2>{address_block}{map_block}</section>' if map_block else ""
    )
    return CLINIC.substitute(
        **common,
        bar_call=f'<a class="btn fill small" href="tel:{e(tel)}">Call</a>' if tel else "",
        stats=f'<section class="stats">{"".join(stats)}</section>' if stats else "",
        where=where_block,
    )


def build_site(lead: dict) -> str:
    return render_site(lead, generate_copy(lead))