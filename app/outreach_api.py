import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .db import get_db
from .llm import LLMError
from .outreach import generate_message

router = APIRouter(tags=["outreach"])

# Gemini free tier is roughly 10-15 requests/minute. Space batch calls out.
BATCH_GAP_SECONDS = 5


class OutreachOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    channel: str
    language: str
    message: str
    status: str


def _draft_for(db: Session, lead: models.Lead, language: str) -> models.Outreach:
    latest_audit = db.scalars(
        select(models.Audit).where(models.Audit.lead_id == lead.id).order_by(models.Audit.id.desc()).limit(1)
    ).first()
    if not latest_audit:
        raise HTTPException(status_code=400, detail="Audit this lead first")

    lead_dict = {
        "name": lead.name,
        "category": lead.category,
        "city": lead.city,
        "website": lead.website,
        "review_count": lead.review_count,
        "rating": lead.rating,
    }
    try:
        message = generate_message(lead_dict, latest_audit.reasons, language)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    row = models.Outreach(lead_id=lead.id, message=message, language=language)
    db.add(row)
    lead.status = "drafted"
    db.commit()
    db.refresh(row)
    return row


@router.post("/leads/{lead_id}/outreach", response_model=OutreachOut)
def create_draft(lead_id: int, language: str = Query(default="english", pattern="^(english|hinglish)$"),
                 db: Session = Depends(get_db)):
    lead = db.get(models.Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _draft_for(db, lead, language)


@router.post("/outreach/generate-pending")
def generate_pending(
    min_score: int = Query(default=70, ge=0, le=100),
    batch: int = Query(default=5, ge=1, le=20),
    language: str = Query(default="english", pattern="^(english|hinglish)$"),
    db: Session = Depends(get_db),
):
    """Draft messages for top audited leads that have none yet. n8n calls this."""
    leads = db.scalars(
        select(models.Lead)
        .where(models.Lead.status == "audited", models.Lead.score >= min_score)
        .order_by(models.Lead.score.desc())
        .limit(batch)
    ).all()

    drafted, failed = 0, []
    for i, lead in enumerate(leads):
        if i:
            time.sleep(BATCH_GAP_SECONDS)
        try:
            _draft_for(db, lead, language)
            drafted += 1
        except HTTPException as exc:
            failed.append({"lead_id": lead.id, "error": exc.detail})
    return {"drafted": drafted, "failed": failed}


@router.get("/outreach", response_model=list[OutreachOut])
def list_outreach(status: str = "draft", limit: int = Query(default=50, ge=1, le=200),
                  db: Session = Depends(get_db)):
    return db.scalars(
        select(models.Outreach).where(models.Outreach.status == status).order_by(models.Outreach.id).limit(limit)
    ).all()


def _set_status(db: Session, outreach_id: int, allowed_from: set[str], new: str) -> models.Outreach:
    row = db.get(models.Outreach, outreach_id)
    if not row:
        raise HTTPException(status_code=404, detail="Outreach not found")
    if row.status not in allowed_from:
        raise HTTPException(status_code=409, detail=f"Cannot go from '{row.status}' to '{new}'")
    row.status = new
    if new == "sent":
        row.lead.status = "contacted"
    db.commit()
    db.refresh(row)
    return row


@router.post("/outreach/{outreach_id}/approve", response_model=OutreachOut)
def approve(outreach_id: int, db: Session = Depends(get_db)):
    return _set_status(db, outreach_id, {"draft"}, "approved")


@router.post("/outreach/{outreach_id}/reject", response_model=OutreachOut)
def reject(outreach_id: int, db: Session = Depends(get_db)):
    return _set_status(db, outreach_id, {"draft", "approved"}, "rejected")


@router.post("/outreach/{outreach_id}/mark-sent", response_model=OutreachOut)
def mark_sent(outreach_id: int, db: Session = Depends(get_db)):
    """You send it manually (WhatsApp/email), then call this so the lead moves to 'contacted'."""
    return _set_status(db, outreach_id, {"approved"}, "sent")
