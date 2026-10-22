# app/main.py
# 路由层：只负责"接到什么请求、返回什么"，不直接碰数据库连接字符串。
# 要查库？只认注入进来的 session 参数。
from fastapi import FastAPI, Depends, HTTPException, status, Request, Header
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlmodel import Session, select
from sqlalchemy import func
from contextlib import asynccontextmanager
from app.database import init_db, get_session
from app.config import settings
from app.models import (Store, Stock, StockCreate, StockUpdate,
                         StoreCreate, StoreUpdate, StockQueryItem)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动：建表（替代已弃用的 @app.on_event("startup")）
    init_db()
    yield
    # 应用关闭：此处可释放资源（当前无需）

# ---- 鉴权依赖：每个请求必须带正确的 X-API-Key，否则 401 ----
async def get_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或缺失 API Key",
        )
    return x_api_key

app = FastAPI(
    title="天鹅公主·门店销量小工具 V2",
    version="0.2.0",
    lifespan=lifespan,
    # 全局依赖：所有接口都要先过 get_api_key（鉴权），不用每个路由单独写
    dependencies=[Depends(get_api_key)],
)

# ---- 统一错误返回：所有异常都收敛成 {"error": {"code", "message"}} 信封 ----
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": 422, "message": "请求参数校验失败",
                           "details": exc.errors()}},
    )

@app.get("/stores")
def list_stores(city: str | None = None, min_orders: int = 0,
                limit: int = 10, offset: int = 0,
                session: Session = Depends(get_session)):
    # ① 拼查询：select(Store) 是"从 Store 表选"
    statement = select(Store)
    # ② 有 city 就加过滤条件（可选参数）
    if city:
        statement = statement.where(Store.city == city)
    # ③ 销量门槛过滤
    statement = statement.where(Store.daily_orders >= min_orders)
    # ④ 按销量降序排
    statement = statement.order_by(Store.daily_orders.desc())
    # ④b 分页：limit=取几条，offset=跳过几条（前端"第几页"换算成 offset）
    statement = statement.limit(limit).offset(offset)
    # ⑤ session.exec(...) 执行；.all() 拿全部结果
    return session.exec(statement).all()

@app.get("/stores/{store_id}", response_model=Store)
def get_store(store_id: int, session: Session = Depends(get_session)):
    # session.get(表, 主键) 按 id 直接取一行
    store = session.get(Store, store_id)
    if not store:
        # 查不到 ⇒ 抛 404，FastAPI 自动转成 HTTP 404 响应
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"门店 {store_id} 不存在")
    return store

@app.post("/stores", response_model=Store, status_code=status.HTTP_201_CREATED)
def create_store(item: StoreCreate, session: Session = Depends(get_session)):
    # 入参 StoreCreate（非表模型，字段真必填）；转成表模型再写库
    db_item = Store(name=item.name, city=item.city, daily_orders=item.daily_orders)
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item

@app.put("/stores/{store_id}", response_model=Store)
def update_store(store_id: int, item: StoreUpdate, session: Session = Depends(get_session)):
    store = session.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"门店 {store_id} 不存在")
    # 只更新客户端真正传了的字段（exclude_unset=True 排除"没传"的字段）
    data = item.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(store, key, value)
    session.add(store)
    session.commit()
    session.refresh(store)
    return store

@app.delete("/stores/{store_id}")
def delete_store(store_id: int, session: Session = Depends(get_session)):
    store = session.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"门店 {store_id} 不存在")
    session.delete(store)
    session.commit()
    return {"ok": True, "deleted": store_id}

@app.post("/stock", response_model=Stock)
def add_stock(item: StockCreate, session: Session = Depends(get_session)):
    # 入参 item 是 StockCreate（非表模型，sku 真必填）；转成表模型再写库
    db_item = Stock(store_id=item.store_id, sku=item.sku, qty=item.qty)
    session.add(db_item)    # 放进会话（还没写库）
    session.commit()        # 真正写库
    session.refresh(db_item)  # 写完后从库里拿回自动生成的 id
    return db_item

@app.get("/stats/by-city")
def stats_by_city(session: Session = Depends(get_session)):
    # 一次查询：每座城市，门店数 + 总销量
    statement = select(
        Store.city,
        func.count(Store.id).label("stores"),
        func.sum(Store.daily_orders).label("total_orders"),
    ).group_by(Store.city)
    rows = session.exec(statement).all()
    # rows 每行是带列名的元组，用 .city / .stores / .total_orders 取
    return [{"city": r.city, "stores": r.stores, "total_orders": r.total_orders}
            for r in rows]

@app.post("/stock/query")
def query_stock(items: list[StockQueryItem],
                session: Session = Depends(get_session)):
    result = []
    for it in items:
        # 按 store_id + sku 去 Stock 表查一条
        row = session.exec(
            select(Stock).where(
                Stock.store_id == it.store_id,
                Stock.sku == it.sku,
            )
        ).first()
        result.append({
            "store_id": it.store_id,
            "sku": it.sku,
            "qty": row.qty if row else 0,  # 查不到默认 0
        })
    return result

@app.put("/stock/{stock_id}", response_model=Stock)
def update_stock(stock_id: int, item: StockUpdate, session: Session = Depends(get_session)):
    stock = session.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"库存 {stock_id} 不存在")
    data = item.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(stock, key, value)
    session.add(stock)
    session.commit()
    session.refresh(stock)
    return stock

@app.delete("/stock/{stock_id}")
def delete_stock(stock_id: int, session: Session = Depends(get_session)):
    stock = session.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"库存 {stock_id} 不存在")
    session.delete(stock)
    session.commit()
    return {"ok": True, "deleted": stock_id}
