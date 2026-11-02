
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-haiku-5-5"

BASIC_EXTRACT_TOOL = {
    "name": "extract_freight_basics",
    "description": (
        "Extract the origin city, destination city, and vehicle size from a "
        "free-text freight quote request. Do not estimate distance here."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "origin": {
                "type": "string",
                "description": "The pickup/origin city as the user wrote it. Empty string if not mentioned.",
            },
            "destination": {
                "type": "string",
                "description": "The drop/destination city as the user wrote it. Empty string if not mentioned.",
            },
            "vehicle_size": {
                "type": "string",
                "description": (
                    "Vehicle size/type as the user wrote it, e.g. '9 FT', '32 FT', "
                    "'Tata 407'. Empty string if not mentioned."
                ),
            },
            "distance_km": {
                "type": "number",
                "description": (
                    "ONLY fill this if the user explicitly stated a distance in km. "
                    "Use 0 otherwise — do not estimate or guess."
                ),
            },
        },
        "required": ["origin", "destination", "vehicle_size", "distance_km"],
    },
}

DISTANCE_TOOL = {
    "name": "report_distance",
    "description": "Report the one-way road distance in km you found via web search.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "distance_km": {
                "type": "number",
                "description": "The one-way road distance in km between the two cities, found via web search.",
            },
        },
        "required": ["distance_km"],
    },
}


def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it before running the app:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )
    return anthropic.Anthropic(api_key=api_key)


def extract_query(text: str) -> dict:
    """Parse free text into {origin, destination, vehicle_size, distance_km}.
    distance_km is 0 unless the user stated it explicitly — the caller is
    expected to resolve the real distance (historical lookup first, web
    search only as a fallback) via estimate_distance_via_search()."""
    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        tools=[BASIC_EXTRACT_TOOL],
        tool_choice={"type": "auto"},
        system=(
            "You must always call the extract_freight_basics tool to answer, "
            "never respond with plain text."
        ),
        messages=[{"role": "user", "content": text}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_freight_basics":
            return block.input

    raise RuntimeError("Model did not return a structured extraction.")


def estimate_distance_via_search(origin: str, destination: str) -> float:
    """Paid fallback: web-search the real one-way road distance for a lane
    with no historical data. Only call this when a historical lookup misses."""
    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        tools=[
           
            {"type": "web_search_20250305", "name": "web_search", "max_uses": 1},
            DISTANCE_TOOL,
        ],
        tool_choice={"type": "auto"},
        system=(
            f"Use the web_search tool once to find the one-way road distance in km "
            f"from {origin} to {destination} in India (not straight-line distance). "
            "Then call report_distance with the number. Never respond with plain text."
        ),
        messages=[{"role": "user", "content": f"Distance from {origin} to {destination}?"}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "report_distance":
            return float(block.input.get("distance_km", 0))

    raise RuntimeError("Model did not return a distance.")
