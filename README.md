# 天鹅公主 · 门店管理 API（store_tool）

一个用于 **AI 应用架构师 / 后端工程师** 求职练手的 FastAPI 后端项目。以中高端烘焙品牌「天鹅公主 SWAN NOBLE」的门店管理为业务背景，覆盖从工程结构到容器化部署的完整后端能力，可直接作为简历中的「可测试、可交付的后端服务」作品。

## 技术栈

- **Web 框架**：FastAPI
- **ORM / 模型**：SQLModel（SQLAlchemy + Pydantic v2 合体）
- **数据库**：SQLite（文件型，零运维）
- **Schema 迁移**：Alembic（版本化建表，可回滚）
- **配置管理**：pydantic-settings（环境变量覆盖，不硬编码）
- **测试**：pytest + FastAPI TestClient
- **鉴权**：API Key（全局依赖注入，统一错误信封）
- **部署**：Docker / Docker Compose

## 功能特性

- 多文件工程结构：路由层 / 模型层 / 数据访问层 / 配置层分离
- 门店（Store）与库存（Stock）的完整 **CRUD** + 列表**分页**
- **统一错误返回**：所有异常收敛为 `{"error": {"code", "message"}}` 信封
- **依赖注入**提供数据库会话与接口鉴权
- **pytest 单测**覆盖核心接口与边界（9 用例）
- **Alembic 迁移**管理 schema 演进（非 `create_all` 兜底）
- **API Key 全局鉴权**
- **Docker 化**：一键构建部署

## 项目结构

```
store_tool/
├── app/
│   ├── __init__.py
│   ├── main.py          # 路由层 + 全局依赖（鉴权 / 统一错误）
│   ├── models.py        # 模型层（表定义 + 入参/出参模型）
│   ├── database.py      # 数据访问层（引擎 / 会话 / 依赖注入）
│   └── config.py        # 配置层（数据库文件 / 密钥）
├── migrations/          # Alembic 迁移脚本
├── seed.py              # 灌入示例门店数据（幂等）
├── test_main.py         # pytest 单测
├── requirements.txt     # 运行时依赖
├── requirements-dev.txt # 开发/测试依赖
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── .gitignore
```

## 快速开始（本地）

```bash
# 1. 建虚拟环境并装依赖（Python 3.13）
python -m venv venv
venv/Scripts/python -m pip install -r requirements.txt
venv/Scripts/python -m pip install -r requirements-dev.txt

# 2. 建表（Alembic 迁移）
venv/Scripts/python -m alembic upgrade head

# 3. 灌示例数据（可选，幂等）
venv/Scripts/python seed.py

# 4. 跑起来
venv/Scripts/python -m uvicorn app.main:app --reload
# 打开 http://127.0.0.1:8000/docs 看交互式文档
```

## 测试

```bash
venv/Scripts/python -m pytest test_main.py -v
```

## 接口鉴权

所有接口需在请求头携带 API Key（默认 `dev-secret-key`，生产用环境变量 `STORE_API_KEY` 覆盖）：

```bash
curl -H "X-API-Key: dev-secret-key" http://127.0.0.1:8000/stores
```

未带或错 Key 一律返回 `401`，并走统一错误信封。

## 主要接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/stores` | 门店列表（支持 `city`/`min_orders` 过滤、`limit`/`offset` 分页） |
| GET | `/stores/{id}` | 按 id 查门店 |
| POST | `/stores` | 新建门店（201） |
| PUT | `/stores/{id}` | 部分更新门店 |
| DELETE | `/stores/{id}` | 删除门店 |
| GET | `/stats/by-city` | 按城市聚合门店数与总销量 |
| POST | `/stock` | 新建库存 |
| PUT | `/stock/{id}` | 更新库存 |
| DELETE | `/stock/{id}` | 删除库存 |
| POST | `/stock/query` | 批量按 `store_id`+`sku` 查库存 |

## Docker 部署

```bash
docker compose up --build
# 调用：curl -H "X-API-Key: dev-secret-key" http://localhost:8000/stores
```

容器启动顺序：Alembic 迁移建表 → 灌示例数据 → 起 uvicorn。

## 学习收获（简历可写点）

- 理解**依赖注入**在数据库连接与鉴权中的统一应用（路由不直接碰连接、鉴权先于业务）
- 掌握 **SQLModel 入参/出参模型分离**（避免表模型当请求体导致必填失效）
- 实践 **Alembic 版本化迁移**作为 schema 唯一真相源
- 具备 **pytest 可测试后端** 与 **Docker 可交付** 的完整最小形态

> 本项目为练手/求职作品，默认密钥仅用于本地演示，生产请替换为强密钥并通过环境变量注入。
