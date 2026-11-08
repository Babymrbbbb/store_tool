# app/config.py
# 配置层：把所有"会变的环境相关值"（库文件名、密钥、环境名）集中这里。
# 用 pydantic-settings：默认值写在代码，运行时可用环境变量覆盖，不硬编码在业务里。
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 数据库文件名；可用环境变量 STORE_STORE_DB_FILE 覆盖（env_prefix=STORE_）
    store_db_file: str = "stores.db"

    # 接口密钥；生产用环境变量 STORE_API_KEY 覆盖，别把真密钥写进代码
    api_key: str = "dev-secret-key"

    # 后续要加的都放这：密钥、运行环境、第三方 token……

    model_config = SettingsConfigDict(
        env_file=".env",      # 可选：从项目根目录 .env 读（不进 git）
        env_prefix="STORE_",  # 环境变量前缀，避免和其它项目冲突
    )


settings = Settings()  # 全局单例，业务代码 from app.config import settings 取用
