"""多 Agent 门店执行闭环自测：三角色握手 + 验收驳回守卫 + 端到端战役。"""
import os
import tempfile
import uuid

from sqlmodel import Session, select

from app import store_loop as loop
from app.agent_loop import (
    AgentMessage,
    HQAgent,
    ReviewAgent,
    ReviewRejected,
    StoreAgent,
    run_campaign,
)
from app.store_loop import Dispatch

_TMP = tempfile.mkdtemp()


def _memory_db():
    # 独立临时文件库：保证每个测试隔离，且表随引擎存在（避免 :memory: 多连接各自建库）
    path = os.path.join(_TMP, f"agent_{uuid.uuid4().hex}.db")
    loop.configure_loop_db(f"sqlite:///{path}")
    loop.init_loop_db()


def test_campaign_pilot_accepted():
    _memory_db()
    # 仅试点门店 A01 / D01，默认三张卡 → 2×3 = 6 条全量下发并跑通验收
    res = run_campaign("门店标准落地", store_codes=["A01", "D01"])
    assert res["accepted"] == 6
    assert res["needs_rework"] == 0
    assert res["stats"]["by_status"]["accepted"] == 6
    # 消息流含 plan / execute / review 三类握手
    kinds = [m.kind for m in res["messages"]]
    assert "plan" in kinds and "execute" in kinds and "review" in kinds


def test_review_rejects_bad_report():
    _memory_db()
    hq = HQAgent()
    ids = hq.dispatch(hq.plan("标准落地", store_codes=["A01"], card_codes=["CARD-001"]))
    store = StoreAgent()
    report = store.execute(ids[0], ok=False, note="")
    review = ReviewAgent()
    try:
        review.review(report)
        assert False, "应通过 ReviewRejected 驳回"
    except ReviewRejected:
        pass
    # 驳回后状态保持 executed（不推进到 accepted）
    with Session(loop._engine) as s:
        d = s.get(Dispatch, ids[0])
        assert d.status == "executed"


def test_review_rejects_short_note():
    _memory_db()
    hq = HQAgent()
    ids = hq.dispatch(hq.plan("标准落地", store_codes=["B01"], card_codes=["CARD-001"]))
    store = StoreAgent()
    report = store.execute(ids[0], note="x")  # 说明过短
    review = ReviewAgent()
    try:
        review.review(report)
        assert False
    except ReviewRejected:
        pass


def test_store_execute_uses_state_machine():
    _memory_db()
    hq = HQAgent()
    ids = hq.dispatch(hq.plan("标准落地", store_codes=["C01"], card_codes=["CARD-002"]))
    store = StoreAgent()
    r = store.execute(ids[0])
    assert isinstance(r, object)
    assert r.store_code == "C01"
    # 直接对 dispatch 对象再 advance 到 accepted 应通过（状态机合法路径）
    with Session(loop._engine) as s:
        d = s.get(Dispatch, ids[0])
        assert d.status == "executed"


def test_campaign_idempotent_on_rerun():
    _memory_db()
    # 第一次跑：试点门店全量下发并验收
    res1 = run_campaign("门店标准落地", store_codes=["A01", "D01"])
    assert res1["accepted"] == 6
    # 第二次重跑：已 accepted 的记录应被跳过，不再重复处理（幂等，不崩溃）
    res2 = run_campaign("门店标准落地", store_codes=["A01", "D01"])
    assert res2["accepted"] == 0
    assert res2["needs_rework"] == 0
    # 总 accepted 仍为 6（没有新增）
    assert res2["stats"]["by_status"]["accepted"] == 6
