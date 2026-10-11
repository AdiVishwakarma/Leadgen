"""Lead discovery via Google Places API (New) - Text Search."""
import httpx

from .config import settings

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.primaryTypeDisplayName",
    ]
)


def search_places(category: str, city: str, limit: int = 20) -> list[dict]:
    """Return normalized business dicts for `category` in `city`."""
    if not settings.google_places_api_key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY is not set")

    results: list[dict] = []
    page_token: str | None = None

    with httpx.Client(timeout=20) as client:
        while len(results) < limit:
            body = {"textQuery": f"{category} in {city}", "pageSize": min(20, limit - len(results))}
            if page_token:
                body["pageToken"] = page_token

            resp = client.post(
                PLACES_URL,
                json=body,
                headers={
                    "X-Goog-Api-Key": settings.google_places_api_key,
                    "X-Goog-FieldMask": FIELD_MASK + ",nextPageToken",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            for p in data.get("places", []):
                results.append(
                    {
                        "place_id": p["id"],
                        "name": p.get("displayName", {}).get("text", "Unknown"),
                        "category": p.get("primaryTypeDisplayName", {}).get("text", category),
                        "address": p.get("formattedAddress"),
                        "phone": p.get("nationalPhoneNumber"),
                        "website": p.get("websiteUri"),
                        "rating": p.get("rating"),
                        "review_count": p.get("userRatingCount"),
                        "city": city,
                    }
                )

            page_token = data.get("nextPageToken")
            if not page_token:
                break

    return results[:limit]
