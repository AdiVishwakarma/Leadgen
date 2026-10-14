"""Deploy a single index.html to Vercel via the REST API (no CLI needed)."""
import time

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


def _wait_ready(deployment_id: str, params: dict | None, headers: dict, tries: int = 15) -> str | None:
    """Poll until the deployment is READY (or failed). Returns the final state, or None on timeout."""
    for _ in range(tries):
        try:
            r = httpx.get(f"{VERCEL_URL}/{deployment_id}", params=params, headers=headers, timeout=20)
            if r.status_code == 200:
                state = r.json().get("readyState")
                if state in ("READY", "ERROR", "CANCELED"):
                    return state
        except httpx.HTTPError:
            pass
        time.sleep(3)
    return None


def _public_host(project_id: str, project_name: str, params: dict | None, headers: dict) -> str:
    """Ask Vercel which vercel.app domains the project really has; the shortest one is the plain
    project-name.vercel.app (the ones with the account name added stay behind the login wall)."""
    try:
        r = httpx.get(f"{PROJECT_URL}/{project_id}/domains", params=params, headers=headers, timeout=20)
        if r.status_code == 200:
            names = [d["name"] for d in r.json().get("domains", []) if d.get("name", "").endswith(".vercel.app")]
            if names:
                return min(names, key=len)
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    return f"{project_name}.vercel.app"


def _is_open(url: str) -> bool:
    """True if a stranger (no Vercel login) can load the page."""
    try:
        r = httpx.get(url, follow_redirects=True, timeout=20)
    except httpx.HTTPError:
        return False
    return r.status_code == 200 and "vercel.com/sso" not in str(r.url) and "<html" in r.text.lower()


def deploy_html(project_name: str, html_text: str) -> dict:
    if not settings.vercel_token:
        raise DeployError("VERCEL_TOKEN is not set")

    params = {"teamId": settings.vercel_team_id} if settings.vercel_team_id else None
    headers = {"Authorization": f"Bearer {settings.vercel_token}"}
    body = {
        "name": project_name,
        "files": [{"file": "index.html", "data": html_text}],
        "projectSettings": {"framework": None},
        "target": "production",
    }
    try:
        resp = httpx.post(VERCEL_URL, json=body, params=params, headers=headers, timeout=60)
    except httpx.HTTPError as exc:
        raise DeployError(f"Network error talking to Vercel: {type(exc).__name__}")

    if resp.status_code not in (200, 201):
        raise DeployError(f"Vercel returned {resp.status_code}: {resp.text[:300]}")

    d = resp.json()
    project_id, deployment_id = d.get("projectId"), d.get("id")
    if not project_id or not deployment_id:
        raise DeployError(f"Vercel response had no project/deployment id: {str(d)[:300]}")

    # Without this the link shows "Log in to Vercel" to everyone except you.
    problem = _make_public(project_id, params, headers)
    if problem:
        raise DeployError(
            f"Page deploy ho gaya par public nahi ho paaya: {problem}. "
            "Project Settings > Deployment Protection > Vercel Authentication manually band kar."
        )

    state = _wait_ready(deployment_id, params, headers) or d.get("readyState")
    if state in ("ERROR", "CANCELED"):
        raise DeployError(f"Vercel deployment {state}. Vercel dashboard me us project ke Deployments tab me logs dekh.")

    host = _public_host(project_id, d.get("name") or project_name, params, headers)
    url = f"https://{host}"
    return {"deployment_id": deployment_id, "url": url, "state": state, "public": _is_open(url)}