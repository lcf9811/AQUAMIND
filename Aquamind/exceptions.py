"""
Aquamind 异常定义
统一的异常处理体系
"""


class AquamindException(Exception):
    """Aquamind 基础异常类"""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code or "AQUAMIND_ERROR"
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self):
        base_msg = f"[{self.error_code}] {self.message}"
        if self.details:
            base_msg += f" - Details: {self.details}"
        return base_msg


# ============ 配置相关异常 ============

class ConfigurationError(AquamindException):
    """配置错误"""
    
    def __init__(self, message: str, config_key: str = None):
        super().__init__(
            message=message,
            error_code="CONFIG_ERROR",
            details={"config_key": config_key} if config_key else {}
        )


class APIKeyMissingError(ConfigurationError):
    """API密钥缺失"""
    
    def __init__(self, provider: str = "LLM"):
        super().__init__(
            message=f"{provider} API密钥未配置，请检查环境变量",
            config_key="API_KEY"
        )


# ============ LLM相关异常 ============

class LLMError(AquamindException):
    """LLM调用错误"""
    
    def __init__(self, message: str, model_name: str = None, details: dict = None):
        error_details = details or {}
        if model_name:
            error_details["model_name"] = model_name
        
        super().__init__(
            message=message,
            error_code="LLM_ERROR",
            details=error_details
        )


class LLMTimeoutError(LLMError):
    """LLM调用超时"""
    
    def __init__(self, timeout: float, model_name: str = None):
        super().__init__(
            message=f"LLM调用超时 (>{timeout}秒)",
            model_name=model_name,
            details={"timeout": timeout}
        )


class LLMRateLimitError(LLMError):
    """LLM调用频率限制"""
    
    def __init__(self, retry_after: float = None, model_name: str = None):
        super().__init__(
            message="LLM API触发频率限制",
            model_name=model_name,
            details={"retry_after": retry_after} if retry_after else {}
        )


class LLMResponseError(LLMError):
    """LLM响应解析错误"""
    
    def __init__(self, message: str, raw_response: str = None):
        super().__init__(
            message=message,
            details={"raw_response": raw_response[:200] if raw_response else None}
        )


# ============ Agent相关异常 ============

class AgentError(AquamindException):
    """Agent执行错误"""
    
    def __init__(self, message: str, agent_name: str = None, details: dict = None):
        error_details = details or {}
        if agent_name:
            error_details["agent_name"] = agent_name
        
        super().__init__(
            message=message,
            error_code="AGENT_ERROR",
            details=error_details
        )


class AgentInitializationError(AgentError):
    """Agent初始化失败"""
    
    def __init__(self, agent_name: str, reason: str):
        super().__init__(
            message=f"Agent初始化失败: {reason}",
            agent_name=agent_name
        )


class AgentExecutionError(AgentError):
    """Agent执行失败"""
    
    def __init__(self, agent_name: str, operation: str, reason: str):
        super().__init__(
            message=f"Agent执行失败: {reason}",
            agent_name=agent_name,
            details={"operation": operation}
        )


class AgentTimeoutError(AgentError):
    """Agent执行超时"""
    
    def __init__(self, agent_name: str, timeout: float):
        super().__init__(
            message=f"Agent执行超时 (>{timeout}秒)",
            agent_name=agent_name,
            details={"timeout": timeout}
        )


# ============ 数据相关异常 ============

class DataError(AquamindException):
    """数据错误"""
    
    def __init__(self, message: str, data_source: str = None):
        super().__init__(
            message=message,
            error_code="DATA_ERROR",
            details={"data_source": data_source} if data_source else {}
        )


class DataNotFoundError(DataError):
    """数据未找到"""
    
    def __init__(self, data_type: str, data_id: str = None):
        message = f"未找到{data_type}数据"
        if data_id:
            message += f" (ID: {data_id})"
        
        super().__init__(message, data_source=data_type)


