"""
OpenCLAW集成配置
使水处理智能体能够在OpenCLAW中配置和调用
"""

import importlib
import json
import os
import sys
from typing import Dict, Any, List
from flask import request, jsonify

# 添加当前目录到Python路径以确保模块导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入智能体类
try:
    from app.agents import (
        InletProcessAgent, OutletProcessAgent,
        ProcessStageAgent, AnaerobicProcessAgent,
        AnoxicProcessAgent, AerobicProcessAgent,
    )
except ImportError as e:
    print(f"警告: 无法导入智能体类: {e}")
    print("请确保app目录在Python路径中")
    # 定义虚拟类以避免运行时错误
    class BaseAgent:
        def __init__(self, *args, **kwargs):
            pass
    InletProcessAgent = OutletProcessAgent = BaseAgent
    ProcessStageAgent = AnaerobicProcessAgent = AnoxicProcessAgent = AerobicProcessAgent = BaseAgent


class OpenCLAWAgentRegistry:
    """OpenCLAW智能体注册表"""
    
    def __init__(self, config_file: str = "config/agent-skills.manifest.json"):
        """
        初始化智能体注册表
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self._load_config()
        self.agents = {}
        self.scada_base_url = os.getenv("SCADA_BASE_URL", "http://localhost:5000")
        
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"配置文件 {self.config_file} 不存在，使用默认配置")
            return {
                "project": "water_treatment_openclaw",
                "scada_http": {
                    "base_url_env": "SCADA_BASE_URL",
                    "default_timeout_ms": 8000
                },
                "agents": []
            }
    
    def register_agent(self, agent_id: str, agent_instance):
        """注册智能体实例"""
        self.agents[agent_id] = agent_instance
        print(f"智能体已注册: {agent_id}")
    
    def _import_agent_class(self, class_name: str):
        """动态导入智能体类以避免循环依赖"""
        try:
            # 直接使用文件顶部导入的类
            if class_name == "InletProcessAgent":
                return InletProcessAgent
            elif class_name == "OutletProcessAgent":
                return OutletProcessAgent
            elif class_name == "ProcessStageAgent":
                return ProcessStageAgent
            elif class_name == "AnaerobicProcessAgent":
                return AnaerobicProcessAgent
            elif class_name == "AnoxicProcessAgent":
                return AnoxicProcessAgent
            elif class_name == "AerobicProcessAgent":
                return AerobicProcessAgent
            else:
                raise ImportError(f"智能体类 {class_name} 未找到")
        except Exception as e:
            # 如果顶部导入失败，尝试动态导入
            try:
                module = importlib.import_module("app.agents")
                return getattr(module, class_name)
            except Exception as e2:
                raise ImportError(f"无法导入智能体类 {class_name}: {e}, {e2}")
    
    def initialize_agents(self):
        """初始化所有智能体"""
        # 动态导入智能体类
        InletProcessAgent = self._import_agent_class("InletProcessAgent")
        OutletProcessAgent = self._import_agent_class("OutletProcessAgent")
        
        # 初始化进水工艺智能体
        inlet_agent = InletProcessAgent(
            scada_base_url=self.scada_base_url,
            agent_id="inlet_process"
        )
        self.register_agent("inlet_process", inlet_agent)
        
        # 初始化出水工艺智能体
        outlet_agent = OutletProcessAgent(
            scada_base_url=self.scada_base_url,
            agent_id="outlet_process"
        )
        self.register_agent("outlet_process", outlet_agent)
        
        # 初始化工段编排智能体（含厌氧/缺氧/好氧三个子智能体）
        ProcessStageAgent = self._import_agent_class("ProcessStageAgent")
        process_stage_agent = ProcessStageAgent(
            scada_base_url=self.scada_base_url,
            agent_id="process_stage"
        )
        self.register_agent("process_stage", process_stage_agent)
        
        # 同时注册三个子智能体，使其可独立调用
        self.register_agent("anaerobic_process", process_stage_agent.anaerobic_agent)
        self.register_agent("anoxic_process", process_stage_agent.anoxic_agent)
        self.register_agent("aerobic_process", process_stage_agent.aerobic_agent)
        
        print(f"共初始化 {len(self.agents)} 个智能体")
    
    def get_agent(self, agent_id: str):
        """获取智能体实例"""
        return self.agents.get(agent_id)
    
    def list_agents(self) -> List[str]:
        """列出所有已注册的智能体"""
        return list(self.agents.keys())
    
    def get_agent_tools(self, agent_id: str) -> Dict[str, Any]:
        """获取智能体的工具定义"""
        agent = self.get_agent(agent_id)
        if agent and hasattr(agent, 'get_tools'):
            return agent.get_tools()
        return {}
    
    def execute_skill(self, agent_id: str, skill_name: str, **kwargs) -> Dict[str, Any]:
        """
        执行智能体技能
        
        Args:
            agent_id: 智能体ID
            skill_name: 技能名称
            **kwargs: 技能参数
            
        Returns:
            执行结果
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return {
                "ok": False,
                "error": f"智能体 {agent_id} 未找到",
                "agent_id": agent_id,
                "skill": skill_name
            }
        
        # 检查技能是否存在
        if not hasattr(agent, skill_name):
            return {
                "ok": False,
                "error": f"技能 {skill_name} 在智能体 {agent_id} 中不存在",
                "agent_id": agent_id,
                "skill": skill_name
            }
        
        try:
            # 执行技能
            skill_method = getattr(agent, skill_name)
            result = skill_method(**kwargs)
            
            return {
                "ok": True,
                "agent_id": agent_id,
                "skill": skill_name,
                "result": result,
                "timestamp": result.get('timestamp') if isinstance(result, dict) else None
            }
            
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "agent_id": agent_id,
                "skill": skill_name,
                "traceback": f"执行技能时发生错误: {e}"
            }
    
    def get_verification_summaries(self) -> Dict[str, Any]:
        """获取所有智能体的验证摘要"""
        summaries = {}
        
        for agent_id, agent in self.agents.items():
            if hasattr(agent, 'get_verification_summary'):
                summary = agent.get_verification_summary()
                if summary:
                    summaries[agent_id] = summary
        
        return {
            "ok": True,
            "timestamp": json.dumps({"iso": "2025-03-20T08:00:00.000Z"}),
            "summaries": summaries,
            "total_agents": len(summaries)
        }
    
    def generate_openclaw_config(self) -> Dict[str, Any]:
        """生成OpenCLAW兼容的配置"""
        config = {
            "version": "1.0.0",
            "project": self.config.get("project", "water_treatment_openclaw"),
            "agents": [],
            "tools": []
        }
        
        for agent_id, agent in self.agents.items():
            # 添加智能体配置
            agent_config = {
                "id": agent_id,
                "type": "specialist_agent",
                "implementation": f"app.agents.{agent_id}_agent.{agent.__class__.__name__}",
                "status": "active"
            }
            config["agents"].append(agent_config)
            
            # 添加工具定义
            tools = self.get_agent_tools(agent_id)
            if tools:
                config["tools"].append(tools)
        
        return config
    
    def save_openclaw_config(self, output_file: str = "config/openclaw_agents_config.json"):
        """保存OpenCLAW配置到文件"""
        config = self.generate_openclaw_config()
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"OpenCLAW配置已保存到: {output_file}")
        return config


