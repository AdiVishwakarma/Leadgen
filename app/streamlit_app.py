import requests
import pandas as pd
import streamlit as st

# ============================================================
# CONFIG
# ============================================================

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="LeadGen",
    page_icon="🎯",
    layout="wide",
)

# ============================================================
# SESSION STATE
# ============================================================

if "leads" not in st.session_state:
    st.session_state["leads"] = []

# ============================================================
# API HELPERS
# ============================================================

def discover_leads(category: str, city: str, limit: int) -> dict:
    response = requests.post(
        f"{API_BASE}/discover",
        json={
            "category": category.lower().strip(),
            "city": city.strip(),
            "limit": limit,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def audit_pending(batch: int) -> dict:
    response = requests.post(
        f"{API_BASE}/audit/pending",
        params={"batch": batch},
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def get_leads() -> list:
    response = requests.get(
        f"{API_BASE}/leads",
        params={
            "min_score": 0,
            "limit": 200,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()

# ============================================================
# CATEGORY OPTIONS
# ============================================================

CATEGORY_OPTIONS = [
    "Dentist",
    "Restaurant",
    "Cafe",
    "Bakery",
    "Salon",
    "Beauty Spa",
    "Gym",
    "Fitness Center",
    "Doctor",
    "Clinic",
    "Hospital",
    "Physiotherapist",
    "Dermatologist",
    "Veterinary Clinic",
    "Pharmacy",
    "Lawyer",
    "Chartered Accountant",
    "Real Estate Agency",
    "Interior Designer",
    "Architect",
    "Coaching Center",
    "School",
    "Daycare",
    "Pet Store",
    "Car Dealer",
    "Bike Dealer",
    "Car Repair",
    "Electronics Store",
    "Furniture Store",
    "Jewellery Store",
    "Photographer",
    "Travel Agency",
    "Event Planner",
    "Hotel",
    "Other",
]

# ============================================================
# CATEGORY MATCHING
# ============================================================

def category_matches(selected_category: str, db_category: str) -> bool:

    selected = selected_category.strip().lower()
    actual = str(db_category or "").strip().lower()

    if not actual:
        return False

    if selected == "other":
        return True

    # Dentist
    if selected == "dentist":
        keywords = [
            "dentist",
            "dental",
            "orthodont",
            "oral surgeon",
        ]
        return any(k in actual for k in keywords)

    # Restaurant
    if selected in ["restaurant", "restaurants"]:
        return (
            "restaurant" in actual
            or "bar & grill" in actual
        )

    # Salon
    if selected == "salon":
        keywords = [
            "salon",
            "barber",
            "hairdresser",
            "hair studio",
            "beauty parlour",
            "beauty parlor",
        ]
        return any(k in actual for k in keywords)

    # Cafe
    if selected == "cafe":
        keywords = [
            "cafe",
            "coffee",
            "cafeteria",
        ]
        return any(k in actual for k in keywords)

    # Bakery
    if selected == "bakery":
        keywords = [
            "bakery",
            "cake",
            "pastry",
        ]
        return any(k in actual for k in keywords)

    # Gym / Fitness
    if selected in ["gym", "fitness center"]:
        keywords = [
            "gym",
            "fitness",
            "crossfit",
            "workout",
        ]
        return any(k in actual for k in keywords)

    # Hotel
    if selected == "hotel":
        keywords = [
            "hotel",
            "resort",
            "lodging",
            "guest house",
        ]
        return any(k in actual for k in keywords)

    # Lawyer
    if selected == "lawyer":
        keywords = [
            "lawyer",
            "law firm",
            "attorney",
            "legal",
        ]
        return any(k in actual for k in keywords)

    # Real Estate
    if selected == "real estate agency":
        keywords = [
            "real estate",
            "realty",
            "property",
        ]
        return any(k in actual for k in keywords)

    # Photographer
    if selected == "photographer":
        keywords = [
            "photographer",
            "photography",
            "photo studio",
        ]
        return any(k in actual for k in keywords)

    # Travel
    if selected == "travel agency":
        keywords = [
            "travel",
            "tour agency",
        ]
        return any(k in actual for k in keywords)

    # Generic fallback
    return (
        selected in actual
        or actual in selected
    )

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("Lead Discovery")

category = st.sidebar.selectbox(
    "Category",
    CATEGORY_OPTIONS,
)

custom_category = ""

if category == "Other":
    custom_category = st.sidebar.text_input(
        "Enter custom category",
        placeholder="e.g. yoga studio",
    )

city = st.sidebar.text_input(
    "City",
    value="Vasai",
)

limit = st.sidebar.number_input(
    "Number of leads",
    min_value=1,
    max_value=50,
    value=20,
)

audit_batch = st.sidebar.number_input(
    "Audit batch",
    min_value=1,
    max_value=50,
    value=10,
)

# ============================================================
# HEADER
# ============================================================

st.title("🎯 LeadGen")
st.caption(
    "Business lead discovery and website opportunity scoring"
)

# ============================================================
# DISCOVER BUTTON
# ============================================================

if st.sidebar.button(
    "🔎 Discover Leads",
    use_container_width=True,
):

    selected_category = (
        custom_category.strip()
        if category == "Other"
        else category
    )

    if not selected_category:
        st.sidebar.error("Enter a category.")
    elif not city.strip():
        st.sidebar.error("Enter a city.")
    else:

        with st.spinner(
            f"Searching {selected_category} businesses in {city}..."
        ):
            try:

                result = discover_leads(
                    selected_category,
                    city,
                    int(limit),
                )

                st.success(
                    f"Found: {result['found']} | "
                    f"Inserted: {result['inserted']} | "
                    f"Duplicates: {result['skipped_duplicates']}"
                )

                st.session_state["leads"] = get_leads()

            except requests.RequestException as exc:
                st.error(f"Discovery failed: {exc}")

# ============================================================
# AUDIT BUTTON
# ============================================================

if st.sidebar.button(
    "🌐 Audit Pending Leads",
    use_container_width=True,
):

    with st.spinner("Auditing pending websites..."):

        try:

            result = audit_pending(
                int(audit_batch)
            )

            st.success(
                f"Audited: {result['audited']} leads"
            )

            st.session_state["leads"] = get_leads()

        except requests.RequestException as exc:
            st.error(f"Audit failed: {exc}")

# ============================================================
# LOAD BUTTON
# ============================================================

if st.sidebar.button(
    "📊 Load Leads",
    use_container_width=True,
):

    with st.spinner("Loading leads..."):

        try:

            st.session_state["leads"] = get_leads()

        except requests.RequestException as exc:
            st.error(f"Could not load leads: {exc}")

# ============================================================
# DISPLAY DATA
# ============================================================

leads = st.session_state.get("leads", [])

if leads:

    df = pd.DataFrame(leads)

    selected_category = (
        custom_category.strip()
        if category == "Other"
        else category
    )

    # Category filter
    if selected_category:

        df = df[
            df["category"].apply(
                lambda value: category_matches(
                    selected_category,
                    value,
                )
            )
        ]

    # City filter
    if city.strip():

        df = df[
            df["city"]
            .fillna("")
            .str.contains(
                city.strip(),
                case=False,
                na=False,
            )
        ]

    # Sort highest score first
    if "score" in df.columns:

        df = df.sort_values(
            "score",
            ascending=False,
        )

    # Metrics
    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Matching Leads",
        len(df),
    )

    if not df.empty and "score" in df.columns:
        col2.metric(
            "Top Score",
            int(df["score"].max()),
        )
    else:
        col2.metric("Top Score", 0)

    if not df.empty and "rating" in df.columns:
        ratings = df["rating"].dropna()

        col3.metric(
            "Avg Rating",
            round(ratings.mean(), 1)
            if not ratings.empty
            else 0,
        )
    else:
        col3.metric("Avg Rating", 0)

    if not df.empty and "review_count" in df.columns:

        col4.metric(
            "Total Reviews",
            int(
                df["review_count"]
                .fillna(0)
                .sum()
            ),
        )

    else:
        col4.metric(
            "Total Reviews",
            0,
        )

    st.subheader(
        f"{selected_category} Leads in {city}"
    )

    # Table
    if df.empty:

        st.warning(
            "No matching leads found for this category and city."
        )

    else:

        columns = [
            "score",
            "name",
            "category",
            "phone",
            "website",
            "rating",
            "review_count",
            "city",
            "status",
            "address",
        ]

        existing_columns = [
            c for c in columns
            if c in df.columns
        ]

        df = df[existing_columns]

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

else:

    st.info(
        "Click 'Discover Leads' to find new businesses "
        "or 'Load Leads' to view existing leads."
    )