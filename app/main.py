# app/main.py
# 路由层：只负责"接到什么请求、返回什么"，不直接碰数据库连接字符串。
# 要查库？只认注入进来的 session 参数。
from fastapi import FastAPI, Depends, HTTPException, status, Request, Header
from fastapi.responses import JSONResponse, HTMLResponse
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

# 鉴权以"路由级"方式挂到业务路由上（不放应用级全局依赖），
# 这样 /health 等公开路由可以天然不带鉴权。
AUTH = [Depends(get_api_key)]

app = FastAPI(
    title="门店销量示例服务 V2",
    version="0.2.0",
    lifespan=lifespan,
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

# ---- 落地页（公开，纯元数据 + 安全说明，不暴露任何业务/真实数据）----
# 用普通字符串（非 f-string）写，避免 CSS 里的 {} 被当成格式化占位符；
# 仅 {VERSION} 一处用 .replace 注入，防止与 CSS 大括号冲突。
LANDING_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>门店销量示例服务（演示）</title>
<style>
  :root { --gold:#d4af37; --gold-soft:#c9a24b; --bg:#0b0b0d; --panel:#16161a; --line:#2a2a30; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:#e8e8ea; font-family:-apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,Roboto,sans-serif; line-height:1.6; }
  .wrap { max-width:760px; margin:0 auto; padding:48px 24px 64px; }
  .brand { display:flex; align-items:center; gap:14px; margin-bottom:8px; }
  .logo { width:40px; height:40px; border-radius:50%; background:linear-gradient(135deg,var(--gold),#8a6d1f); display:flex; align-items:center; justify-content:center; color:#0b0b0d; font-weight:700; }
  h1 { font-size:24px; margin:0; color:var(--gold); letter-spacing:1px; }
  .sub { color:#9a9aa2; font-size:13px; letter-spacing:2px; margin:4px 0 28px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:24px; margin-bottom:20px; }
  h2 { font-size:15px; color:var(--gold-soft); margin:0 0 12px; letter-spacing:1px; }
  p { margin:0 0 12px; font-size:14px; color:#cfcfd6; }
  .ep { display:flex; align-items:center; gap:12px; padding:10px 0; border-bottom:1px solid var(--line); }
  .ep:last-child { border-bottom:none; }
  code { background:#0e0e12; color:var(--gold); padding:2px 8px; border-radius:6px; font-size:13px; }
  .badge { font-size:11px; padding:2px 10px; border-radius:999px; border:1px solid; white-space:nowrap; }
  .badge.pub { color:#5fd08a; border-color:#2f6b48; }
  .badge.auth { color:#e0a94b; border-color:#6b552f; }
  .warn { background:rgba(212,175,55,0.08); border:1px solid #6b552f; border-radius:12px; padding:16px 20px; color:#e0c98a; font-size:13px; }
  .warn b { color:var(--gold); }
  .foot { color:#6a6a72; font-size:12px; margin-top:28px; text-align:center; }
  a { color:var(--gold); text-decoration:none; }
  a:hover { text-decoration:underline; }
</style>
</head>
<body>
  <div class="wrap">
    <div class="brand">
      <div class="logo">Demo</div>
      <div><h1>门店销量示例服务</h1></div>
    </div>
    <div class="sub">SYNTHETIC DEMO · STORE DEMO API · v{VERSION}</div>

    <div class="card">
      <h2>这是什么</h2>
      <p>一个用于演示的门店销量 / 库存查询 API 服务，是「AI 应用落地」学习项目（FastAPI + SQLite + 鉴权 + 单测）的阶段性产出。</p>
      <p>它对外展示的是工程能力：统一错误信封、路由级鉴权、配置分离、自动化测试与可公网部署，而不是任何真实业务数据。</p>
    </div>

    <div class="card">
      <h2>接口一览</h2>
      <div class="ep"><code>/health</code><span class="badge pub">公开</span><span>健康检查，返回服务状态</span></div>
      <div class="ep"><code>/stores</code><span class="badge auth">需密钥</span><span>门店销量列表（演示数据）</span></div>
      <div class="ep"><code>/stats/by-city</code><span class="badge auth">需密钥</span><span>按城市聚合销量（演示数据）</span></div>
      <div class="ep"><code>/docs</code><span class="badge pub">公开</span><span><a href="/docs">Swagger 交互文档</a></span></div>
    </div>

    <div class="warn">
      <b>安全说明：</b>本实例为公开演示环境，仅连接独立的「演示数据库」，内含 5 家纯虚构门店；<b>不包含任何真实经营数据</b>。业务接口均须携带 API Key（请求头 X-API-Key），缺失即返回 401。
    </div>

    <div class="foot">演示实例 · 仅含虚构数据 · 部署于公开隧道（URL 可能随重启变化）</div>
  </div>
</body>
</html>
'''

# ---- 健康检查（公网验收项）：免密钥、直接 200、无重定向 ----
# 故意不放 AUTH 依赖，也不走 mount 子应用（本版本 Starlette 的 mount
# 默认会把 /health 307 跳到 /health/，裸 curl / 探针拿不到 200）。
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "swan-store-tool", "version": "0.2.0"}

@app.get("/")
def root():
    # 根路径返回示例主题落地页（公开、纯元数据 + 安全说明，不含任何业务/真实数据）。
    return HTMLResponse(content=LANDING_HTML.replace("{VERSION}", "0.2.0"))

@app.get("/stores", dependencies=AUTH)
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

@app.get("/stores/{store_id}", response_model=Store, dependencies=AUTH)
def get_store(store_id: int, session: Session = Depends(get_session)):
    # session.get(表, 主键) 按 id 直接取一行
    store = session.get(Store, store_id)
    if not store:
        # 查不到 ⇒ 抛 404，FastAPI 自动转成 HTTP 404 响应
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"门店 {store_id} 不存在")
    return store

@app.post("/stores", response_model=Store, status_code=status.HTTP_201_CREATED, dependencies=AUTH)
def create_store(item: StoreCreate, session: Session = Depends(get_session)):
    # 入参 StoreCreate（非表模型，字段真必填）；转成表模型再写库
    db_item = Store(name=item.name, city=item.city, daily_orders=item.daily_orders)
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item

@app.put("/stores/{store_id}", response_model=Store, dependencies=AUTH)
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

@app.delete("/stores/{store_id}", dependencies=AUTH)
def delete_store(store_id: int, session: Session = Depends(get_session)):
    store = session.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"门店 {store_id} 不存在")
    session.delete(store)
    session.commit()
    return {"ok": True, "deleted": store_id}

@app.post("/stock", response_model=Stock, dependencies=AUTH)
def add_stock(item: StockCreate, session: Session = Depends(get_session)):
    # 入参 item 是 StockCreate（非表模型，sku 真必填）；转成表模型再写库
    db_item = Stock(store_id=item.store_id, sku=item.sku, qty=item.qty)
    session.add(db_item)    # 放进会话（还没写库）
    session.commit()        # 真正写库
    session.refresh(db_item)  # 写完后从库里拿回自动生成的 id
    return db_item

@app.get("/stats/by-city", dependencies=AUTH)
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

@app.post("/stock/query", dependencies=AUTH)
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

@app.put("/stock/{stock_id}", response_model=Stock, dependencies=AUTH)
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

@app.delete("/stock/{stock_id}", dependencies=AUTH)
def delete_stock(stock_id: int, session: Session = Depends(get_session)):
    stock = session.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"库存 {stock_id} 不存在")
    session.delete(stock)
    session.commit()
    return {"ok": True, "deleted": stock_id}
