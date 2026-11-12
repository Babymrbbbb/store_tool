"""门店执行闭环（合成参考实现）—— store_tool 的扩展模块。

背景：
  内部业务系统有一套「作战卡下发 → 门店执行 → 门店验收」的门店执行闭环。
  本模块是其方法论开源复刻：用合成门店（演示品牌，A/B/C/D 四市共 12 家）
  演示同一套状态机与全量下发逻辑，**不含任何真实门店名 / 经营数据**。

状态机：dispatched → executed → accepted（每步显式校验前置态，非法转移抛错）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from sqlmodel import Field, Session, SQLModel, create_engine, select

# 合成门店分布（与 hunkon_rag 真相源一致：A 市 6 / B 市 3 / C 市 2 / D 市 1 = 12）
CITY_PLAN: dict[str, int] = {"A 市": 6, "B 市": 3, "C 市": 2, "D 市": 1}

# 三张作战卡（合成、通用，不涉及真实业务）
BATTLE_CARDS: list[tuple[str, str, str]] = [
    ("CARD-001", "陈列标准卡", "门头 / 中岛 / 冷藏柜的陈列规范"),
    ("CARD-002", "服务话术卡", "迎宾、推荐、异议处理的标准话术"),
    ("CARD-003", "订货节奏卡", "每日 20:00 前完成次日订货"),
]

# 试点门店（合成）：这两家跑通「下发 → 执行 → 验收」全闭环，其余仅下发。
PILOT_CODES: set[str] = {"A01", "D01"}

VALID_TRANSITIONS: dict[str, set[str]] = {
    "dispatched": {"executed"},
    "executed": {"accepted"},
    "accepted": set(),
}

DEFAULT_DB = "store_loop.db"
_loop_url = f"sqlite:///{DEFAULT_DB}"
_engine = create_engine(_loop_url, connect_args={"check_same_thread": False})


def configure_loop_db(url: str) -> None:
    """切换底层数据库（测试用内存库 / 临时文件，不污染业务库）。"""
    global _engine, _loop_url
    _loop_url = url
    _engine = create_engine(url, connect_args={"check_same_thread": False})


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LoopStore(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True)
    city: str
    name: str


class BattleCard(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True)
    title: str
    desc: str


class Dispatch(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    store_code: str = Field(index=True)
    card_code: str = Field(index=True)
    status: str = Field(default="dispatched")  # dispatched / executed / accepted
    dispatched_at: str = ""
    executed_at: str = ""
    accepted_at: str = ""


def init_loop_db() -> None:
    SQLModel.metadata.create_all(_engine)


def _seed_stores() -> list[LoopStore]:
    stores: list[LoopStore] = []
    for city, n in CITY_PLAN.items():
        prefix = city[0]  # A / B / C / D
        for i in range(1, n + 1):
            code = f"{prefix}{i:02d}"
            stores.append(LoopStore(code=code, city=city, name=f"{city}演示店{code}"))
    return stores


def seed_loop(full: bool = True) -> int:
    """建表 + 写入合成门店 / 作战卡 / 全量下发。返回下发记录数。

    full=True 时，试点门店（PILOT_CODES）直接置为 accepted，演示全闭环；
    其余门店仅 dispatched（对应真实系统里「全量下发 + 试点落地管控闭环」）。
    """
    init_loop_db()
    with Session(_engine) as s:
        # 幂等：先清空再重建，保证重复 seed 结果一致
        for row in s.exec(select(Dispatch)).all():
            s.delete(row)
        for row in s.exec(select(LoopStore)).all():
            s.delete(row)
        for row in s.exec(select(BattleCard)).all():
            s.delete(row)
        s.commit()

        stores = _seed_stores()
        s.add_all(stores)
        cards = [BattleCard(code=c, title=t, desc=d) for c, t, d in BATTLE_CARDS]
        s.add_all(cards)
        s.commit()

        n = 0
        for st in stores:
            for c in cards:
                disp = Dispatch(
                    store_code=st.code,
                    card_code=c.code,
                    status="dispatched",
                    dispatched_at=now_iso(),
                )
                if full and st.code in PILOT_CODES:
                    # 试点门店直接跑通 执行 + 验收（合成演示全闭环）
                    disp.status = "accepted"
                    disp.executed_at = now_iso()
                    disp.accepted_at = now_iso()
                s.add(disp)
                n += 1
        s.commit()
        return n


def advance(dispatch_id: int, target: str) -> Dispatch:
    """按状态机显式推进；非法转移或不存在的 dispatch 抛 ValueError。"""
    if target not in ("executed", "accepted"):
        raise ValueError(f"非法目标态: {target}")
    with Session(_engine) as s:
        d = s.get(Dispatch, dispatch_id)
        if not d:
            raise ValueError(f"下发记录 {dispatch_id} 不存在")
        allowed = VALID_TRANSITIONS.get(d.status, set())
        if target not in allowed:
            raise ValueError(
                f"{d.status} → {target} 非法（仅允许 {sorted(allowed)}）"
            )
        if target == "executed":
            d.status, d.executed_at = "executed", now_iso()
        elif target == "accepted":
            d.status, d.accepted_at = "accepted", now_iso()
        s.add(d)
        s.commit()
        s.refresh(d)
        return d


def stats() -> dict:
    """汇总：门店数 / 卡数 / 下发数 / 各状态计数。"""
    with Session(_engine) as s:
        rows = s.exec(select(Dispatch)).all()
        by_status = {"dispatched": 0, "executed": 0, "accepted": 0}
        for r in rows:
            by_status[r.status] = by_status.get(r.status, 0) + 1
        return {
            "stores": len({r.store_code for r in rows}),
            "cards": len({r.card_code for r in rows}),
            "dispatches": len(rows),
            "by_status": by_status,
        }
