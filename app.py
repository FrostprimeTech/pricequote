"""
Freight Rate Quoting App — for live client-call use.

Run with:
    .venv/bin/streamlit run app.py

Pricing comes from rate_card.RATE_CARD (vehicle x distance band -> one-way
Rs/km), not an ML model. Only 8FT, 9FT, 10FT, 11FT, 12FT, 14FT are supported.

The Chat Quote tab (LLM-based free-text quoting) is parked for now — set
CHAT_QUOTE_ENABLED back to True to re-enable it. All of its code
(nlp_extract.py, quote_engine.get_chat_quote, rate_card web-search
fallback) is untouched and ready to go.
"""

CHAT_QUOTE_ENABLED = False

import streamlit as st

from freight_pipeline import CSV_PATH, MACRO_ZONE_MAP, load_and_engineer
from quote_engine import (
    get_chat_quote,
    get_quote,
    match_origin,
    match_vehicle,
    resolve_distance,
)
from rate_card import RATE_CARD, VEHICLE_TYPES

st.set_page_config(page_title="Freight Rate Quote", layout="centered")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

    html, body, [class*="css"]  {
        font-family: 'Inter', -apple-system, sans-serif;
    }

    .stApp {
        background: #FAFAF9;
    }

    #MainMenu, footer, header {visibility: hidden;}

    .app-header {
        display: flex;
        align-items: baseline;
        gap: 10px;
        margin: 6px 0 28px 0;
        border-bottom: 1px solid #E5E5E3;
        padding-bottom: 16px;
    }
    .app-header {
        background: #F2F1EC;
        border-radius: 12px;
        padding: 18px 22px;
        border-bottom: none;
    }
    .app-header .title {
        font-size: 22px;
        font-weight: 700;
        color: #1C1C1A;
        letter-spacing: -0.3px;
        margin: 0;
    }
    .app-header .subtitle {
        font-size: 13px;
        color: #8A8A85;
        margin: 0;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background: transparent;
        border-bottom: 1px solid #E5E5E3;
    }
    .stTabs [data-baseweb="tab"] {
        color: #8A8A85;
        font-weight: 600;
        padding: 8px 4px;
        margin-right: 20px;
    }
    .stTabs [aria-selected="true"] {
        color: #1C1C1A !important;
        border-bottom: 2px solid #1C1C1A;
    }

    section[data-testid="stSelectbox"], div[data-testid="stNumberInput"], div[data-testid="stTextInput"] {
        background: #FFFFFF;
        border-radius: 6px;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stNumberInput"] input,
    [data-testid="stTextInput"] input {
        background: #FFFFFF !important;
        border: 1px solid #E5E5E3 !important;
        color: #1C1C1A !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] span,
    [data-testid="stSelectbox"] [data-baseweb="select"] div {
        color: #1C1C1A !important;
    }
    [data-testid="stSelectbox"] svg {
        fill: #1C1C1A !important;
    }

    label[data-testid="stWidgetLabel"] p {
        color: #6B6B66 !important;
        font-weight: 600;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }

    .stButton > button {
        font-weight: 600;
        border-radius: 6px;
        padding: 9px 24px;
    }

    /* Primary buttons (selected state, main CTA): solid dark fill */
    .stButton > button[kind="primary"],
    [data-testid="stBaseButton-primary"] {
        background: #1C1C1A !important;
        border: none !important;
        color: #FAFAF9 !important;
    }
    .stButton > button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
        background: #3A3A36 !important;
        color: #FAFAF9 !important;
    }
    .stButton > button[kind="primary"] p,
    .stButton > button[kind="primary"] span,
    .stButton > button[kind="primary"] div,
    [data-testid="stBaseButton-primary"] p,
    [data-testid="stBaseButton-primary"] span,
    [data-testid="stBaseButton-primary"] div {
        color: #FAFAF9 !important;
    }

    /* Secondary buttons (unselected state): light outline */
    .stButton > button[kind="secondary"],
    [data-testid="stBaseButton-secondary"] {
        background: #FFFFFF !important;
        border: 1px solid #D8D7D2 !important;
        color: #6B6B66 !important;
    }
    .stButton > button[kind="secondary"]:hover,
    [data-testid="stBaseButton-secondary"]:hover {
        background: #F2F1EC !important;
        border-color: #C5C4BE !important;
        color: #1C1C1A !important;
    }
    .stButton > button[kind="secondary"] p,
    .stButton > button[kind="secondary"] span,
    .stButton > button[kind="secondary"] div,
    [data-testid="stBaseButton-secondary"] p,
    [data-testid="stBaseButton-secondary"] span,
    [data-testid="stBaseButton-secondary"] div {
        color: inherit !important;
    }

    .field-label {
        color: #6B6B66 !important;
        font-weight: 600;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.3px;
        margin-bottom: 4px;
    }

    .quote-card {
        background: linear-gradient(135deg, #FFFFFF 0%, #F2F1EC 100%);
        border: 1px solid #E5E5E3;
        border-left: 3px solid #1C1C1A;
        border-radius: 8px;
        padding: 20px 24px;
        margin: 16px 0;
    }
    .quote-card .label {
        color: #8A8A85;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        margin-bottom: 4px;
    }
    .quote-card .price {
        color: #1C1C1A;
        font-size: 32px;
        font-weight: 700;
        letter-spacing: -0.5px;
        line-height: 1.1;
    }
    .quote-card.warn {
        background: linear-gradient(135deg, #FFFFFF 0%, #F3EEE3 100%);
        border-left-color: #A68A5B;
    }
    .quote-card.warn .price {
        color: #7A6435;
    }
    .quote-card .range {
        color: #8A8A85;
        font-size: 13px;
        font-weight: 500;
        margin-top: 6px;
    }

    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E5E5E3;
        border-radius: 6px;
        padding: 10px 12px;
    }
    [data-testid="stMetricLabel"] {
        color: #8A8A85 !important;
    }
    [data-testid="stMetricValue"] {
        color: #1C1C1A !important;
        font-size: 18px !important;
    }

    /* Force readable text everywhere, regardless of browser/OS dark-mode
       defaults — without this, Streamlit's own theme can render light text
       that's invisible against our light background (e.g. expander content). */
    .stApp, .stApp p, .stApp span, .stApp li, .stApp label {
        color: #1C1C1A;
    }

    [data-testid="stExpander"] {
        background: #FFFFFF;
        border: 1px solid #E5E5E3;
        border-radius: 6px;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] details > summary {
        background: #FFFFFF !important;
        color: #3A3A36 !important;
        font-weight: 600;
    }
    [data-testid="stExpander"] summary * {
        color: #3A3A36 !important;
    }
    [data-testid="stExpander"] svg {
        fill: #3A3A36 !important;
    }
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] li {
        color: #3A3A36 !important;
    }

    .quote-card .label, .app-header .subtitle, .stTabs [data-baseweb="tab"] {
        color: #8A8A85 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_history():
    df = load_and_engineer(CSV_PATH)
    dist_lookup = (
        df.groupby(["From", "Final_Destination"])["Distance (km)"].median().to_dict()
    )
    dest_by_origin = (
        df.dropna(subset=["Final_Destination"])
        .groupby("From")["Final_Destination"]
        .unique()
        .apply(sorted)
        .to_dict()
    )
    return dist_lookup, dest_by_origin


dist_lookup, dest_by_origin = load_history()
origins = sorted(MACRO_ZONE_MAP.keys())
rate_card_vehicles = sorted(RATE_CARD.keys(), key=lambda v: int(v.replace("FT", "")))

st.markdown(
    """
    <div class="app-header">
        <p class="title">Rate Quote</p>
        <p class="subtitle">Route prices for vendors</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if CHAT_QUOTE_ENABLED:
    tab_form, tab_chat = st.tabs(["Form Quote", "Chat Quote"])
else:
    (tab_form,) = st.tabs(["Form Quote"])

# --------------------------------------------------------------------------
# Form tab
# --------------------------------------------------------------------------
with tab_form:
    if "vehicle_type" not in st.session_state:
        st.session_state.vehicle_type = VEHICLE_TYPES[0]

    st.markdown('<p class="field-label">Type</p>', unsafe_allow_html=True)
    type_col1, type_col2 = st.columns(2)
    with type_col1:
        if st.button(
            "Freezer",
            type="primary" if st.session_state.vehicle_type == "FREEZER" else "secondary",
            use_container_width=True,
        ):
            st.session_state.vehicle_type = "FREEZER"
    with type_col2:
        if st.button(
            "Chiller",
            type="primary" if st.session_state.vehicle_type == "CHILLER" else "secondary",
            use_container_width=True,
        ):
            st.session_state.vehicle_type = "CHILLER"
    vehicle_type = st.session_state.vehicle_type

    col1, col2 = st.columns(2)
    with col1:
        origin = st.selectbox(
            "Origin hub",
            origins,
            accept_new_options=True,
            placeholder="Select or type an origin",
        )
    with col2:
        dest_options = list(dest_by_origin.get(origin, []))
        destination = st.selectbox(
            "Destination",
            dest_options,
            accept_new_options=True,
            placeholder="Select or type a destination",
        )

    origin = origin or ""
    destination = destination or ""

    vehicle = st.selectbox(
        "Vehicle size",
        rate_card_vehicles,
        accept_new_options=True,
        placeholder="Select or type a vehicle size",
    )
    vehicle = vehicle or ""

    default_distance = dist_lookup.get((origin, destination), 0.0)
    distance = st.number_input(
        "Distance (km)",
        min_value=0.0,
        value=float(default_distance),
        step=5.0,
        help="Auto-filled from historical trips when a known origin/destination match exists.",
    )

    if st.button("Get Quote", type="primary"):
        if distance <= 0:
            st.error("Enter a distance greater than 0.")
        else:
            try:
                result = get_quote(origin, destination, vehicle, distance, vehicle_type)
            except ValueError as e:
                st.error(str(e))
            else:
                if result["below_floor"]:
                    st.warning(
                        f"Below floor price: Rs.{result['per_km_rate']:,.2f}/km is under the "
                        f"Rs.{result['floor_rate']:,.2f}/km floor for {result['vehicle']} in the "
                        f"{result['distance_band']} band. Double-check before quoting."
                    )
                card_class = "quote-card warn" if result["below_floor"] else "quote-card"
                st.markdown(
                    f"""
                    <div class="{card_class}">
                        <div class="label">Quoted Rate</div>
                        <div class="price">Rs.{result['rate']:,.0f}</div>
                        <div class="range">Rs.{result['rate_low']:,.0f} - Rs.{result['rate_high']:,.0f}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Per-KM Rate", f"Rs.{result['per_km_rate']:,.2f}")
                m2.metric("Distance", f"{result['distance_display']:,.0f} km")
                m3.metric("Distance Band", result["distance_band"])
                m4.metric("Type", result["vehicle_type"].title())

                with st.expander("Calculation breakdown", expanded=True):
                    st.markdown(
                        f"- Type: **{result['vehicle_type'].title()}**\n"
                        f"- Origin: **{origin}**\n"
                        f"- Destination: **{destination}**\n"
                        f"- Vehicle: **{result['vehicle']}**\n"
                        f"- Distance : **{result['distance']:,.0f} km** "
                        f"(distance round way {result['distance_display']:,.0f} km)\n"
                        f"- Distance band: **{result['distance_band']}**\n"
                        f"- Rate card per-km rate: **Rs.{result['per_km_rate']:,.2f}/km**\n"
                        f"- Rate = {result['per_km_rate']:,.2f} x {result['distance']:,.0f} "
                        f"= **Rs.{result['rate']:,.0f}**"
                    )


if CHAT_QUOTE_ENABLED:
    with tab_chat:
        st.caption('Try: "Pune to Solapur, need a 9 ft truck" or "Patna to Siliguri 450km, 9FT"')
        st.caption("Supported vehicles: 8FT, 9FT, 10FT, 11FT, 12FT, 14FT")
        query = st.text_input("Describe the shipment", key="chat_query")

        if st.button("Get Quote from Text", type="primary"):
            if not query.strip():
                st.error("Type a shipment description first.")
            else:
                try:
                    from nlp_extract import extract_query

                    with st.spinner("Parsing request..."):
                        extracted = extract_query(query)
                except Exception as e:
                    st.error(f"Could not parse query: {e}")
                    extracted = None

                if extracted:
                    origin_matched = match_origin(extracted.get("origin", ""))
                    destination_raw = extracted.get("destination", "").strip()
                    vehicle_matched = match_vehicle(extracted.get("vehicle_size", ""), rate_card_vehicles)
                    stated_distance = extracted.get("distance_km", 0) or 0

                    if not origin_matched:
                        st.error(f"Couldn't match origin '{extracted.get('origin')}' to a known hub.")
                    elif not vehicle_matched:
                        st.error(
                            f"Couldn't match vehicle '{extracted.get('vehicle_size')}' to a supported "
                            "size (8FT, 9FT, 10FT, 11FT, 12FT, 14FT)."
                        )
                    elif not destination_raw:
                        st.error("Couldn't find a destination in your request.")
                    else:
                        # Cost-friendly distance resolution: historical lookup (free)
                        # first, stated distance second, paid web search last resort.
                        distance, distance_source = resolve_distance(
                            origin_matched, destination_raw, dist_lookup, stated_distance
                        )
                        if distance <= 0:
                            try:
                                from nlp_extract import estimate_distance_via_search

                                with st.spinner("No historical data for this lane — searching..."):
                                    distance = estimate_distance_via_search(origin_matched, destination_raw)
                                distance_source = "web search (new lane)"
                            except Exception as e:
                                st.error(f"Could not determine distance: {e}")
                                distance = 0

                        if distance <= 0:
                            st.error(
                                f"No known distance for {origin_matched} -> {destination_raw}. "
                                "Mention the distance in km, e.g. '...450 km...'."
                            )
                        else:
                            try:
                                result = get_chat_quote(origin_matched, destination_raw, vehicle_matched, distance)
                            except ValueError as e:
                                st.error(str(e))
                            else:
                                st.markdown(
                                    f"""
                                    <div class="quote-card">
                                        <div class="label">Final Quoted Rate</div>
                                        <div class="price">Rs.{result['rate']:,.0f}</div>
                                        <div class="range">Rs.{result['rate_low']:,.0f} - Rs.{result['rate_high']:,.0f}</div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                                m1, m2, m3, m4 = st.columns(4)
                                m1.metric("Per-KM Rate", f"Rs.{result['per_km_rate']:,.2f}")
                                m2.metric("Distance", f"{result['distance_display']:,.0f} km")
                                m3.metric("Zone", result["zone"])
                                m4.metric("Zone Multiplier", f"x{result['zone_multiplier']}")
                                st.caption(
                                    f"Parsed: {origin_matched} -> {destination_raw}, "
                                    f"vehicle {result['vehicle']}, distance source: {distance_source}."
                                )

                                with st.expander("Calculation breakdown", expanded=True):
                                    st.markdown(
                                        f"- Origin: **{origin_matched}** ({result['zone']})\n"
                                        f"- Destination: **{destination_raw}**\n"
                                        f"- Vehicle: **{result['vehicle']}**\n"
                                        f"- Distance: **{result['distance']:,.0f} km** ({distance_source}) "
                                        f"(displayed above as {result['distance_display']:,.0f} km)\n"
                                        f"- Distance band: **{result['distance_band']}**\n"
                                        f"- Rate card per-km rate: **Rs.{result['per_km_rate']:,.2f}/km**\n"
                                        f"- Base rate = {result['per_km_rate']:,.2f} x {result['distance']:,.0f} "
                                        f"= **Rs.{result['base_rate']:,.0f}**\n"
                                        f"- Zone multiplier ({result['zone']}): x{result['zone_multiplier']}\n"
                                        f"- Final rate = {result['base_rate']:,.0f} x {result['zone_multiplier']} "
                                        f"= **Rs.{result['rate']:,.0f}**"
                                    )
