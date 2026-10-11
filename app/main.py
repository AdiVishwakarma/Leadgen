from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit as audit_mod
from . import discovery, models, schemas
from .db import Base, engine, get_db
from .outreach_api import router as outreach_router
from .scoring import score_lead

app = FastAPI(title="Lead Gen API", version="0.2.0")
app.include_router(outreach_router)


@app.on_event("startup")
def create_tables() -> None:
    # Fine for a first version. Move to Alembic migrations before this grows.
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/discover", response_model=schemas.DiscoverResponse)
def discover(req: schemas.DiscoverRequest, db: Session = Depends(get_db)):
    try:
        places = discovery.search_places(req.category, req.city, req.limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    inserted = 0
    for p in places:
        exists = db.scalar(select(models.Lead.id).where(models.Lead.place_id == p["place_id"]))
        if exists:
            continue
        db.add(models.Lead(**p))
        inserted += 1
    db.commit()
    return schemas.DiscoverResponse(found=len(places), inserted=inserted, skipped_duplicates=len(places) - inserted)


def _audit_lead(db: Session, lead: models.Lead) -> models.Audit:
    signals = audit_mod.audit_website(lead.website)
    lead_dict = {
        "review_count": lead.review_count,
        "rating": lead.rating,
        "phone": lead.phone,
    }
    score, reasons = score_lead(lead_dict, signals)
    row = models.Audit(lead_id=lead.id, signals=signals, score=score, reasons=reasons)
    db.add(row)
    lead.score = score
    if lead.status == "new":
        lead.status = "audited"
    db.commit()
    db.refresh(row)
    return row


@app.post("/leads/{lead_id}/audit", response_model=schemas.AuditOut)
def audit_one(lead_id: int, db: Session = Depends(get_db)):
    lead = db.get(models.Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _audit_lead(db, lead)


@app.post("/audit/pending")
def audit_pending(batch: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)):
    """Audit up to `batch` leads that are still status=new. n8n calls this on a schedule."""
    leads = db.scalars(select(models.Lead).where(models.Lead.status == "new").limit(batch)).all()
    for lead in leads:
        _audit_lead(db, lead)
    return {"audited": len(leads)}


@app.get("/leads", response_model=list[schemas.LeadOut])
def list_leads(
    min_score: int = Query(default=0, ge=0, le=100),
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = select(models.Lead).where(models.Lead.score >= min_score)
    if status:
        q = q.where(models.Lead.status == status)
    q = q.order_by(models.Lead.score.desc().nulls_last()).limit(limit)
    return db.scalars(q).all()


@app.get("/leads/{lead_id}/audits", response_model=list[schemas.AuditOut])
def lead_audits(lead_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.Audit).where(models.Audit.lead_id == lead_id).order_by(models.Audit.id.desc())
    ).all()
    return rows
