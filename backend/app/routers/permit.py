"""高风险作业票接口：登记、审签、进现场、延期、监护确认到关闭的完整流转。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.permit import PermitService

router = APIRouter(prefix="/api/permit", tags=["高风险作业票"])

service = PermitService()

LIST_FIELDS = ["票号", "作业类别", "作业地点", "申请人", "监护人", "有效期至", "监护确认", "许可状态"]
STATUSES = ["待审签", "已审签", "作业中", "已关闭"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按票号检索"),
    status: str | None = Query(default=None, description="待审签、已审签、作业中、已关闭"),
    category: str | None = Query(default=None, description="动火作业、登高作业等作业类别"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按票号、许可状态与作业类别过滤作业票列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, category=category, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出高风险作业票台账：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "permit", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单张作业票明细；与列表共用同一条记录，许可状态保持一致。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"作业票 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一张作业票，作业类别、作业地点、监护人缺一不可，问题会写清原因。"""
    entry, problems = service.create_entry(payload.values)
    if problems:
        return ActionResult(ok=False, message="；".join(problems))
    return ActionResult(ok=True, message="作业票已登记，待审签", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单张作业票执行提交审签、开始作业、办理延期、监护确认、关闭作业票。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
