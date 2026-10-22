# test_main.py — Day03/Day04 单测：用 TestClient 固化接口行为
# 运行：pytest test_main.py -v
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)
client.headers["X-API-Key"] = settings.api_key  # 全局带鉴权头，避免每个用例重复加

# ---------- Day03：基础 + 统一错误信封 ----------
def test_list_stores_returns_200_and_list():
    r = client.get("/stores")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_get_store_404_uses_uniform_envelope():
    r = client.get("/stores/999")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == 404

def test_validation_error_uses_uniform_envelope():
    # POST /stock 缺必填字段 sku ⇒ 422，且是统一信封
    r = client.post("/stock", json={"store_id": 1})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == 422

# ---------- Day04：分页 ----------
def test_pagination_limit():
    r = client.get("/stores", params={"limit": 1, "offset": 0})
    assert r.status_code == 200
    assert len(r.json()) <= 1

# ---------- Day04：Store CRUD（自清理，不污染库） ----------
def test_create_store_returns_201_and_id():
    r = client.post("/stores", json={"name": "测试店A", "city": "测试城", "daily_orders": 5})
    assert r.status_code == 201
    body = r.json()
    assert body["id"] is not None
    client.delete(f"/stores/{body['id']}")  # 清理

def test_update_store_changes_only_given_field():
    c = client.post("/stores", json={"name": "测试店B", "city": "测试城", "daily_orders": 5}).json()
    r = client.put(f"/stores/{c['id']}", json={"daily_orders": 999})
    assert r.status_code == 200
    assert r.json()["daily_orders"] == 999
    client.delete(f"/stores/{c['id']}")  # 清理

def test_delete_store_then_404():
    c = client.post("/stores", json={"name": "测试店C", "city": "测试城", "daily_orders": 5}).json()
    d = client.delete(f"/stores/{c['id']}")
    assert d.status_code == 200
    assert d.json()["ok"] is True
    g = client.get(f"/stores/{c['id']}")
    assert g.status_code == 404

# ---------- Day07：鉴权 ----------
def test_missing_api_key_returns_401():
    anon = TestClient(app)  # 不带 key 的匿名客户端
    r = anon.get("/stores")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == 401

def test_wrong_api_key_returns_401():
    r = client.get("/stores", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == 401
