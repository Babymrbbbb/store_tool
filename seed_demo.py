# seed_demo.py
# 用途：为公网演示实例灌入【纯虚构数据】。
#
# ⚠️ 安全设计（最重要的一条）：本脚本写入独立的 demo.db，
#    与真实 stores.db 物理隔离。即使公网实例被攻入，攻击者只能看到脱敏假数据，
#    拿不到任何真实经营信息。
#
# 运行：python seed_demo.py   （必须在 store_tool 目录下，确保能 import app）
#
# 部署公网时配套：
#   1) 设环境变量 STORE_STORE_DB_FILE=demo.db  ← 让服务读演示库，而不是真实库
#   2) 设环境变量 STORE_API_KEY=<一段强随机串>  ← 固定密钥，避免重启后随机值变化
# 详见《阶段B_安全部署检查清单.md》

import os
from sqlmodel import Session, select, create_engine, SQLModel
from app.models import Store, Stock

# ★ 关键：单独一个演示库，绝不碰 stores.db
DEMO_DB = "demo.db"
engine = create_engine(
    f"sqlite:///{DEMO_DB}",
    echo=False,
    connect_args={"check_same_thread": False},
)

# 纯虚构数据：门店名/城市均为"示例"，与任何真实企业经营数据无关。
# 数字也是示意值，不代表任何真实销量。
demo_stores = [
    Store(name="演示店-朝阳", city="示例市A", daily_orders=128),
    Store(name="演示店-天河", city="示例市B", daily_orders=210),
    Store(name="演示店-西湖", city="示例市C", daily_orders=176),
    Store(name="演示店-滨海", city="示例市A", daily_orders=92),
    Store(name="演示店-高新", city="示例市B", daily_orders=143),
]

demo_stock = [
    Stock(store_id=1, sku="演示-SKU-001", qty=50),
    Stock(store_id=2, sku="演示-SKU-002", qty=30),
    Stock(store_id=3, sku="演示-SKU-003", qty=18),
]

SQLModel.metadata.create_all(engine)
with Session(engine) as s:
    if not s.exec(select(Store)).first():
        s.add_all(demo_stores)
        s.add_all(demo_stock)
        s.commit()
        print(f"已向 {DEMO_DB} 灌入 {len(demo_stores)} 家【假】演示门店 + {len(demo_stock)} 条演示库存")
    else:
        print(f"{DEMO_DB} 已有数据，跳过（如需重置请先删除 {DEMO_DB}）")

print("下一步：部署时设 STORE_STORE_DB_FILE=demo.db 且 STORE_API_KEY=强随机串")
