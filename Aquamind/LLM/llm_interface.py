"""
大模型API接口管理器
支持Qwen和OpenAI兼容接口

功能:
- 自动重试机制
- 超时控制
- 错误处理
- 日志记录
"""

import os
import openai
from dotenv import load_dotenv
import json
import time
from typing import Dict, Any, List, Optional
import sys

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 导入配置和异常
try:
    from config import llm_config
    from logger import get_logger
    from exceptions import (
        LLMError,
        LLMTimeoutError,
        LLMRateLimitError,
        LLMResponseError
    )
    USE_ENHANCED_FEATURES = True
except ImportError:
    # 如果配置文件不存在，使用基础功能
    USE_ENHANCED_FEATURES = False
    llm_config = None

class LLMInterface:
    """
    大模型接口管理器
    
    功能:
    - 支持Qwen和OpenAI兼容接口
    - 自动重试机制（处理网络错误、频率限制）
    - 超时控制
    - 详细错误日志
    """

    def __init__(self):
        """初始化大模型接口"""
        # 初始化日志
        if USE_ENHANCED_FEATURES:
            self.logger = get_logger(__name__)
        else:
            self.logger = None
        
        # 从配置或环境变量获取参数
        if USE_ENHANCED_FEATURES and llm_config:
            self.qwen_api_base = llm_config.QWEN_API_BASE
            self.qwen_api_key = llm_config.QWEN_API_KEY
            self.qwen_model_name = llm_config.QWEN_MODEL_NAME
            self.openai_api_base = llm_config.OPENAI_API_BASE
            self.openai_api_key = llm_config.OPENAI_API_KEY
            self.timeout = llm_config.REQUEST_TIMEOUT
            self.max_retries = llm_config.MAX_RETRIES
            self.retry_delay = llm_config.RETRY_DELAY
        else:
            # 回退到环境变量
            self.qwen_api_base = os.getenv("QWEN_API_BASE")
            self.qwen_api_key = os.getenv("QWEN_API_KEY")
            self.qwen_model_name = os.getenv("QWEN_MODEL_NAME", "qwen-plus")
            self.openai_api_base = os.getenv("OPENAI_API_BASE")
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
            self.timeout = int(os.getenv("LLM_REQUEST_TIMEOUT", "60"))
            self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
            self.retry_delay = float(os.getenv("LLM_RETRY_DELAY", "1.0"))

        # 设置OpenAI客户端
        try:
            self.client = openai.OpenAI(
                base_url=self.qwen_api_base or self.openai_api_base,
                api_key=self.qwen_api_key or self.openai_api_key,
                timeout=self.timeout
            )
            self.model_name = self.qwen_model_name
            
            if self.logger:
                self.logger.info(f"LLM接口初始化成功 - 模型: {self.model_name}")
        except Exception as e:
            if self.logger:
                self.logger.error(f"LLM接口初始化失败: {e}")
            raise

    def call_llm(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """
        调用大模型API（带重试机制）

        Args:
            prompt: 输入提示
            max_tokens: 最大输出token数
            temperature: 生成温度

        Returns:
            模型生成的文本
            
        Raises:
            LLMError: LLM调用失败
            LLMTimeoutError: 请求超时
            LLMRateLimitError: 频率限制
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                latency = time.time() - start_time
                
                if self.logger:
                    self.logger.debug(
                        f"LLM调用成功 - 耗时: {latency:.2f}秒, "
                        f"提示词: {len(prompt)}字符"
                    )
                
                return response.choices[0].message.content
                
            except openai.Timeout as e:
                last_error = e
                if self.logger:
                    self.logger.warning(
                        f"LLM请求超时 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                    )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    
            except openai.RateLimitError as e:
                last_error = e
                if self.logger:
                    self.logger.warning(
                        f"LLM频率限制 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                    )
                # 频率限制时等待更长时间
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1) * 2)
                    
            except openai.APIError as e:
                last_error = e
                if self.logger:
                    self.logger.error(f"LLM API错误: {e}")
                # API错误通常不需要重试
                break
                
            except Exception as e:
                last_error = e
                if self.logger:
                    self.logger.error(
                        f"LLM调用异常 (尝试 {attempt + 1}/{self.max_retries}): {e}"
                    )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        # 所有重试都失败
        error_msg = f"LLM调用失败（已重试{self.max_retries}次）: {last_error}"
        if self.logger:
            self.logger.error(error_msg)
        
        # 根据增强功能决定是否抛出异常
        if USE_ENHANCED_FEATURES:
            if isinstance(last_error, openai.Timeout):
                raise LLMTimeoutError(self.timeout, self.model_name)
            elif isinstance(last_error, openai.RateLimitError):
                raise LLMRateLimitError(model_name=self.model_name)
            else:
                raise LLMError(error_msg, self.model_name)
        else:
            # 兼容模式：返回错误消息
            return f"抱歉，模型调用出现问题: {str(last_error)}"

    def predict_toxicity_with_llm(self, input_data: Dict[str, Any], historical_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        使用大模型预测毒性

        Args:
            input_data: 输入的水质参数
            historical_data: 历史数据

        Returns:
            包含预测结果的字典
        """
        # 构建提示词
        prompt = self._build_toxicity_prediction_prompt(input_data, historical_data)

        # 调用大模型
        llm_response = self.call_llm(prompt, max_tokens=500, temperature=0.3)

        # 解析响应
        return self._parse_llm_response(llm_response)

    def _build_toxicity_prediction_prompt(self, input_data: Dict[str, Any], historical_data: Dict[str, Any] = None) -> str:
        """构建毒性预测的提示词"""
        prompt = f"""
你是一个专业的水质毒性预测专家。请根据以下水质参数预测未来24小时的毒性水平。

当前水质参数：
- 温度: {input_data.get('temperature', 0)}°C
- 湿度: {input_data.get('humidity', 0)}%
- 氨氮: {input_data.get('ammonia_n', 0)} mg/L
- 硝氮: {input_data.get('nitrate_n', 0)} mg/L
- pH值: {input_data.get('ph', 0)}
- 降雨量: {input_data.get('rainfall', 0)} mm

"""

        if historical_data:
            prompt += f"""
历史数据统计：
- 平均毒性: {historical_data.get('mean_toxicity', 0):.2f}
- 毒性标准差: {historical_data.get('std_toxicity', 0):.2f}
- 最大毒性: {historical_data.get('max_toxicity', 0):.2f}
- 最小毒性: {historical_data.get('min_toxicity', 0):.2f}

"""

        prompt += """
请基于以上信息，分析水质状况并预测未来24小时的毒性水平。

请按照以下JSON格式返回结果：
{
    "predicted_toxicity": 数值,
    "toxicity_level": "低|中|高",
    "confidence": 0.0-1.0之间的置信度,
    "factors": ["影响毒性的因素列表"],
    "explanation": "详细的分析说明",
    "recommendations": ["建议措施列表"]
}
"""
        return prompt

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析大模型响应"""
        try:
            # 尝试提取JSON部分
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                result = json.loads(json_str)

                # 确保必要字段存在
                if 'predicted_toxicity' not in result:
                    result['predicted_toxicity'] = 2.0
                if 'toxicity_level' not in result:
                    result['toxicity_level'] = '中'
                if 'confidence' not in result:
                    result['confidence'] = 0.7

                return result
            else:
                # 如果没有JSON格式，返回默认值
                return {
                    "predicted_toxicity": 2.0,
                    "toxicity_level": "中",
                    "confidence": 0.5,
                    "factors": ["数据解析失败"],
                    "explanation": "无法解析模型响应",
                    "recommendations": ["请检查输入数据"]
                }
        except json.JSONDecodeError:
            # JSON解析失败，返回错误信息
            return {
                "predicted_toxicity": 2.0,
                "toxicity_level": "中",
                "confidence": 0.3,
                "factors": ["响应格式错误"],
                "explanation": f"模型响应: {response[:200]}...",
                "recommendations": ["请重试预测"]
            }

    def chat(self, message: str) -> str:
        """与大模型聊天"""
        return self.call_llm(message, max_tokens=500, temperature=0.7)


def test_llm_interface():
    """测试大模型接口"""
    print("初始化大模型接口...")
    llm = LLMInterface()

    print("\n测试1: 简单聊天")
    response = llm.chat("你好，介绍一下自己")
    print(f"模型回复: {response}")

    print("\n测试2: 毒性预测")
    test_data = {
        "temperature": 25.0,
        "humidity": 60.0,
        "ammonia_n": 10.0,
        "nitrate_n": 5.0,
        "ph": 7.0,
        "rainfall": 0.0
    }

    hist_data = {
        "mean_toxicity": 2.0,
        "std_toxicity": 0.5,
        "max_toxicity": 3.5,
        "min_toxicity": 0.5
    }

    result = llm.predict_toxicity_with_llm(test_data, hist_data)
    print(f"预测结果: {result}")


if __name__ == "__main__":
    test_llm_interface()