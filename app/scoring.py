"""Rule-based opportunity scoring.

Score = how strong a prospect is for a website/redesign pitch (0-100).
Two parts: (1) website gap, (2) business viability (a gap on a dead business is worthless).
Deterministic on purpose: explainable in an interview, free to run, testable.
"""

MAX_SCORE = 100


def score_lead(lead: dict, signals: dict) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    def add(points: int, reason: str) -> None:
        nonlocal score
        score += points
        reasons.append(f"+{points} {reason}")

    # --- Part 1: website gap (max 70) ---
    if not signals.get("has_website"):
        if signals.get("social_only"):
            add(60, "only a social/directory page, no real website")
        else:
            add(70, "no website")
    elif signals.get("unreachable"):
        add(55, "website is down or unreachable")
    else:
        if not signals.get("final_https", signals.get("https")):
            add(15, "no HTTPS")
        if not signals.get("has_viewport"):
            add(20, "not mobile-friendly (no viewport meta)")
        if (signals.get("load_seconds") or 0) > 4:
            add(10, f"slow load ({signals['load_seconds']}s)")
        if not signals.get("has_meta_description") or not signals.get("has_title"):
            add(8, "missing title/meta description (weak SEO)")
        if not signals.get("has_contact_link") and not signals.get("has_form"):
            add(10, "no clickable contact method")
        if (signals.get("text_length") or 0) < 400:
            add(7, "very thin content")

    # --- Part 2: business viability (max 30) ---
    reviews = lead.get("review_count") or 0
    rating = lead.get("rating") or 0
    if reviews >= 100:
        add(15, f"established business ({reviews} reviews)")
    elif reviews >= 20:
        add(10, f"active business ({reviews} reviews)")
    elif reviews >= 5:
        add(4, f"some traction ({reviews} reviews)")
    else:
        reasons.append("+0 very few reviews, weak signal of an active business")

    if rating >= 4.0:
        add(5, f"good rating ({rating})")
    if lead.get("phone"):
        add(10, "has a phone number (reachable)")

    return min(score, MAX_SCORE), reasons
