"""Deploy a single index.html to Vercel via the REST API (no CLI needed)."""
import httpx

from .config import settings

VERCEL_URL = "https://api.vercel.com/v13/deployments"


class DeployError(RuntimeError):
    pass


def deploy_html(project_name: str, html_text: str) -> dict:
    if not settings.vercel_token:
        raise DeployError("VERCEL_TOKEN is not set")

    params = {"teamId": settings.vercel_team_id} if settings.vercel_team_id else None
    body = {
        "name": project_name,
        "files": [{"file": "index.html", "data": html_text}],
        "projectSettings": {"framework": None},
        # Production target gives a stable project-name.vercel.app alias.
        "target": "production",
    }
    try:
        resp = httpx.post(
            VERCEL_URL,
            json=body,
            params=params,
            headers={"Authorization": f"Bearer {settings.vercel_token}"},
            timeout=60,
        )
    except httpx.HTTPError as exc:
        raise DeployError(f"Network error talking to Vercel: {type(exc).__name__}")

    if resp.status_code not in (200, 201):
        raise DeployError(f"Vercel returned {resp.status_code}: {resp.text[:300]}")

    d = resp.json()
    aliases = d.get("alias") or []
    host = aliases[0] if aliases else d.get("url")
    if not host:
        raise DeployError(f"Vercel response had no URL: {str(d)[:300]}")
    return {"deployment_id": d.get("id"), "url": f"https://{host}", "state": d.get("readyState")}