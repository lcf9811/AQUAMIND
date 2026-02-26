"""
LLM 接口模块

使用 LangChain 最新 API 统一模型初始化和调用。
"""

import os
from typing import Optional
from functools import lru_cache

from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

from aquamind.core.config import settings


def get_model(
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **kwargs
) -> BaseChatModel:
    """
    获取 LLM 模型实例
    
    使用 OpenAI 兼容接口，支持阿里云千问等模型。
    
    Args:
        model_name: 模型名称，默认使用配置值
        temperature: 生成温度，默认使用配置值
        max_tokens: 最大 token 数，默认使用配置值
        **kwargs: 其他 ChatOpenAI 参数
    
    Returns:
        BaseChatModel: LangChain 聊天模型实例
    
    Example:
        >>> model = get_model()
        >>> response = model.invoke("你好")
        
        >>> # 自定义参数
        >>> model = get_model(temperature=0.2, model_name="qwen-plus")
    """
    return ChatOpenAI(
        api_key=settings.llm.api_key,
        base_url=settings.llm.api_base,
        model=model_name or settings.llm.model_name,
        temperature=temperature if temperature is not None else settings.llm.temperature,
        max_tokens=max_tokens or settings.llm.max_tokens,
        timeout=settings.llm.request_timeout,
        max_retries=settings.llm.max_retries,
        **kwargs
    )


@lru_cache(maxsize=1)
def get_cached_model() -> BaseChatModel:
    """
    获取缓存的模型实例（单例模式）
    
    适用于不需要动态调整参数的场景。
    """
    return get_model()


def call_llm(
    prompt: str,
    model: Optional[BaseChatModel] = None,
    temperature: Optional[float] = None
) -> str:
    """
    简单的 LLM 调用接口
    
    Args:
        prompt: 用户输入
        model: 模型实例，默认使用缓存模型
        temperature: 临时调整温度
    
    Returns:
        str: 模型响应文本
    """
    if model is None:
        if temperature is not None:
            model = get_model(temperature=temperature)
        else:
            model = get_cached_model()
    
    response = model.invoke(prompt)
    return response.content


if __name__ == "__main__":
    print("LLM 接口测试")
    print("=" * 60)
    
    # 测试模型初始化
    print("\n初始化模型...")
    try:
        model = get_model()
        print(f"模型类型: {type(model).__name__}")
        print(f"模型名称: {settings.llm.model_name}")
        print(f"API Base: {settings.llm.api_base}")
        
        # 如果有 API Key，测试调用
        if settings.llm.api_key:
            print("\n测试调用...")
            response = call_llm("请用一句话介绍你自己")
            print(f"响应: {response[:100]}...")
        else:
            print("\n未配置 API_KEY，跳过调用测试")
    except Exception as e:
        print(f"错误: {e}")
