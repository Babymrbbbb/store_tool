"""多 Agent 门店执行闭环（合成参考实现）——在单状态机之上编排三角色协作。

借鉴 Orkas / ECC 的「多 Agent 协作」范式：把原本隐式的
「总部下发 → 门店执行 → 门店验收」拆成三个显式 Agent 角色，每一步都有
结构化握手（AgentMessage）与回传（ExecutionReport），便于审计与回放。

完全复用 store_loop 的状态机（dispatched → executed → accepted）与合成数据
（A/B/C/D 四市共 12 家），**不含任何真实门店名 / 经营数据 / 内部业务系统描述**。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlmodel import Session, select

from app import store_loop as loop
from app.store_loop import Dispatch


class ReviewRejected(Exception):
    """验收 Agent 驳回：执行报告不满足验收条件，不推进到 accepted。"""


@dataclass
class AgentMessage:
    """Agent 之间的最小握手单元（合成）。"""

    sender: str
    receiver: str
    kind: str  # plan / execute / review / feedback
    payload: dict
    at: str = field(default_factory=loop.now_iso)


@dataclass
class ExecutionReport:
    """门店 Agent 回传的执行报告（合成）。"""

    dispatch_id: int
    store_code: str
    card_code: str
    executed_at: str
    note: str
    ok: bool


class HQAgent:
    """总部 Agent：拆解目标 → 选定作战卡与门店 → 下发（置 dispatched）。"""

    name = "HQ"

    def plan(self, objective: str, store_codes=None, card_codes=None) -> AgentMessage:
        cards = card_codes or [c[0] for c in loop.BATTLE_CARDS]
        stores = store_codes or [
            f"{city[0]}{i:02d}"
            for city, n in loop.CITY_PLAN.items()
            for i in range(1, n + 1)
        ]
        return AgentMessage(
            self.name,
            "Store",
            "plan",
            {"objective": objective, "stores": stores, "cards": cards},
        )

    def dispatch(self, plan: AgentMessage) -> list[int]:
        """确保计划内的 (门店, 卡) 都有 dispatched 记录；返回 dispatch id 列表。"""
        ids: list[int] = []
        with Session(loop._engine) as s:
            for st in plan.payload["stores"]:
                for cd in plan.payload["cards"]:
                    existing = s.exec(
                        select(Dispatch).where(
                            Dispatch.store_code == st, Dispatch.card_code == cd
                        )
                    ).first()
                    if existing:
                        ids.append(existing.id)
                        continue
                    d = Dispatch(
                        store_code=st,
                        card_code=cd,
                        status="dispatched",
                        dispatched_at=loop.now_iso(),
                    )
                    s.add(d)
                    s.commit()
                    s.refresh(d)
                    ids.append(d.id)
        return ids


class StoreAgent:
    """门店 Agent：执行下发的作战卡 → 回传执行报告（推进到 executed）。"""

    name = "Store"

    def execute(self, dispatch_id: int, note: str = "", ok: bool = True) -> ExecutionReport:
        disp = loop.advance(dispatch_id, "executed")  # 复用状态机，非法跳步会抛错
        return ExecutionReport(
            dispatch_id=disp.id,
            store_code=disp.store_code,
            card_code=disp.card_code,
            executed_at=disp.executed_at,
            note=note or f"{disp.store_code} 已完成 {disp.card_code} 标准动作",
            ok=ok,
        )


class ReviewAgent:
    """验收 Agent：校验执行报告 → 通过则推进到 accepted，否则驳回（保持 executed）。"""

    name = "Review"

    def review(self, report: ExecutionReport) -> AgentMessage:
        # 验收条件（合成、通用）：执行成功且回传说明非空
        if not report.ok:
            raise ReviewRejected(f"执行未成功（dispatch {report.dispatch_id}），保持 executed 待重做")
        if not report.note or len(report.note.strip()) < 4:
            raise ReviewRejected(f"执行报告说明过短（dispatch {report.dispatch_id}），保持 executed 待补录")
        loop.advance(report.dispatch_id, "accepted")  # 复用状态机
        return AgentMessage(
            self.name,
            "HQ",
            "review",
            {"dispatch_id": report.dispatch_id, "decision": "accepted"},
        )


def run_campaign(
    objective: str, store_codes=None, card_codes=None
) -> dict:
    """端到端跑一场多 Agent 战役：HQ 下发 → 各门店执行 → 验收。

    返回：消息日志 + 各状态计数（accepted / needs_rework）。
    """
    hq, store, review = HQAgent(), StoreAgent(), ReviewAgent()
    messages: list[AgentMessage] = []

    plan = hq.plan(objective, store_codes=store_codes, card_codes=card_codes)
    messages.append(plan)
    ids = hq.dispatch(plan)

    # 仅处理尚未推进的下发记录，保证「重跑战役」幂等：已 executed / accepted 的跳过，
    # 否则 StoreAgent.execute 会对 accepted 记录执行 executed→executed 的非法跳步而崩溃。
    with Session(loop._engine) as s:
        dispatched_ids = [
            d.id
            for d in s.exec(
                select(Dispatch).where(
                    Dispatch.id.in_(ids), Dispatch.status == "dispatched"
                )
            )
        ]

    accepted, needs_rework = 0, 0
    for did in dispatched_ids:
        report = store.execute(did)
        messages.append(
            AgentMessage(store.name, review.name, "execute", report.__dict__)
        )
        try:
            msg = review.review(report)
            messages.append(msg)
            accepted += 1
        except ReviewRejected as e:
            messages.append(
                AgentMessage(review.name, store.name, "feedback", {"reason": str(e)})
            )
            needs_rework += 1

    return {
        "objective": objective,
        "messages": messages,
        "accepted": accepted,
        "needs_rework": needs_rework,
        "stats": loop.stats(),
    }
