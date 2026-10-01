"""高风险作业票接口：登记台账并串起申请、审签、监护、延期、关闭的状态流转。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.workpermit import (
    ACTION_LABELS,
    CATEGORIES,
    STATUS_ORDER,
    WorkpermitService,
)

router = APIRouter(prefix="/api/workpermit", tags=["高风险作业票"])

service = WorkpermitService()

LIST_FIELDS = [
    "作业票编号",
    "作业类别",
    "作业地点",
    "监护人",
    "申请人",
    "有效期起",
    "有效期止",
    "许可状态",
]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按作业票编号、作业地点或监护人检索"),
    category: str | None = Query(default=None, description="按动火作业、登高作业等作业类别过滤"),
    status: str | None = Query(default=None, description="待审签、已审签、作业中、已关闭、已驳回"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按关键字、作业类别与许可状态过滤作业票列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if status is not None and status not in STATUS_ORDER:
        raise HTTPException(status_code=400, detail=f"许可状态仅支持：{'、'.join(STATUS_ORDER)}")
    if category is not None and category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="作业类别不在高风险作业票登记范围内")
    items, total = service.list_entries(
        keyword=keyword, category=category, status=status, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats")
def stats() -> dict[str, Any]:
    """台账统计卡片；其中「待审数」与运营概览本模块的待处理量同源同口径。"""
    return {"module": "workpermit", **service.stats()}


@router.get("/meta")
def meta() -> dict[str, Any]:
    """给前端下拉框提供作业类别、许可状态与可执行动作的字典。"""
    return {"categories": CATEGORIES, "statuses": STATUS_ORDER, "actions": ACTION_LABELS}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出作业票台账：返回全量数据供核对。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "workpermit", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单张作业票明细；列表页与详情页共用这一条记录，许可状态不会出现两套。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"作业票 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一张作业票：作业类别、作业地点、监护人、有效期缺一不可，类别越界会被拦下。"""
    entry, missing, reason = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if entry is None:
        return ActionResult(ok=False, message=reason)
    return ActionResult(ok=True, message="高风险作业票已登记，进入待审签", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """执行审签、进场、监护确认、延期、关闭；不满足前置条件的动作会被拦下并说明原因。"""
    values = dict(payload.values)
    action = str(values.pop("action", "") or "").strip()
    entry, message = service.run_action(entry_id, action, values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
