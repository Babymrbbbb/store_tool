# app/config.py
# 配置层：把所有"会变的环境相关值"（库文件名、密钥、环境名）集中这里。
# 用 pydantic-settings：默认值写在代码，运行时可用环境变量覆盖，不硬编码在业务里。
import secrets

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _random_key() -> str:
    """进程级临时强密钥：不把可预测的弱字面量写进代码。

    未配置 STORE_API_KEY 时每次启动生成随机值；生产/稳定演示必须显式设环境变量。
    """
    return secrets.token_urlsafe(32)


class Settings(BaseSettings):
    # 数据库文件名；可用环境变量 STORE_STORE_DB_FILE 覆盖（env_prefix=STORE_）
    store_db_file: str = "stores.db"

    # 接口密钥：默认随机强密钥，用环境变量 STORE_API_KEY 覆盖，别把真密钥写进代码
    api_key: str = Field(default_factory=_random_key)

    # 后续要加的都放这：密钥、运行环境、第三方 token……

    model_config = SettingsConfigDict(
        env_file=".env",      # 可选：从项目根目录 .env 读（不进 git）
        env_prefix="STORE_",  # 环境变量前缀，避免和其它项目冲突
    )


settings = Settings()  # 全局单例，业务代码 from app.config import settings 取用