# Flask API端点集成
def create_openclaw_endpoints(app, registry):
    """为Flask应用创建OpenCLAW API端点"""
    
    @app.route('/api/v1/openclaw/agents', methods=['GET'])
    def list_openclaw_agents():
        """列出所有可用的智能体"""
        agents = registry.list_agents()
        agent_details = []
        
        for agent_id in agents:
            tools = registry.get_agent_tools(agent_id)
            agent_details.append({
                "id": agent_id,
                "name": tools.get('name', agent_id),
                "description": tools.get('description', ''),
                "skills": [skill['name'] for skill in tools.get('skills', [])]
            })
        
        return {
            "ok": True,
            "data": {
                "agents": agent_details,
                "total": len(agents)
            }
        }
    
    @app.route('/api/v1/openclaw/execute', methods=['POST'])
    def execute_openclaw_skill():
        """执行智能体技能"""
        if not request.is_json:
            return jsonify({
                "ok": False,
                "error": "Content-Type必须为application/json"
            }), 400
        
        data = request.get_json()
        agent_id = data.get('agent_id')
        skill_name = data.get('skill_name')
        parameters = data.get('parameters', {})
        
        if not agent_id or not skill_name:
            return jsonify({
                "ok": False,
                "error": "缺少必要参数: agent_id 和 skill_name"
            }), 400
        
        result = registry.execute_skill(agent_id, skill_name, **parameters)
        
        return jsonify(result)
    
    @app.route('/api/v1/openclaw/verifications', methods=['GET'])
    def get_verifications():
        """获取所有智能体的验证摘要"""
        result = registry.get_verification_summaries()
        return jsonify(result)
    
    @app.route('/api/v1/openclaw/config', methods=['GET'])
    def get_openclaw_config():
        """获取OpenCLAW配置"""
        config = registry.generate_openclaw_config()
        return jsonify({"ok": True, "data": config})
    
    print("OpenCLAW API端点已注册")


# 使用示例
if __name__ == "__main__":
    # 创建注册表实例
    registry = OpenCLAWAgentRegistry()
    
    # 初始化智能体
    registry.initialize_agents()
    
    # 生成并保存配置
    config = registry.save_openclaw_config()
    
    print("=" * 50)
    print("OpenCLAW集成配置完成")
    print("=" * 50)
    
    # 列出所有智能体
    agents = registry.list_agents()
    print(f"已注册智能体: {agents}")
    
    # 演示技能执行
    print("\n演示技能执行:")
    
    # 执行进水工艺评估
    print("\n1. 执行进水工艺评估:")
    result = registry.execute_skill("inlet_process", "assess_flow_quality")
    print(f"结果: {result.get('ok')}")
    if result.get('ok') and 'result' in result:
        assessment = result['result']
        print(f"  流量评估: {assessment.get('assessment', {}).get('flow_ok')}")
    
    # 执行工段全流程优化
    print("\n2. 执行工段全流程优化:")
    result = registry.execute_skill("process_stage", "run_full_optimization")
    print(f"结果: {result.get('ok')}")
    if result.get('ok') and 'result' in result:
        opt = result['result']
        print(f"  优化状态: {opt.get('status', 'unknown')}")
    
    # 执行出水合规检查
    print("\n3. 执行出水合规检查:")
    result = registry.execute_skill("outlet_process", "check_compliance")
    print(f"结果: {result.get('ok')}")
    if result.get('ok') and 'result' in result:
        compliance = result['result']
        print(f"  合规分数: {compliance.get('summary', {}).get('compliance_score', 0):.1f}%")
    
    print("\n配置完成！智能体已准备好与OpenCLAW集成。")