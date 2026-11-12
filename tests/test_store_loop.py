"""门店执行闭环（合成）测试：全量下发计数 / 状态机合法推进 / 非法跳过拦截。

背景：
  store_tool 的扩展模块 app/store_loop.py 复刻内部「作战卡下发 → 执行 → 验收」
  闭环，用合成门店（演示品牌 12 家）演示，不含真实数据。
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from sqlmodel import Session, select

from app import store_loop as L  # noqa: E402


@pytest.fixture(autouse=True)
def _tmp_db():
    tmp = tempfile.mkdtemp()
    L.configure_loop_db(f"sqlite:///{tmp}/loop.db")
    yield
    L.configure_loop_db(f"sqlite:///{L.DEFAULT_DB}")


def _first_dispatched_id():
    with Session(L._engine) as s:
        d = s.exec(select(L.Dispatch).where(L.Dispatch.status == "dispatched")).first()
        return d.id


def test_seed_counts():
    n = L.seed_loop()
    assert n == 36  # 12 家 × 3 张卡
    st = L.stats()
    assert st["stores"] == 12
    assert st["cards"] == 3
    assert st["dispatches"] == 36
    assert st["by_status"]["accepted"] == 6  # 2 家试点 × 3 卡 = 全闭环
    assert st["by_status"]["dispatched"] == 30


def test_advance_valid_chain():
    L.seed_loop()
    did = _first_dispatched_id()
    d1 = L.advance(did, "executed")
    assert d1.status == "executed"
    d2 = L.advance(did, "accepted")
    assert d2.status == "accepted"


def test_advance_invalid_skip_blocked():
    L.seed_loop()
    did = _first_dispatched_id()
    with pytest.raises(ValueError):
        L.advance(did, "accepted")  # 不能从 dispatched 直接跳到 accepted


def test_unknown_dispatch_raises():
    L.seed_loop()
    with pytest.raises(ValueError):
        L.advance(999999, "executed")
