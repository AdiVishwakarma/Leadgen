from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import models
from .db import get_db
from .deploy import DeployError, deploy_html
from .sitegen import build_site, slugify

router = APIRouter(tags=["sites"])


class SiteOut(BaseModel):
    lead_id: int
    url: str
    deployment_id: str | None


def _lead_dict(lead: models.Lead) -> dict:
    return {
        "name": lead.name,
        "category": lead.category,
        "city": lead.city,
        "address": lead.address,
        "phone": lead.phone,
        "rating": lead.rating,
        "review_count": lead.review_count,
        "place_id": lead.place_id,
    }


def _get_lead(db: Session, lead_id: int) -> models.Lead:
    lead = db.get(models.Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.get("/leads/{lead_id}/site/preview", response_class=HTMLResponse)
def preview_site(lead_id: int, db: Session = Depends(get_db)):
    """Render the page locally without deploying. Open this in your browser first."""
    return build_site(_lead_dict(_get_lead(db, lead_id)))


@router.post("/leads/{lead_id}/site", response_model=SiteOut)
def create_site(lead_id: int, db: Session = Depends(get_db)):
    """Generate the page and deploy it to Vercel. Returns the shareable URL."""
    lead = _get_lead(db, lead_id)
    html_text = build_site(_lead_dict(lead))
    try:
        result = deploy_html(f"preview-{slugify(lead.name)}-{lead.id}", html_text)
    except DeployError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    row = models.Site(lead_id=lead.id, url=result["url"], deployment_id=result["deployment_id"])
    db.add(row)
    if lead.status in ("new", "audited", "drafted"):
        lead.status = "site_ready"
    db.commit()
    return SiteOut(lead_id=lead.id, url=row.url, deployment_id=row.deployment_id)


@router.get("/leads/{lead_id}/site", response_model=list[SiteOut])
def list_sites(lead_id: int, db: Session = Depends(get_db)):
    rows = db.query(models.Site).filter(models.Site.lead_id == lead_id).order_by(models.Site.id.desc()).all()
    return [SiteOut(lead_id=r.lead_id, url=r.url, deployment_id=r.deployment_id) for r in rows]