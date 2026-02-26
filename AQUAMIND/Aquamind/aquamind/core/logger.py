"""
Aquamind 日志管理

提供结构化日志、日志轮转、多级别输出。
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime

from aquamind.core.config import settings, LOG_DIR


class LoggerManager:
    """日志管理器（单例）"""
    
    _instance: Optional["LoggerManager"] = None
    _initialized: bool = False
    
    def __new__(cls) -> "LoggerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._loggers: dict = {}
        self._setup_root_logger()
    
    def _setup_root_logger(self):
        """配置根日志器"""
        # 确保日志目录存在
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # 配置根日志器
        root_logger = logging.getLogger()
        level = logging.DEBUG if settings.system.debug_mode else logging.INFO
        root_logger.setLevel(level)
        
        # 清除已有处理器
        root_logger.handlers.clear()
        
        # 格式器
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 文件处理器（普通日志）
        log_file = LOG_DIR / "aquamind.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # 错误日志处理器
        error_log_file = LOG_DIR / "error.log"
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志器"""
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(name)
        return self._loggers[name]


# 全局日志管理器
_manager = LoggerManager()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取日志器
    
    Args:
        name: 日志器名称，通常使用 __name__
    
    Returns:
        配置好的日志器
    
    Example:
        >>> from aquamind.core.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("系统启动")
    """
    return _manager.get_logger(name or "aquamind")


class PerformanceLogger:
    """性能日志记录器（上下文管理器）"""
    
    def __init__(self, operation: str, logger: Optional[logging.Logger] = None):
        self.operation = operation
        self.logger = logger or get_logger("performance")
        self.start_time: Optional[datetime] = None
    
    def __enter__(self) -> "PerformanceLogger":
        self.start_time = datetime.now()
        self.logger.debug(f"[开始] {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type is not None:
            self.logger.error(
                f"[失败] {self.operation} - 耗时: {elapsed:.2f}秒 - 错误: {exc_val}"
            )
        else:
            self.logger.info(
                f"[完成] {self.operation} - 耗时: {elapsed:.2f}秒"
            )
        
        return False  # 不抑制异常


class AgentLogger:
    """智能体专用日志器"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = get_logger(f"agent.{agent_name}")
    
    def log_init(self):
        """记录初始化"""
        self.logger.info(f"[{self.agent_name}] 初始化完成")
    
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
    
    def log_tool_call(self, tool_name: str, args: dict):
        """记录工具调用"""
        self.logger.debug(
            f"[{self.agent_name}] 调用工具: {tool_name}, 参数: {args}"
        )


def log_system_info():
    """记录系统启动信息"""
    logger = get_logger("system")
    logger.info("=" * 60)
    logger.info(f"{settings.system.system_name} v{settings.system.version}")
    logger.info(f"调试模式: {settings.system.debug_mode}")
    logger.info(f"日志级别: {settings.system.log_level}")
    logger.info(f"日志目录: {LOG_DIR}")
    logger.info("=" * 60)


def setup_logging(level: str = "INFO"):
    """设置日志级别
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
    """
    root_logger = logging.getLogger()
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    
    # 同时更新控制台处理器的级别
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            handler.setLevel(log_level)
