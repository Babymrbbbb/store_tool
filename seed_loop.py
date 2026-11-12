#!/usr/bin/env python3
"""一键建库并写入合成门店执行闭环数据（演示用，不含任何真实数据）。

用法：python seed_loop.py
写入 app/store_loop.DEFAULT_DB（默认 store_loop.db），并打印汇总。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.store_loop import seed_loop, stats  # noqa: E402


def main() -> None:
    n = seed_loop()
    print(f"已写入 {n} 条下发记录（12 家门店 × 3 张作战卡）")
    print("汇总：", stats())


if __name__ == "__main__":
    main()
