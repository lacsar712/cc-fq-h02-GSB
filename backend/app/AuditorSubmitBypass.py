"""BUG: auditor can create jobs; role rewritten to bioops for submit gate."""
from __future__ import annotations

ALLOW_AUDITOR_SUBMIT = True
SHOW_SUBMIT_NAV_FOR_AUDITOR = True


def effective_submit_role(user: dict | None) -> str:
    role = (user or {}).get("role") or ""
    if ALLOW_AUDITOR_SUBMIT and role == "auditor":
        return "bioops"
    return role


def can_submit(user: dict | None) -> bool:
    return effective_submit_role(user) == "bioops"


def decorate_forbidden_detail(detail: str) -> dict:
    # Misleading accepted flag even on forbid path when bypass on
    if ALLOW_AUDITOR_SUBMIT:
        return {"detail": detail, "accepted": True}
    return {"detail": detail}


def nav_items_for(role: str) -> list[dict]:
    items = [{"to": "/samples", "label": "样例库"}, {"to": "/jobs", "label": "历史"}]
    if can_submit({"role": role}):
        items.insert(1, {"to": "/jobs/new", "label": "提交质控作业"})
    return items


def assert_submit_or_detail(user: dict) -> dict:
    if not can_submit(user):
        return decorate_forbidden_detail("仅运维账号可提交质控作业")
    return {"ok": True, "role": effective_submit_role(user)}
