"""高风险作业票业务规则：申请、审签、监护、延期、关闭的状态流转都收在这里。

许可状态序列：待审签 → 已审签 → 作业中 → 已关闭（审签驳回为终止分支）。
同一张票在列表页与详情页读的是同一条记录，状态字段统一为 status，
中文「许可状态」始终由 _sync_flags 同步，避免两个页面看到不同结果。
待审数的口径也只有一个：status == 待审签，概览页的 pending 标志按同一口径维护。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "workpermit"

# 高风险作业类别：动火、登高这两类是最常见的，其余按特殊作业规范补齐。
CATEGORIES = [
    "动火作业",
    "登高作业",
    "受限空间作业",
    "吊装作业",
    "临时用电作业",
    "动土作业",
    "断路作业",
    "盲板抽堵作业",
]

STATUS_PENDING = "待审签"
STATUS_REJECTED = "已驳回"
STATUS_APPROVED = "已审签"
STATUS_ONSITE = "作业中"
STATUS_CLOSED = "已关闭"
STATUS_ORDER = [
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_APPROVED,
    STATUS_ONSITE,
    STATUS_CLOSED,
]
# 需要现场跟进的活跃状态。
ACTIVE_STATUSES = [STATUS_APPROVED, STATUS_ONSITE]

REQUIRED_FIELDS = ["作业类别", "作业地点", "监护人", "有效期起", "有效期止"]
OPTIONAL_FIELDS = ["申请人", "作业内容", "作业票编号"]

# 系统内可执行的流转动作；每个动作允许的前置状态在 run_action 里逐条核对。
# 登记即进入「待审签」，没有单独的提交动作——重复点提交时直接提示，审签结论只落一次。
ACTION_APPROVE = "审签通过"
ACTION_REJECT = "审签驳回"
ACTION_ENTER = "进入现场"
ACTION_CONFIRM = "监护确认"
ACTION_POSTPONE = "申请延期"
ACTION_CLOSE = "关闭作业票"
ACTION_LABELS = [
    ACTION_APPROVE,
    ACTION_REJECT,
    ACTION_ENTER,
    ACTION_CONFIRM,
    ACTION_POSTPONE,
    ACTION_CLOSE,
]

TODAY = date.today().isoformat()


def _parse_date(value: Any) -> date | None:
    """把前端传上来的 YYYY-MM-DD 文本解析成日期；格式不对时返回 None 交回调用方提示。"""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


class WorkpermitService:
    # ----- 读取 -----
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        category: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            key = keyword.strip()
            rows = [
                row for row in rows
                if key in str(row.get("作业票编号", ""))
                or key in str(row.get("作业地点", ""))
                or key in str(row.get("监护人", ""))
            ]
        if category:
            rows = [row for row in rows if row.get("作业类别") == category]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def stats(self) -> dict[str, int]:
        """台账顶部的统计卡片；待审数与 /api/overview 里本模块 pending 同源同口径。"""
        rows = store.rows(MODULE)
        result = {label: 0 for label in STATUS_ORDER}
        for row in rows:
            label = str(row.get("status"))
            if label in result:
                result[label] += 1
        result["total"] = len(rows)
        result["待审数"] = result[STATUS_PENDING]
        return result

    # ----- 登记 -----
    def create_entry(
        self, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[str], str]:
        """登记作业票：必填缺失、类别越界、有效期不合理都要明确提示，不静默写库。"""
        missing = [
            field for field in REQUIRED_FIELDS
            if not str(values.get(field) or "").strip()
        ]
        if missing:
            return None, missing, ""

        category = str(values.get("作业类别")).strip()
        if category not in CATEGORIES:
            return None, [], f"作业类别「{category}」不在高风险作业票登记范围内"

        start = _parse_date(values.get("有效期起"))
        end = _parse_date(values.get("有效期止"))
        if start is None or end is None:
            return None, [], "有效期起止需为 YYYY-MM-DD 格式的日期"
        if end <= start:
            return None, [], "有效期止必须晚于有效期起"

        rows = store.rows(MODULE)
        next_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        code = str(values.get("作业票编号") or "").strip() or f"HWP-{next_id:04d}"

        entry: dict[str, Any] = {
            "id": next_id,
            "作业票编号": code,
            "作业类别": category,
            "作业地点": str(values.get("作业地点")).strip(),
            "监护人": str(values.get("监护人")).strip(),
            "申请人": str(values.get("申请人") or "").strip() or "值班人员",
            "作业内容": str(values.get("作业内容") or "").strip(),
            "有效期起": start.isoformat(),
            "有效期止": end.isoformat(),
            "登记时间": TODAY,
            "审签人": "",
            "审签结论": "",
            "审签时间": "",
            "审签说明": "",
            "监护人已确认": False,
            "监护确认时间": "",
            "关闭人": "",
            "关闭时间": "",
            "延期记录": [],
        }
        entry["status"] = STATUS_PENDING
        self._sync_flags(entry)
        rows.append(entry)
        return entry, [], ""

    # ----- 状态流转 -----
    def run_action(
        self,
        entry_id: int,
        action: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"作业票 {entry_id} 不存在或已归档"
        params = params or {}

        # 关闭之后不能再变更：任何动作一律拦下。
        if entry["status"] == STATUS_CLOSED:
            return None, "作业票已关闭，关闭之后不能再变更"

        handler = {
            ACTION_APPROVE: self._approve,
            ACTION_REJECT: self._reject,
            ACTION_ENTER: self._enter,
            ACTION_CONFIRM: self._confirm,
            ACTION_POSTPONE: self._postpone,
            ACTION_CLOSE: self._close,
        }.get(action)
        if handler is None:
            return None, f"动作「{action}」不属于高风险作业票可执行范围"
        return handler(entry, params)

    def _approve(
        self, entry: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        if entry["status"] != STATUS_PENDING:
            # 重复提交审签只留一次结果：已出结论的票不允许再覆盖。
            return None, f"当前许可状态为「{entry['status']}」，审签结果只保留一次，不能重复审签"
        entry["审签人"] = str(params.get("审签人") or "").strip() or "值班负责人"
        entry["审签结论"] = "通过"
        entry["审签说明"] = str(params.get("说明") or "").strip()
        entry["审签时间"] = TODAY
        entry["status"] = STATUS_APPROVED
        self._sync_flags(entry)
        return entry, "审签通过，作业票可进入现场"

    def _reject(
        self, entry: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        if entry["status"] != STATUS_PENDING:
            return None, f"当前许可状态为「{entry['status']}」，审签结果只保留一次，不能重复审签"
        entry["审签人"] = str(params.get("审签人") or "").strip() or "值班负责人"
        entry["审签结论"] = "驳回"
        entry["审签说明"] = str(params.get("说明") or "").strip() or "现场条件不满足安全要求"
        entry["审签时间"] = TODAY
        entry["status"] = STATUS_REJECTED
        self._sync_flags(entry)
        return entry, "审签驳回，作业票终止，不能进入现场"

    def _enter(
        self, entry: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        if entry["status"] != STATUS_APPROVED:
            return None, f"当前许可状态为「{entry['status']}」，只有审签通过的作业票才能进现场"
        entry["status"] = STATUS_ONSITE
        self._sync_flags(entry)
        return entry, "已进入现场开始作业，监护人全程在场监护"

    def _confirm(
        self, entry: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        if entry["status"] != STATUS_ONSITE:
            return None, f"当前许可状态为「{entry['status']}」，进场作业后才需要监护确认"
        if entry.get("监护人已确认"):
            return None, "监护人已确认过现场安全，无需重复确认"
        entry["监护人已确认"] = True
        entry["监护确认时间"] = TODAY
        self._sync_flags(entry)
        return entry, "监护人已确认现场安全，具备关闭条件"

    def _postpone(
        self, entry: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        if entry["status"] not in ACTIVE_STATUSES:
            return None, f"当前许可状态为「{entry['status']}」，只有已审签或作业中的票可以申请延期"
        new_start = _parse_date(params.get("新有效期起"))
        new_end = _parse_date(params.get("新有效期止"))
        if new_start is None or new_end is None:
            return None, "新有效期起止需为 YYYY-MM-DD 格式的日期"
        if new_end <= new_start:
            return None, "新有效期止必须晚于新有效期起"
        old_end = _parse_date(entry.get("有效期止"))
        if old_end is not None and new_end <= old_end:
            return None, "延期后的有效期止必须晚于当前有效期止"
        # 延期要切换到新的有效期，同时留下一条可追溯记录。
        history = entry.setdefault("延期记录", [])
        history.append({
            "原有效期起": entry["有效期起"],
            "原有效期止": entry["有效期止"],
            "新有效期起": new_start.isoformat(),
            "新有效期止": new_end.isoformat(),
            "延期时间": TODAY,
            "说明": str(params.get("说明") or "").strip() or "作业未完成，申请延期",
        })
        entry["有效期起"] = new_start.isoformat()
        entry["有效期止"] = new_end.isoformat()
        self._sync_flags(entry)
        return entry, f"有效期已切换为 {new_start.isoformat()} 至 {new_end.isoformat()}"

    def _close(
        self, entry: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        if entry["status"] != STATUS_ONSITE:
            return None, f"当前许可状态为「{entry['status']}」，现场作业完成后才能关闭作业票"
        # 监护人没有确认的不允许关闭。
        if not entry.get("监护人已确认"):
            return None, "监护人尚未确认现场安全，不允许关闭作业票"
        entry["关闭人"] = str(params.get("关闭人") or "").strip() or entry.get("监护人") or "值班人员"
        entry["关闭时间"] = TODAY
        entry["status"] = STATUS_CLOSED
        self._sync_flags(entry)
        return entry, "作业票已关闭，后续不可再变更"

    # ----- 内部口径 -----
    def _sync_flags(self, entry: dict[str, Any]) -> None:
        """状态、中文许可状态与概览 pending/abnormal 标志统一在这里维护，保证口径唯一。"""
        entry["许可状态"] = entry["status"]
        entry["pending"] = entry["status"] == STATUS_PENDING
        entry["abnormal"] = entry["status"] == STATUS_REJECTED
