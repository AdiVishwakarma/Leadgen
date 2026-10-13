"""Deploy a single index.html to Vercel via the REST API (no CLI needed)."""
import httpx

from .config import settings

VERCEL_URL = "https://api.vercel.com/v13/deployments"
PROJECT_URL = "https://api.vercel.com/v9/projects"


class DeployError(RuntimeError):
    pass


def _make_public(project_id: str, params: dict | None, headers: dict) -> str | None:
    """Turn off Vercel Authentication so clients can open the link without a Vercel login.
    Returns an error text, or None if it worked."""
    try:
        r = httpx.patch(
            f"{PROJECT_URL}/{project_id}",
            json={"ssoProtection": None},
            params=params,
            headers=headers,
            timeout=30,
        )
    except httpx.HTTPError as exc:
        return f"network error ({type(exc).__name__})"
    if r.status_code not in (200, 201):
        return f"{r.status_code}: {r.text[:200]}"
    return None


def deploy_html(project_name: str, html_text: str) -> dict:
    if not settings.vercel_token:
        raise DeployError("VERCEL_TOKEN is not set")

    params = {"teamId": settings.vercel_team_id} if settings.vercel_team_id else None
    headers = {"Authorization": f"Bearer {settings.vercel_token}"}
    body = {
        "name": project_name,
        "files": [{"file": "index.html", "data": html_text}],
        "projectSettings": {"framework": None},
        # Production target gives a stable project-name.vercel.app alias.
        "target": "production",
    }
    try:
        resp = httpx.post(VERCEL_URL, json=body, params=params, headers=headers, timeout=60)
    except httpx.HTTPError as exc:
        raise DeployError(f"Network error talking to Vercel: {type(exc).__name__}")

    if resp.status_code not in (200, 201):
        raise DeployError(f"Vercel returned {resp.status_code}: {resp.text[:300]}")

    d = resp.json()
    aliases = d.get("alias") or []
    host = aliases[0] if aliases else d.get("url")
    if not host:
        raise DeployError(f"Vercel response had no URL: {str(d)[:300]}")

    # Without this the link shows "Log in to Vercel" to everyone except you.
    if d.get("projectId"):
        problem = _make_public(d["projectId"], params, headers)
        if problem:
            raise DeployError(
                f"Page deploy ho gaya ({host}) par public nahi ho paaya: {problem}. "
                "Project Settings > Deployment Protection > Vercel Authentication manually band kar."
            )
    return {"deployment_id": d.get("id"), "url": f"https://{host}", "state": d.get("readyState")}