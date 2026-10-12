"""Lead Gen dashboard (Streamlit). It only talks to the FastAPI server over HTTP.

Run (FastAPI must already be running on port 8000):
    streamlit run app/streamlit_app.py
"""
import os
import re
from urllib.parse import quote

import httpx
import pandas as pd
import streamlit as st

DEFAULT_API = os.getenv("LEADGEN_API", "http://127.0.0.1:8000")
OPT_OUT = "won't message again"
STATUS_FILTERS = ["Sab", "audited", "drafted", "site_ready", "contacted"]


# ------------------------------------------------------------------ pure helpers (unit tested)
def wa_number(phone: str | None) -> tuple[str | None, str | None]:
    """Indian phone -> WhatsApp number (91XXXXXXXXXX). Returns (number, problem)."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    national = digits[2:] if digits.startswith("91") and len(digits) == 12 else digits.lstrip("0")
    if len(national) != 10:
        return None, "Number ka format samajh nahi aaya"
    if national[0] not in "6789":
        return None, "Ye landline lagta hai, WhatsApp pe nahi hoga"
    return "91" + national, None


def with_link(message: str, url: str | None) -> str:
    """Put the demo link into the draft. The draft asks 'want a free preview?'; once the page
    exists we replace that question with the link. No question found -> link goes above the opt-out line."""
    msg = message.strip()
    if not url:
        return msg
    sentence = f"I've already put together a quick demo page for you to look at: {url}"
    m = re.search(r"[^.?!\n]*\bpreview\b[^.?!\n]*\?", msg, flags=re.I)
    if m:
        return msg[: m.start()] + sentence + msg[m.end():]
    idx = msg.lower().replace("’", "'").find(OPT_OUT)
    if idx == -1:
        return f"{msg}\n\n{sentence}"
    start = msg.rfind("\n", 0, idx)
    start = 0 if start == -1 else start
    return f"{msg[:start].rstrip()}\n\n{sentence}\n\n{msg[start:].lstrip()}"


def short_site(url: str | None) -> str:
    return re.sub(r"^https?://(www\.)?", "", url or "").split("/")[0] if url else "Nahi"


# ------------------------------------------------------------------ API + UI glue
def api(base: str, method: str, path: str, timeout: int = 120, **kw):
    """Returns (data, error). Never raises."""
    try:
        r = httpx.request(method, base + path, timeout=timeout, **kw)
    except httpx.HTTPError as exc:
        return None, f"API se connect nahi hua ({type(exc).__name__}). FastAPI server chal raha hai?"
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:  # noqa: BLE001
            detail = r.text
        return None, f"{r.status_code}: {detail}"
    return r.json(), None


def link(label: str, url: str) -> None:
    if hasattr(st, "link_button"):
        st.link_button(label, url)
    else:  # very old Streamlit
        st.markdown(f"[{label}]({url})")


def rerun() -> None:
    (st.rerun if hasattr(st, "rerun") else st.experimental_rerun)()


def flash(kind: str, text: str) -> None:
    st.session_state["flash"] = (kind, text)


def main() -> None:
    st.set_page_config(page_title="Lead Gen", layout="wide")
    st.title("Lead Gen dashboard")

    note = st.session_state.pop("flash", None)
    if note:
        (st.success if note[0] == "ok" else st.error)(note[1])

    # ---------------- sidebar: find + audit
    base = st.sidebar.text_input("API address", DEFAULT_API).rstrip("/")

    with st.sidebar.form("discover"):
        st.subheader("1. Nayi leads dhoondho")
        category = st.text_input("Category", "dentist")
        city = st.text_input("City", "Vasai")
        limit = st.number_input("Kitni leads", min_value=1, max_value=60, value=20)
        go = st.form_submit_button("Dhoondho")
    if go:
        with st.spinner("Google se leads la raha hoon..."):
            data, err = api(base, "POST", "/discover", json={"category": category, "city": city, "limit": int(limit)})
        flash("err" if err else "ok", err or f"{data['found']} mili, {data['inserted']} nayi, {data['skipped_duplicates']} pehle se thi.")
        rerun()

    st.sidebar.subheader("2. Website check + score")
    if st.sidebar.button("Naye leads ka audit chalao"):
        with st.spinner("Websites check ho rahi hain (thoda time lagega)..."):
            data, err = api(base, "POST", "/audit/pending", params={"batch": 20}, timeout=600)
        flash("err" if err else "ok", err or f"{data['audited']} leads ka audit ho gaya.")
        rerun()

    # ---------------- filters + list
    f1, f2, f3 = st.columns(3)
    min_score = f1.slider("Minimum score", 0, 100, 0)
    status = f2.selectbox("Status", STATUS_FILTERS)
    no_site_only = f3.checkbox("Sirf bina website wale", value=False)

    params: dict = {"min_score": min_score, "limit": 200}
    if status != "Sab":
        params["status"] = status
    leads, err = api(base, "GET", "/leads", params=params)
    if err:
        st.error(err)
        st.stop()
    if no_site_only:
        leads = [l for l in leads if not l["website"]]
    if not leads:
        st.info("Koi lead nahi mili. Sidebar se leads dhoondho, phir audit chalao.")
        st.stop()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Leads", len(leads))
    m2.metric("Bina website", sum(1 for l in leads if not l["website"]))
    m3.metric("Message ready", sum(1 for l in leads if l["status"] in ("drafted", "site_ready")))
    m4.metric("Bheji gayi", sum(1 for l in leads if l["status"] == "contacted"))

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": l["id"], "Naam": l["name"], "Category": l["category"], "Score": l["score"],
                    "Status": l["status"], "Website": short_site(l["website"]),
                    "Reviews": l["review_count"], "Phone": l["phone"],
                }
                for l in leads
            ]
        ),
        hide_index=True,
    )

    # ---------------- one lead
    by_id = {l["id"]: l for l in leads}
    # Fixed key + labels without status: otherwise the selection resets to the first lead after every action.
    sel = st.selectbox(
        "Lead chun",
        list(by_id),
        format_func=lambda i: f"#{i}  {by_id[i]['name']}  (score {by_id[i]['score']})",
        key="selected_lead",
    )
    lead = by_id[sel]
    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader(lead["name"])
        st.caption(f"{lead['category'] or ''}  |  {lead['city'] or ''}  |  status: {lead['status']}  |  score: {lead['score']}")
        st.write(lead["address"] or "")
        st.write(f"Phone: {lead['phone'] or 'nahi hai'}")
        if lead["rating"]:
            st.write(f"Rating: {lead['rating']} ({lead['review_count']} reviews)")

        audits, _ = api(base, "GET", f"/leads/{sel}/audits")
        if audits:
            st.markdown("**Score kyun aaya**")
            for reason in audits[0]["reasons"]:
                st.write("- " + reason)

        st.markdown("**Step 1. Khud confirm kar (bhejne se pehle)**")
        if lead["website"]:
            st.warning(f"Is lead ki website hai: {lead['website']}. Pitch dobara soch.")
        else:
            st.info("Google Maps listing me website nahi hai. Neeche button se Google pe check kar ki sach me nahi hai.")
        link("Google pe search karo", "https://www.google.com/search?q=" + quote(f"{lead['name']} {lead['city'] or ''}"))

    with right:
        # ---- step 2: demo page
        st.markdown("**Step 2. Demo page**")
        sites, _ = api(base, "GET", f"/leads/{sel}/site")
        site_url = sites[0]["url"] if sites else None
        if st.button("Demo page dobara banao" if site_url else "Demo page banao", key=f"site_{sel}"):
            with st.spinner("Page bana ke Vercel pe bhej raha hoon..."):
                data, err = api(base, "POST", f"/leads/{sel}/site", timeout=180)
            flash("err" if err else "ok", err or "Demo page ready.")
            rerun()
        if site_url:
            st.write(site_url)
            link("Demo page kholo", site_url)
        link("Local preview (deploy se pehle)", f"{base}/leads/{sel}/site/preview")

        # ---- step 3: message
        st.markdown("**Step 3. Message**")
        lang = st.radio("Language", ["english", "hinglish"], horizontal=True, key=f"lang_{sel}")
        open_rows = []
        for s in ("draft", "approved"):
            rows, _ = api(base, "GET", "/outreach", params={"status": s, "limit": 200})
            open_rows += [r for r in (rows or []) if r["lead_id"] == sel]
        row = max(open_rows, key=lambda r: r["id"]) if open_rows else None

        if st.button("Naya message banao" if row else "Message banao", key=f"draft_{sel}"):
            with st.spinner("Gemini message likh raha hai (1 minute tak lag sakta hai)..."):
                data, err = api(base, "POST", f"/leads/{sel}/outreach", params={"language": lang}, timeout=240)
            flash("err" if err else "ok", err or "Naya message ready.")
            rerun()

        if row:
            final = with_link(row["message"], site_url)
            if not site_url:
                st.caption("Demo page abhi nahi bana, isliye message me link nahi hai. Pehle Step 2 kar.")
            st.text_area("Message", final, height=300, disabled=True, key=f"msg_{row['id']}_{bool(site_url)}")

            num, problem = wa_number(lead["phone"])
            if num:
                link("WhatsApp me kholo", f"https://wa.me/{num}?text={quote(final)}")
                st.caption("WhatsApp me message pehle se likha milega. Wahin edit karke send kar sakta hai.")
            else:
                st.warning(problem)
            with st.expander("Copy karne ke liye"):
                st.code(final, language=None)

            b1, b2 = st.columns(2)
            if b1.button("Maine bhej diya", type="primary", key=f"sent_{row['id']}"):
                err = None
                if row["status"] == "draft":
                    _, err = api(base, "POST", f"/outreach/{row['id']}/approve")
                if not err:
                    _, err = api(base, "POST", f"/outreach/{row['id']}/mark-sent")
                flash("err" if err else "ok", err or "Mark ho gaya: lead ab 'contacted' hai.")
                rerun()
            if b2.button("Ye message reject karo", key=f"rej_{row['id']}"):
                _, err = api(base, "POST", f"/outreach/{row['id']}/reject")
                flash("err" if err else "ok", err or "Reject ho gaya.")
                rerun()
        elif lead["status"] == "contacted":
            st.success("Is lead ko message bheja ja chuka hai.")


# Streamlit runs this file as a script; pytest only imports it, so only build the UI when a runtime exists.
from streamlit import runtime  # noqa: E402

if runtime.exists():
    main()