# app/models.py
# 模型层：只定义"数据表长什么样"，不碰数据库连接、不写路由。
# SQLModel 同时是"表定义"和"Pydantic 模型"——Day01 学的 Field 校验直接复用。
from sqlmodel import SQLModel, Field


class Store(SQLModel, table=True):
    # table=True  ⇒ 这是数据库表（不是普通 Pydantic 模型）
    id: int | None = Field(default=None, primary_key=True)  # 主键，数据库自动生成
    name: str = Field(index=True)        # index=True ⇒ 按店名查更快
    city: str = Field(index=True)        # index=True ⇒ 按城市过滤更快
    daily_orders: int = Field(default=0, ge=0)  # 默认值0；ge=0 ⇒ 校验"销量不能为负"


# 创建门店入参（非表模型，字段真必填）
class StoreCreate(SQLModel):
    name: str
    city: str
    daily_orders: int = 0

# 更新门店入参（全可选：只传要改的字段）
class StoreUpdate(SQLModel):
    name: str | None = None
    city: str | None = None
    daily_orders: int | None = None


class Stock(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    store_id: int = Field(foreign_key="store.id", index=True)  # 外键 ⇒ 这库存属于哪家店
    sku: str
    qty: int = Field(default=0)


# 创建库存的"入参"模型（无 table=True ⇒ Pydantic 真校验：sku 必填）
# 为什么单独建：表模型 Stock 因 table=True 会把字段当可空，不能直接当请求体，否则缺字段不报 422
class StockCreate(SQLModel):
    store_id: int
    sku: str
    qty: int = 0

# 更新库存入参（全可选）
class StockUpdate(SQLModel):
    sku: str | None = None
    qty: int | None = None


# 不是数据库表，只是"批量查询"的请求体结构（无 table=True）
class StockQueryItem(SQLModel):
    store_id: int
    sku: str
