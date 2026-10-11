from app.audit import extract_signals, is_social_only
from app.scoring import score_lead

GOOD_LEAD = {"review_count": 150, "rating": 4.6, "phone": "098765 43210"}
GOOD_HTML = """
<html><head><title>Clinic</title>
<meta name="description" content="Best clinic">
<meta name="viewport" content="width=device-width">
</head><body>""" + ("word " * 200) + """<a href="tel:123">Call</a></body></html>
"""


def test_no_website_is_top_prospect():
    score, reasons = score_lead(GOOD_LEAD, {"has_website": False})
    assert score >= 95
    assert any("no website" in r for r in reasons)


def test_social_only_scores_slightly_below_no_website():
    a, _ = score_lead(GOOD_LEAD, {"has_website": False})
    b, _ = score_lead(GOOD_LEAD, {"has_website": False, "social_only": True})
    assert b < a


def test_healthy_website_scores_low():
    signals = {"has_website": True, "https": True, "final_https": True, "load_seconds": 1.2}
    signals.update(extract_signals(GOOD_HTML))
    score, _ = score_lead(GOOD_LEAD, signals)
    assert score <= 35  # only viability points, no gap points


def test_dead_business_with_no_website_scores_lower_than_active_one():
    dead = {"review_count": 0, "rating": 0, "phone": None}
    s_dead, _ = score_lead(dead, {"has_website": False})
    s_active, _ = score_lead(GOOD_LEAD, {"has_website": False})
    assert s_dead < s_active


def test_unreachable_site_is_a_strong_signal():
    score, reasons = score_lead(GOOD_LEAD, {"has_website": True, "unreachable": True})
    assert score >= 70
    assert any("unreachable" in r for r in reasons)


def test_score_is_capped_at_100():
    score, _ = score_lead(GOOD_LEAD, {"has_website": False})
    assert score <= 100


def test_social_host_detection():
    assert is_social_only("https://www.facebook.com/mybiz")
    assert is_social_only("https://instagram.com/mybiz")
    assert not is_social_only("https://mybiz.in")
