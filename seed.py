# seed.py
# 用途：一次性往 stores.db 灌入示例门店，方便你本地验证接口。
# 运行：python seed.py  （必须在 store_tool 目录下，确保能 import app）
from sqlmodel import Session, select
from app.database import engine, init_db
from app.models import Store

init_db()  # 先确保表存在

sample = [
    Store(name="北京西单店", city="北京", daily_orders=128),
    Store(name="上海徐家汇店", city="上海", daily_orders=210),
    Store(name="广州天河店", city="广州", daily_orders=176),
    # TODO: 补齐到 43 家（先 3 家跑通流程）
]

with Session(engine) as s:
    existing = s.exec(select(Store)).first()  # 查是否已有数据
    if not existing:
        s.add_all(sample)
        s.commit()
        print(f"已灌入 {len(sample)} 家门店")
    else:
        print("已有数据，跳过")
