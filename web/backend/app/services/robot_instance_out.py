"""RobotInstance ORM → API 出参（含 runtime_status）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import RobotInstance
from app.schemas import RobotInstanceOut
from app.services.robot_run_guard import (
    find_active_run_for_instance,
    resolve_instance_runtime_status,
)


def robot_instance_to_out(db: Session, inst: RobotInstance) -> RobotInstanceOut:
    base = RobotInstanceOut.model_validate(inst)
    active = find_active_run_for_instance(db, inst.id)
    return base.model_copy(
        update={
            "runtime_status": resolve_instance_runtime_status(db, inst),
            "active_run_id": active.id if active else None,
        }
    )
