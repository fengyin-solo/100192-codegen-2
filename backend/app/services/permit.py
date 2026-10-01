"""高风险作业票业务规则：申请、审签、监护、延期与关闭的流转口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "permit"
REQUIRED_FIELDS = ["票号", "作业类别", "作业地点", "监护人"]
WORK_CATEGORIES = ["动火作业", "登高作业", "受限空间作业", "临时用电作业", "吊装作业"]
STATUS_ORDER = ["待审签", "已审签", "作业中", "已关闭"]
CLOSED_STATUS = "已关闭"
ENTRY_FIELDS = ["票号", "作业类别", "作业地点", "申请人", "作业单位", "监护人", "有效期至"]


class PermitService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        category: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("票号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if category:
            rows = [row for row in rows if row.get("作业类别") == category]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        problems: list[str] = []
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            problems.append(f"缺少必填字段：{'、'.join(missing)}")
        category = str(values.get("作业类别") or "").strip()
        if category and category not in WORK_CATEGORIES:
            problems.append(f"作业类别「{category}」不在高风险作业范围内（{'、'.join(WORK_CATEGORIES)}）")
        if problems:
            return None, problems
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in ENTRY_FIELDS:
            entry[field] = str(values.get(field) or "").strip()
        entry["监护确认"] = "未确认"
        entry["审签记录"] = []
        entry["status"] = STATUS_ORDER[0]
        entry["abnormal"] = False
        self._sync(entry)
        rows.append(entry)
        return entry, []

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"作业票 {entry_id} 不存在或已归档"
        if entry.get("status") == CLOSED_STATUS:
            return None, f"作业票 {entry_id} 已关闭，不能再变更"
        handlers = {
            "提交审签": self._approve,
            "开始作业": self._start_work,
            "办理延期": self._extend,
            "监护确认": self._confirm_guardian,
            "关闭作业票": self._close,
        }
        handler = handlers.get(action)
        if handler is None:
            return None, f"动作「{action}」不属于高风险作业票可执行范围"
        entry, message = handler(entry, values)
        if entry is not None:
            self._sync(entry)
        return entry, message

    def _approve(
        self, entry: dict[str, Any], values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        if entry.get("status") != "待审签":
            # 重复提交审签只留一次结果：状态与审签记录都不再变化
            return entry, "作业票已完成审签，重复提交不再变更"
        entry["status"] = "已审签"
        approver = str(values.get("审签人") or "").strip() or "值班安全员"
        entry["审签记录"] = [{"审签人": approver, "结果": "同意"}]
        return entry, "作业票审签通过，可安排进现场"

    def _start_work(
        self, entry: dict[str, Any], values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        status = entry.get("status")
        if status == "待审签":
            return None, "审签通过后才能进现场作业"
        if status != "已审签":
            return None, f"作业票当前状态为{status}，不能重复开始作业"
        entry["status"] = "作业中"
        return entry, "作业票已进现场，作业中"

    def _extend(
        self, entry: dict[str, Any], values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        if entry.get("status") not in ("已审签", "作业中"):
            return None, "待审签的作业票尚未生效，先完成审签再办理延期"
        new_due = str(values.get("有效期至") or "").strip()
        if not new_due:
            return None, "办理延期需填写新的有效期"
        current_due = str(entry.get("有效期至") or "").strip()
        if current_due and new_due <= current_due:
            return None, f"新的有效期需晚于当前有效期 {current_due}"
        entry["有效期至"] = new_due
        return entry, f"作业票已延期，有效期至 {new_due}"

    def _confirm_guardian(
        self, entry: dict[str, Any], values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        if entry.get("status") not in ("已审签", "作业中"):
            return None, "待审签的作业票无需监护确认"
        if entry.get("监护确认") == "已确认":
            return entry, "监护人已确认过，无需重复确认"
        entry["监护确认"] = "已确认"
        return entry, "监护人已确认现场安全"

    def _close(
        self, entry: dict[str, Any], values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        if entry.get("监护确认") != "已确认":
            return None, "监护人未确认，不允许关闭作业票"
        entry["status"] = CLOSED_STATUS
        return entry, "作业票已关闭"

    def _sync(self, entry: dict[str, Any]) -> None:
        """列表、详情与概览共用同一条记录：许可状态与待审标记始终跟着 status 走。"""
        entry["许可状态"] = entry.get("status")
        entry["pending"] = entry.get("status") == "待审签"
