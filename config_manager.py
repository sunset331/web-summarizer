"""
配置管理模块
统一管理所有API配置和系统设置
"""

import json
import os
from typing import Dict, Any

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        # 如果提供的是相对路径，转换为绝对路径
        if not os.path.isabs(config_file):
            # 获取当前脚本所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 获取项目根目录（util的上一级目录）
            project_root = os.path.dirname(current_dir)
            # 构建配置文件的绝对路径
            self.config_file = os.path.join(project_root, config_file)
        else:
            self.config_file = config_file
            
        print(f"[INFO] 配置文件路径: {self.config_file}")
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
        """
        try:
            if not os.path.exists(self.config_file):
                raise FileNotFoundError(f"配置文件 {self.config_file} 不存在")
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            print(f"[INFO] 成功加载配置文件: {self.config_file}")
            return config
            
        except Exception as e:
            print(f"[ERROR] 加载配置文件失败: {e}")
            # 返回默认配置
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "doubao": {
                "api_key": "",
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "model": "doubao-seed-1-6-250615",
                "timeout": 120,
                "max_tokens": 20000,
                "temperature": 0.2
            },
            "xunfei": {
                "appid": "",
                "secret": "",
                "base_url": "https://api.xfyun.cn",
                "timeout": 60
            },
            "system": {
                "max_retries": 3,
                "chunk_size": 2000,
                "default_encoding": "utf-8",
                "log_level": "INFO"
            },
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "bit_depth": 16,
                "format": "wav"
            }
        }
    
    def get_doubao_config(self) -> Dict[str, Any]:
        """获取豆包API配置"""
        return self.config.get("doubao", {})
    
    def get_xunfei_config(self) -> Dict[str, Any]:
        """获取讯飞API配置"""
        return self.config.get("xunfei", {})
    
    def get_system_config(self) -> Dict[str, Any]:
        """获取系统配置"""
        return self.config.get("system", {})
    
    def get_audio_config(self) -> Dict[str, Any]:
        """获取音频配置"""
        return self.config.get("audio", {})
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持点号分隔的多级键，如 "doubao.api_key"
            default: 默认值
            
        Returns:
            配置值
        """
        try:
            keys = key.split('.')
            value = self.config
            
            for k in keys:
                value = value[k]
            
            return value
        except (KeyError, TypeError):
            return default
    
    def reload(self) -> None:
        """重新加载配置文件"""
        self.config = self._load_config()
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        更新配置
        
        Args:
            updates: 要更新的配置字典
        """
        try:
            # 深度更新配置
            self._deep_update(self.config, updates)
            
            # 保存到文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            print(f"[INFO] 配置已更新并保存到: {self.config_file}")
            
        except Exception as e:
            print(f"[ERROR] 更新配置失败: {e}")
    
    def _deep_update(self, base_dict: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """深度更新字典"""
        for key, value in updates.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

# 全局配置管理器实例
config_manager = ConfigManager()

# 便捷函数
def get_doubao_config() -> Dict[str, Any]:
    """获取豆包API配置"""
    return config_manager.get_doubao_config()

def get_xunfei_config() -> Dict[str, Any]:
    """获取讯飞API配置"""
    return config_manager.get_xunfei_config()

def get_system_config() -> Dict[str, Any]:
    """获取系统配置"""
    return config_manager.get_system_config()

def get_audio_config() -> Dict[str, Any]:
    """获取音频配置"""
    return config_manager.get_audio_config()

def get_config(key: str, default: Any = None) -> Any:
    """获取配置值"""
    return config_manager.get(key, default)
