"""
Aquamind 异常定义

统一的异常处理体系。
"""

from typing import Optional, Dict, Any


class AquamindError(Exception):
    """Aquamind 基础异常类"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "AQUAMIND_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        base_msg = f"[{self.error_code}] {self.message}"
        if self.details:
            base_msg += f" - {self.details}"
        return base_msg


# ============ 配置相关异常 ============

class ConfigError(AquamindError):
    """配置错误"""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="CONFIG_ERROR",
            details={"config_key": config_key} if config_key else {}
        )


class APIKeyMissingError(ConfigError):
    """API 密钥缺失"""
    
    def __init__(self, provider: str = "LLM"):
        super().__init__(
            message=f"{provider} API 密钥未配置，请检查 .env 文件",
            config_key="API_KEY"
        )


# ============ LLM 相关异常 ============

class LLMError(AquamindError):
    """LLM 调用错误"""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if model_name:
            error_details["model_name"] = model_name
        super().__init__(
            message=message,
            error_code="LLM_ERROR",
            details=error_details
        )


class LLMTimeoutError(LLMError):
    """LLM 调用超时"""
    
    def __init__(self, timeout: float, model_name: Optional[str] = None):
        super().__init__(
            message=f"LLM 调用超时 (>{timeout}秒)",
            model_name=model_name,
            details={"timeout": timeout}
        )


class LLMRateLimitError(LLMError):
    """LLM 频率限制"""
    
    def __init__(
        self,
        retry_after: Optional[float] = None,
        model_name: Optional[str] = None
    ):
        super().__init__(
            message="LLM API 触发频率限制",
            model_name=model_name,
            details={"retry_after": retry_after} if retry_after else {}
        )


# ============ Agent 相关异常 ============

class AgentError(AquamindError):
    """Agent 执行错误"""
    
    def __init__(
        self,
        message: str,
        agent_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if agent_name:
            error_details["agent_name"] = agent_name
        super().__init__(
            message=message,
            error_code="AGENT_ERROR",
            details=error_details
        )


class AgentInitError(AgentError):
    """Agent 初始化失败"""
    
    def __init__(self, agent_name: str, reason: str):
        super().__init__(
            message=f"Agent 初始化失败: {reason}",
            agent_name=agent_name
        )


class AgentExecutionError(AgentError):
    """Agent 执行失败"""
    
    def __init__(self, agent_name: str, operation: str, reason: str):
        super().__init__(
            message=f"Agent 执行失败: {reason}",
            agent_name=agent_name,
            details={"operation": operation}
        )


class AgentTimeoutError(AgentError):
    """Agent 执行超时"""
    
    def __init__(self, agent_name: str, timeout: float):
        super().__init__(
            message=f"Agent 执行超时 (>{timeout}秒)",
            agent_name=agent_name,
            details={"timeout": timeout}
        )


# ============ 数据相关异常 ============

class DataError(AquamindError):
    """数据错误"""
    
    def __init__(self, message: str, data_source: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="DATA_ERROR",
            details={"data_source": data_source} if data_source else {}
        )


class DataNotFoundError(DataError):
    """数据未找到"""
    
    def __init__(self, data_type: str, data_id: Optional[str] = None):
        message = f"未找到 {data_type} 数据"
        if data_id:
            message += f" (ID: {data_id})"
        super().__init__(message, data_source=data_type)


class DataValidationError(DataError):
    """数据验证失败"""
    
    def __init__(self, field: str, reason: str, value: Any = None):
        message = f"数据验证失败: {field} - {reason}"
        super().__init__(message)
        self.details.update({
            "field": field,
            "reason": reason,
            "value": str(value) if value is not None else None
        })


# ============ 控制相关异常 ============

class ControlError(AquamindError):
    """控制系统错误"""
    
    def __init__(self, message: str, system: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="CONTROL_ERROR",
            details={"system": system} if system else {}
        )


class PLCError(ControlError):
    """PLC 通信错误"""
    
    def __init__(self, reason: str, plc_address: Optional[str] = None):
        super().__init__(
            message=f"PLC 通信失败: {reason}",
            system="PLC"
        )
        if plc_address:
            self.details["plc_address"] = plc_address


# ============ 工具函数 ============

def handle_exception(
    exc: Exception,
    logger=None,
    context: str = ""
) -> str:
    """
    统一异常处理函数
    
    Args:
        exc: 异常对象
        logger: 日志器
        context: 上下文信息
    
    Returns:
        用户友好的错误消息
    """
    if isinstance(exc, AquamindError):
        error_msg = str(exc)
    else:
        error_msg = f"未预期的错误: {type(exc).__name__} - {str(exc)}"
    
    if logger:
        if context:
            logger.error(f"[{context}] {error_msg}", exc_info=True)
        else:
            logger.error(error_msg, exc_info=True)
    
    return error_msg
