"""
Aquamind 系统配置文件
统一管理所有配置参数
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "Data"
REPORT_DIR = PROJECT_ROOT / "Report"
LOG_DIR = PROJECT_ROOT / "logs"
SESSION_DIR = PROJECT_ROOT / "sessions"

# 确保目录存在
for directory in [DATA_DIR, REPORT_DIR, LOG_DIR, SESSION_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


class LLMConfig:
    """大模型配置"""
    # Qwen 配置
    QWEN_API_BASE: str = os.getenv("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QWEN_API_KEY: Optional[str] = os.getenv("QWEN_API_KEY")
    QWEN_MODEL_NAME: str = os.getenv("QWEN_MODEL_NAME", "qwen-plus")
    
    # OpenAI 兼容配置
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", QWEN_API_BASE)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", QWEN_API_KEY)
    
    # 模型参数
    TEMPERATURE: float = float(os.getenv("MODEL_TEMPERATURE", "0.7"))
    MAX_TOKENS: int = int(os.getenv("MODEL_MAX_TOKENS", "8192"))
    TOP_P: float = float(os.getenv("MODEL_TOP_P", "0.9"))
    
    # 请求配置
    REQUEST_TIMEOUT: int = int(os.getenv("LLM_REQUEST_TIMEOUT", "60"))  # 秒
    MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    RETRY_DELAY: float = float(os.getenv("LLM_RETRY_DELAY", "1.0"))  # 秒
    
    @classmethod
    def validate(cls) -> bool:
        """验证配置是否完整"""
        if not cls.QWEN_API_KEY and not cls.OPENAI_API_KEY:
            raise ValueError("未配置API密钥，请设置 QWEN_API_KEY 或 OPENAI_API_KEY")
        return True


class SystemConfig:
    """系统配置"""
    # 系统名称和版本
    SYSTEM_NAME: str = "Aquamind Systems"
    VERSION: str = "2.0.0"
    
    # 运行模式
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "False").lower() == "true"
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "True").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # 缓存有效期（秒）
    
    # 并发配置
    MAX_CONCURRENT_AGENTS: int = int(os.getenv("MAX_CONCURRENT_AGENTS", "5"))
    AGENT_TIMEOUT: int = int(os.getenv("AGENT_TIMEOUT", "120"))  # 秒
    
    # 数据配置
    HISTORICAL_DATA_FILE: str = "Toxicity.csv"
    MAX_HISTORICAL_DAYS: int = int(os.getenv("MAX_HISTORICAL_DAYS", "90"))


class LogConfig:
    """日志配置"""
    # 日志级别
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # 日志格式
    LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    DATE_FORMAT: str = '%Y-%m-%d %H:%M:%S'
    
    # 日志文件
    LOG_FILE: str = str(LOG_DIR / "aquamind.log")
    ERROR_LOG_FILE: str = str(LOG_DIR / "error.log")
    
    # 日志轮转
    MAX_LOG_SIZE: int = 10 * 1024 * 1024  # 10MB
    BACKUP_COUNT: int = 5


class AgentConfig:
    """智能体配置"""
    # 毒性等级阈值
    TOXICITY_LOW_THRESHOLD: float = float(os.getenv("TOXICITY_LOW_THRESHOLD", "1.5"))
    TOXICITY_HIGH_THRESHOLD: float = float(os.getenv("TOXICITY_HIGH_THRESHOLD", "3.0"))
    
    # 转盘控制参数
    TURNTABLE_MIN_FREQUENCY: float = 5.0  # Hz
    TURNTABLE_MAX_FREQUENCY: float = 50.0  # Hz
    TURNTABLE_REACTORS_COUNT: int = 3
    
    # MBR控制参数
    MBR_TMP_NORMAL: float = 20.0  # kPa
    MBR_TMP_WARNING: float = 30.0  # kPa
    MBR_MIN_FLUX: float = 15.0  # LMH
    MBR_MAX_FLUX: float = 20.0  # LMH
    
    # 再生控制参数
    CARBON_EFFICIENCY_THRESHOLD: float = 70.0  # %
    REGENERATION_TEMP: float = 800.0  # °C
    REGENERATION_FEED_RATE: float = 30.0  # kg/h
    
    # 诊断参数
    HEALTH_SCORE_EXCELLENT: float = 90.0
    HEALTH_SCORE_GOOD: float = 75.0
    HEALTH_SCORE_WARNING: float = 60.0


class IntentConfig:
    """意图识别配置"""
    # 意图关键词映射
    INTENT_KEYWORDS = {
        "collect_feedback": ["反馈", "记录", "feedback", "建议", "意见", "改进"],
        "check_regeneration": ["再生", "饱和", "regenerat", "再生温度", "加热"],
        "system_diagnostic": ["诊断", "评估", "状态", "健康", "检测系统"],
        "predict_toxicity": ["预测", "毒性", "forecast", "predict"],
        "control_mbr": ["mbr", "膜", "通量", "tmp", "跨膜压"],
        "control_turntable": ["转盘", "频率", "转速", "活性炭", "吸附"],
        "full_analysis": ["完整", "综合", "全部", "所有", "整体"]
    }
    
    # 意图优先级（数字越大优先级越高）
    INTENT_PRIORITY = {
        "collect_feedback": 7,
        "check_regeneration": 6,
        "system_diagnostic": 5,
        "predict_toxicity": 4,
        "control_mbr": 3,
        "control_turntable": 2,
        "full_analysis": 1
    }


class PLCConfig:
    """PLC配置"""
    # PLC连接参数（预留）
    PLC_ENABLED: bool = os.getenv("PLC_ENABLED", "False").lower() == "true"
    PLC_HOST: Optional[str] = os.getenv("PLC_HOST")
    PLC_PORT: int = int(os.getenv("PLC_PORT", "502"))
    PLC_TIMEOUT: float = float(os.getenv("PLC_TIMEOUT", "5.0"))
    
    # PLC变量前缀
    TURNTABLE_VAR_PREFIX: str = "MB01.TT"
    MBR_VAR_PREFIX: str = "MB02.MBR"
    REGENERATION_VAR_PREFIX: str = "MB03.RG"


# 配置验证
def validate_config():
    """验证所有配置"""
    try:
        LLMConfig.validate()
        print(f"[Config] {SystemConfig.SYSTEM_NAME} v{SystemConfig.VERSION} 配置加载成功")
        if SystemConfig.DEBUG_MODE:
            print("[Config] DEBUG模式已启用")
        return True
    except Exception as e:
        print(f"[Config] 配置验证失败: {e}")
        return False


# 导出配置实例
llm_config = LLMConfig()
system_config = SystemConfig()
log_config = LogConfig()
agent_config = AgentConfig()
intent_config = IntentConfig()
plc_config = PLCConfig()


if __name__ == "__main__":
    # 测试配置
    print("=" * 60)
    print("Aquamind 配置测试")
    print("=" * 60)
    
    validate_config()
    
    print("\n[LLM配置]")
    print(f"  API Base: {llm_config.QWEN_API_BASE}")
    print(f"  Model: {llm_config.QWEN_MODEL_NAME}")
    print(f"  Temperature: {llm_config.TEMPERATURE}")
    print(f"  Max Tokens: {llm_config.MAX_TOKENS}")
    
    print("\n[系统配置]")
    print(f"  系统名称: {system_config.SYSTEM_NAME}")
    print(f"  版本: {system_config.VERSION}")
    print(f"  调试模式: {system_config.DEBUG_MODE}")
    print(f"  缓存启用: {system_config.ENABLE_CACHE}")
    
    print("\n[日志配置]")
    print(f"  日志级别: {log_config.LOG_LEVEL}")
    print(f"  日志文件: {log_config.LOG_FILE}")
    
    print("\n[智能体配置]")
    print(f"  毒性低阈值: {agent_config.TOXICITY_LOW_THRESHOLD}")
    print(f"  毒性高阈值: {agent_config.TOXICITY_HIGH_THRESHOLD}")
    print(f"  活性炭效率阈值: {agent_config.CARBON_EFFICIENCY_THRESHOLD}%")
    
    print("\n配置测试完成！")
