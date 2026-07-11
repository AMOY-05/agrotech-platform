from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.db.database import get_db
from app.models.db.user_model import PriceReport
from loguru import logger

router = APIRouter()


class PriceReportRequest(BaseModel):
    crop_type: str
    region: str
    price_ngn_per_kg: float
    farmer_id: Optional[str] = None
    notes: Optional[str] = None


class PriceReportResponse(BaseModel):
    success: bool
    message: str
    report_id: int


@router.post("/report", response_model=PriceReportResponse, tags=["Price Reports"])
async def submit_price_report(
    request: PriceReportRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Accepts crowdsourced price reports from farmers.
    Used to improve price forecast accuracy over time.
    """
    logger.info(
        f"Price report: {request.crop_type} ₦{request.price_ngn_per_kg}/kg "
        f"@ {request.region} from {request.farmer_id}"
    )

    try:
        report = PriceReport(
            farmer_id=request.farmer_id,
            crop_type=request.crop_type.lower().strip(),
            region=request.region,
            price_ngn_per_kg=str(request.price_ngn_per_kg),
            notes=request.notes,
            reported_at=datetime.utcnow()
        )

        db.add(report)
        await db.commit()
        await db.refresh(report)

        return PriceReportResponse(
            success=True,
            message="Price report submitted successfully. Thank you!",
            report_id=report.id
        )

    except Exception as e:
        logger.error(f"Price report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports", tags=["Price Reports"])
async def get_price_reports(
    crop_type: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns crowdsourced price reports.
    Used by admin dashboard and future price model retraining.
    """
    try:
        query = select(PriceReport).order_by(
            PriceReport.reported_at.desc()
        ).limit(limit)

        if crop_type:
            query = query.where(
                PriceReport.crop_type == crop_type.lower()
            )
        if region:
            query = query.where(
                PriceReport.region.ilike(f"%{region}%")
            )

        result = await db.execute(query)
        reports = result.scalars().all()

        return {
            "reports": [
                {
                    "id": r.id,
                    "crop_type": r.crop_type,
                    "region": r.region,
                    "price_ngn_per_kg": r.price_ngn_per_kg,
                    "notes": r.notes,
                    "reported_at": str(r.reported_at),
                    "farmer_id": r.farmer_id
                }
                for r in reports
            ],
            "total": len(reports)
        }

    except Exception as e:
        logger.error(f"Get reports failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))