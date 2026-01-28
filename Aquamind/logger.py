"""
Aquamind 统一日志管理系统
提供结构化日志、日志轮转、多级别输出
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime

from config import log_config, system_config


class AquamindLogger:
    """Aquamind 日志管理器"""
    
    _instance = None
    _loggers = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._setup_root_logger()
    
    def _setup_root_logger(self):
        """配置根日志器"""
        # 创建日志目录
        log_dir = Path(log_config.LOG_FILE).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if system_config.DEBUG_MODE else logging.INFO)
        
        # 清除已有的处理器
        root_logger.handlers.clear()
        
        # 创建格式器
        formatter = logging.Formatter(
            log_config.LOG_FORMAT,
            datefmt=log_config.DATE_FORMAT
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 文件处理器（普通日志）
        file_handler = RotatingFileHandler(
            log_config.LOG_FILE,
            maxBytes=log_config.MAX_LOG_SIZE,
            backupCount=log_config.BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # 错误日志处理器
        error_handler = RotatingFileHandler(
            log_config.ERROR_LOG_FILE,
            maxBytes=log_config.MAX_LOG_SIZE,
            backupCount=log_config.BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        获取指定名称的日志器
        
        Args:
            name: 日志器名称（通常使用模块名）
        
        Returns:
            配置好的日志器
        """
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        
        return self._loggers[name]


# 全局日志管理器实例
_log_manager = AquamindLogger()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取日志器的便捷函数
    
    Args:
        name: 日志器名称，通常使用 __name__
    
    Returns:
        配置好的日志器
    
    Example:
        >>> from logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("系统启动")
    """
    if name is None:
        name = "aquamind"
    
    return _log_manager.get_logger(name)


class PerformanceLogger:
    """性能日志记录器"""
    
    def __init__(self, operation_name: str, logger: logging.Logger = None):
        self.operation_name = operation_name
        self.logger = logger or get_logger("performance")
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f"[开始] {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type is not None:
            self.logger.error(
                f"[失败] {self.operation_name} - 耗时: {elapsed:.2f}秒 - 错误: {exc_val}"
            )
        else:
            self.logger.info(
                f"[完成] {self.operation_name} - 耗时: {elapsed:.2f}秒"
            )
        
        return False  # 不抑制异常


class AgentLogger:
    """智能体专用日志记录器"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = get_logger(f"agent.{agent_name}")
    
    def log_initialization(self):
        """记录初始化"""
        self.logger.info(f"[{self.agent_name}] 智能体初始化完成")
    
    def log_request(self, user_input: str):
        """记录请求"""
        self.logger.info(f"[{self.agent_name}] 收到请求: {user_input[:100]}")
    
    def log_response(self, response_length: int, response_time: float):
        """记录响应"""
        self.logger.info(
            f"[{self.agent_name}] 响应完成 - "
            f"长度: {response_length}字符, 耗时: {response_time:.2f}秒"
        )
    
    def log_error(self, error: Exception, context: str = ""):
        """记录错误"""
        self.logger.error(
            f"[{self.agent_name}] 错误{f' ({context})' if context else ''}: {error}",
            exc_info=True
        )
    
    def log_llm_call(self, prompt_length: int, response_length: int, latency: float):
        """记录LLM调用"""
        self.logger.debug(
            f"[{self.agent_name}] LLM调用 - "
            f"提示词: {prompt_length}字符, "
            f"响应: {response_length}字符, "
            f"延迟: {latency:.2f}秒"
        )


def log_system_info():
    """记录系统信息"""
    logger = get_logger("system")
    logger.info("=" * 60)
    logger.info(f"{system_config.SYSTEM_NAME} v{system_config.VERSION}")
    logger.info(f"调试模式: {system_config.DEBUG_MODE}")
    logger.info(f"日志级别: {log_config.LOG_LEVEL}")
    logger.info(f"日志文件: {log_config.LOG_FILE}")
    logger.info("=" * 60)


# 初始化时记录系统信息
if __name__ != "__main__":
    log_system_info()


if __name__ == "__main__":
    # 测试日志系统
    print("测试 Aquamind 日志系统")
    print("=" * 60)
    
    # 测试基本日志
    logger = get_logger("test")
    logger.debug("这是调试信息")
    logger.info("这是普通信息")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")
    
    # 测试性能日志
    print("\n测试性能日志:")
    with PerformanceLogger("测试操作"):
        import time
        time.sleep(0.5)
    
    # 测试智能体日志
    print("\n测试智能体日志:")
    agent_logger = AgentLogger("TestAgent")
    agent_logger.log_initialization()
    agent_logger.log_request("测试请求输入")
    agent_logger.log_response(500, 1.23)
    agent_logger.log_llm_call(100, 500, 0.8)
    
    try:
        raise ValueError("测试错误")
    except Exception as e:
        agent_logger.log_error(e, "测试上下文")
    
    print(f"\n日志已保存到: {log_config.LOG_FILE}")
    print("=" * 60)
