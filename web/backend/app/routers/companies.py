"""注册时可拉取已有公司列表（供选择）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company
from app.schemas import CompanyPublicOut

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyPublicOut])
def list_companies_for_register(db: Session = Depends(get_db)) -> list[Company]:
    return db.query(Company).order_by(Company.name.asc()).all()
