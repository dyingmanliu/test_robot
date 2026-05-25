"""功能树工具接口。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from agent_service.analysis_agent.feature_explore.tree_build import (
    build_function_tree_by_path,
    sync_giic_tree_from_features,
)
from agent_service.service.schemas import BuildFunctionTreeRequest, SyncGiicRequest

log = logging.getLogger("agent_service.tree")

router = APIRouter()


@router.post("/api/agent/tree/sync-giic")
async def sync_giic(req: SyncGiicRequest):
    normalized = sync_giic_tree_from_features(dict(req.tree_json))
    return JSONResponse(content=normalized)


@router.post("/api/agent/tree/build-function-tree")
async def build_function_tree(req: BuildFunctionTreeRequest):
    tree = build_function_tree_by_path(req.app_name, req.features)
    return JSONResponse(content=tree)
