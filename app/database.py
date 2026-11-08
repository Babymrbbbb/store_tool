# app/database.py
# 数据访问层：只负责"怎么连数据库、怎么开/关会话"，不写路由、不定义表。
from sqlmodel import create_engine, Session, SQLModel
from app import models  # 关键：导入 models 模块 ⇒ 执行后 Store/Stock 表注册进 SQLModel.metadata
from app.config import settings

# SQLite 是"文件型数据库"——不用装服务器，数据就存在配置指定的文件里
# 文件名来自配置（可被环境变量 STORE_STORE_DB_FILE 覆盖），不再硬编码
sqlite_file = settings.store_db_file
engine = create_engine(
    f"sqlite:///{sqlite_file}",
    echo=False,                           # True 会在终端打印每条 SQL，调试时打开看
    connect_args={"check_same_thread": False},  # SQLite 默认只允许创建它的线程访问；uvicorn 多线程，必须放开这限制
)

def init_db():
    # 建表：读 SQLModel.metadata 里注册的所有表（Store、Stock），库里没有就建
    SQLModel.metadata.create_all(engine)

def get_session():
    # ★ 依赖注入点：用 with 开一个会话，yield 交给路由用，请求结束自动关（连接回收）
    with Session(engine) as session:
        yield session