class DataValidationError(DataError):
    """数据验证失败"""
    
    def __init__(self, field: str, reason: str, value=None):
        message = f"数据验证失败: {field} - {reason}"
        details = {"field": field, "reason": reason}
        if value is not None:
            details["value"] = str(value)
        
        super().__init__(message)
        self.details.update(details)


class HistoricalDataError(DataError):
    """历史数据错误"""
    
    def __init__(self, reason: str):
        super().__init__(
            message=f"历史数据处理失败: {reason}",
            data_source="historical_data"
        )


# ============ 控制相关异常 ============

class ControlError(AquamindException):
    """控制系统错误"""
    
    def __init__(self, message: str, system: str = None):
        super().__init__(
            message=message,
            error_code="CONTROL_ERROR",
            details={"system": system} if system else {}
        )


class PLCCommunicationError(ControlError):
    """PLC通信错误"""
    
    def __init__(self, reason: str, plc_address: str = None):
        super().__init__(
            message=f"PLC通信失败: {reason}",
            system="PLC"
        )
        if plc_address:
            self.details["plc_address"] = plc_address


class ControlParameterError(ControlError):
    """控制参数错误"""
    
    def __init__(self, parameter: str, value, reason: str):
        super().__init__(
            message=f"控制参数'{parameter}'无效: {reason}",
            system="parameter_validation"
        )
        self.details.update({"parameter": parameter, "value": str(value)})


# ============ 意图识别异常 ============

class IntentRecognitionError(AquamindException):
    """意图识别错误"""
    
    def __init__(self, user_input: str, reason: str = "无法识别意图"):
        super().__init__(
            message=reason,
            error_code="INTENT_ERROR",
            details={"user_input": user_input[:100]}
        )


# ============ 系统异常 ============

class SystemError(AquamindException):
    """系统错误"""
    
    def __init__(self, message: str, component: str = None):
        super().__init__(
            message=message,
            error_code="SYSTEM_ERROR",
            details={"component": component} if component else {}
        )


class ResourceExhaustedError(SystemError):
    """资源耗尽"""
    
    def __init__(self, resource_type: str, details: dict = None):
        super().__init__(
            message=f"资源耗尽: {resource_type}",
            component="resource_manager"
        )
        if details:
            self.details.update(details)


# ============ 工具函数 ============

def handle_exception(exc: Exception, logger=None, context: str = "") -> str:
    """
    统一异常处理函数
    
    Args:
        exc: 异常对象
        logger: 日志器
        context: 上下文信息
    
    Returns:
        用户友好的错误消息
    """
    if isinstance(exc, AquamindException):
        error_msg = str(exc)
    else:
        error_msg = f"未预期的错误: {type(exc).__name__} - {str(exc)}"
    
    if logger:
        if context:
            logger.error(f"[{context}] {error_msg}", exc_info=True)
        else:
            logger.error(error_msg, exc_info=True)
    
    return error_msg


if __name__ == "__main__":
    # 测试异常系统
    print("测试 Aquamind 异常系统")
    print("=" * 60)
    
    # 测试配置异常
    try:
        raise APIKeyMissingError("Qwen")
    except AquamindException as e:
        print(f"配置异常: {e}")
    
    # 测试LLM异常
    try:
        raise LLMTimeoutError(30.0, "qwen-plus")
    except LLMError as e:
        print(f"LLM异常: {e}")
    
    # 测试Agent异常
    try:
        raise AgentExecutionError("ToxicityAgent", "predict", "模型调用失败")
    except AgentError as e:
        print(f"Agent异常: {e}")
    
    # 测试数据异常
    try:
        raise DataValidationError("ammonia_n", "数值超出范围", -5.0)
    except DataError as e:
        print(f"数据异常: {e}")
    
    # 测试异常处理函数
    try:
        raise ValueError("普通异常测试")
    except Exception as e:
        msg = handle_exception(e, context="测试")
        print(f"\n异常处理结果: {msg}")
    
    print("=" * 60)
