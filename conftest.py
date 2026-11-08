# conftest.py — pytest 启动时最先加载，用于在"隔离的测试库"上跑用例。
# 解决的问题：
#   1) 原测试套件没有自己建表，依赖 stores.db 里已有表（来自 seed.py 的历史运行），
#      换台机器 / 全新 clone 直接 pytest 会报 "no such table"。
#   2) 原测试会直接读写真实的 stores.db（开发库），不安全也不干净。
# 这里把测试库重定向到 test.db（已被 .gitignore 的 *.db 忽略），并在会话开始时建表。
import os

# 必须在导入 app 之前设置，config.py 在 import 时就读环境变量构造 Settings 单例。
# 用 setdefault：若你在命令行显式传了 STORE_STORE_DB_FILE / STORE_API_KEY，则以你的为准。
os.environ.setdefault("STORE_STORE_DB_FILE", "test.db")
os.environ.setdefault("STORE_API_KEY", "test-key")

import pytest
from app.database import init_db


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db():
    # 会话级、自动生效：建表一次，供全部用例使用。
    init_db()
    yield
