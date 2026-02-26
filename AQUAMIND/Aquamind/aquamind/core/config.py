"""
Aquamind 配置管理

使用 pydantic-settings 进行类型安全的配置管理。
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORT_DIR = PROJECT_ROOT / "reports"
LOG_DIR = PROJECT_ROOT / "logs"


class LLMSettings(BaseSettings):
    """LLM 配置"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # API 配置
    api_base: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="API_BASE"
    )
    api_key: Optional[str] = Field(default=None, alias="API_KEY")
    model_name: str = Field(default="qwen-plus", alias="MODEL_NAME")
    
    # 模型参数
    temperature: float = Field(default=0.7, alias="MODEL_TEMPERATURE")
    max_tokens: int = Field(default=8192, alias="MODEL_MAX_TOKENS")
    top_p: float = Field(default=0.9, alias="MODEL_TOP_P")
    
    # 请求配置
    request_timeout: int = Field(default=60, alias="LLM_REQUEST_TIMEOUT")
    max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    retry_delay: float = Field(default=1.0, alias="LLM_RETRY_DELAY")
    
    def validate_api_key(self) -> bool:
        """验证 API 密钥是否已配置"""
        if not self.api_key:
            raise ValueError("未配置 API_KEY，请检查 .env 文件")
        return True


class SystemSettings(BaseSettings):
    """系统配置"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # 系统信息
    system_name: str = "Aquamind Systems"
    version: str = "2.0.0"
    
    # 运行模式
    debug_mode: bool = Field(default=False, alias="DEBUG_MODE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # 缓存配置
    enable_cache: bool = Field(default=True, alias="ENABLE_CACHE")
    cache_ttl: int = Field(default=300, alias="CACHE_TTL")


class AgentSettings(BaseSettings):
    """智能体配置"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # 毒性阈值
    toxicity_low_threshold: float = Field(
        default=1.5, alias="TOXICITY_LOW_THRESHOLD"
    )
    toxicity_high_threshold: float = Field(
        default=3.0, alias="TOXICITY_HIGH_THRESHOLD"
    )
    
    # 转盘控制
    turntable_min_frequency: float = 5.0
    turntable_max_frequency: float = 50.0
    turntable_reactors_count: int = 3
    
    # MBR 控制
    mbr_tmp_normal: float = 20.0
    mbr_tmp_warning: float = 30.0
    mbr_min_flux: float = 15.0
    mbr_max_flux: float = 20.0
    
    # 再生控制
    carbon_efficiency_threshold: float = Field(
        default=70.0, alias="CARBON_EFFICIENCY_THRESHOLD"
    )
    regeneration_temp: float = 800.0
    regeneration_feed_rate: float = 30.0
    
    # 诊断评分
    health_score_excellent: float = 90.0
    health_score_good: float = 75.0
    health_score_warning: float = 60.0
    
    def get_toxicity_level(self, toxicity: float) -> str:
        """根据毒性值获取等级"""
        if toxicity < self.toxicity_low_threshold:
            return "低"
        elif toxicity < self.toxicity_high_threshold:
            return "中"
        else:
            return "高"


class PLCSettings(BaseSettings):
    """PLC 配置"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    enabled: bool = Field(default=False, alias="PLC_ENABLED")
    host: Optional[str] = Field(default=None, alias="PLC_HOST")
    port: int = Field(default=502, alias="PLC_PORT")
    timeout: float = Field(default=5.0, alias="PLC_TIMEOUT")
    
    # 变量前缀
    turntable_var_prefix: str = "MB01.TT"
    mbr_var_prefix: str = "MB02.MBR"
    regeneration_var_prefix: str = "MB03.RG"


class Settings:
    """统一配置入口"""
    
    def __init__(self):
        self.llm = LLMSettings()
        self.system = SystemSettings()
        self.agent = AgentSettings()
        self.plc = PLCSettings()
        
        # 确保目录存在
        for directory in [DATA_DIR, REPORT_DIR, LOG_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def validate(self) -> bool:
        """验证所有配置"""
        try:
            self.llm.validate_api_key()
            print(f"[Config] {self.system.system_name} v{self.system.version} 配置验证成功")
            return True
        except ValueError as e:
            print(f"[Config] 配置验证失败: {e}")
            return False


# 全局配置实例
settings = Settings()


if __name__ == "__main__":
    print("=" * 60)
    print("Aquamind 配置测试")
    print("=" * 60)
    
    print(f"\n[LLM 配置]")
    print(f"  API Base: {settings.llm.api_base}")
    print(f"  Model: {settings.llm.model_name}")
    print(f"  Temperature: {settings.llm.temperature}")
    
    print(f"\n[系统配置]")
    print(f"  名称: {settings.system.system_name}")
    print(f"  版本: {settings.system.version}")
    print(f"  调试模式: {settings.system.debug_mode}")
    
    print(f"\n[智能体配置]")
    print(f"  毒性低阈值: {settings.agent.toxicity_low_threshold}")
    print(f"  毒性高阈值: {settings.agent.toxicity_high_threshold}")
