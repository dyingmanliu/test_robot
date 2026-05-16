"""用户已租用的机器人实例：列表与展示属性编辑。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import RobotInstance, User
from app.schemas import RobotInstanceOut, RobotInstancePatch

router = APIRouter(prefix="/robot-instances", tags=["robot-instances"])


def _instance_readable(user: User, inst: RobotInstance) -> bool:
    if user.company_id is not None and inst.company_id is not None and inst.company_id == user.company_id:
        return True
    return inst.user_id == user.id


@router.get("/mine", response_model=list[RobotInstanceOut])
def list_my_instances(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RobotInstance]:
    q = db.query(RobotInstance)
    if user.company_id is not None:
        q = q.filter(RobotInstance.company_id == user.company_id)
    else:
        q = q.filter(RobotInstance.user_id == user.id)
    return q.order_by(RobotInstance.id.desc()).all()


@router.get("/{instance_id}", response_model=RobotInstanceOut)
def get_my_instance(
    instance_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RobotInstance:
    inst = db.query(RobotInstance).filter(RobotInstance.id == instance_id).first()
    if inst is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机器人实例不存在")
    if not _instance_readable(user, inst):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该实例")
    return inst


@router.patch("/{instance_id}", response_model=RobotInstanceOut)
def patch_my_instance(
    instance_id: int,
    body: RobotInstancePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RobotInstance:
    inst = db.query(RobotInstance).filter(RobotInstance.id == instance_id).first()
    if inst is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机器人实例不存在")
    if inst.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改该实例")
    if body.display_name is not None:
        inst.display_name = body.display_name
    if body.display_bio is not None:
        inst.display_bio = body.display_bio
    if body.test_agent_backend is not None:
        inst.test_agent_backend = body.test_agent_backend
    db.commit()
    db.refresh(inst)
    return inst
