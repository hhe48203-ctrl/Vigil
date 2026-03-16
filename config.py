# 统一配置加载：优先 config.yaml，缺省值 + .env 兜底
import os
from pathlib import Path

import yaml

CONFIG_FILE = Path(__file__).parent / "config.yaml"

# 所有配置项的默认值和说明
DEFAULTS = {
    "anthropic_api_key": {"default": "", "env": "ANTHROPIC_API_KEY", "required": True, "desc": "Anthropic API 密钥"},
    "discord_bot_token": {"default": "", "env": "DISCORD_BOT_TOKEN", "required": True, "desc": "Discord Bot Token"},
    "discord_channel_id": {"default": "", "env": "DISCORD_CHANNEL_ID", "required": True, "desc": "Discord 频道 ID"},
    "heartbeat_interval": {"default": 1800, "env": "HEARTBEAT_INTERVAL", "required": False, "desc": "心跳间隔（秒）"},
    "history_compress_threshold": {"default": 40, "env": "HISTORY_COMPRESS_THRESHOLD", "required": False, "desc": "历史压缩阈值"},
    "history_keep_recent": {"default": 20, "env": "HISTORY_KEEP_RECENT", "required": False, "desc": "压缩后保留最近消息数"},
    "tavily_api_key": {"default": "", "env": "TAVILY_API_KEY", "required": False, "desc": "Tavily 搜索 API 密钥"},
    "model": {"default": "claude-haiku-4-5-20251001", "env": "MODEL", "required": False, "desc": "默认模型"},
}

_config_cache: dict | None = None


def _load_yaml() -> dict:
    """读取 config.yaml，不存在则返回空 dict"""
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open() as f:
            data = yaml.safe_load(f) or {}
        return data
    return {}


def load_config() -> dict:
    """加载合并配置：config.yaml > 环境变量 > 默认值"""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    yaml_data = _load_yaml()
    config = {}

    for key, spec in DEFAULTS.items():
        # 优先级：config.yaml > 环境变量 > 默认值
        if key in yaml_data:
            config[key] = yaml_data[key]
        elif spec["env"] and os.getenv(spec["env"]):
            config[key] = os.getenv(spec["env"])
        else:
            config[key] = spec["default"]

    _config_cache = config
    return config


def get(key: str, fallback=None):
    """获取单个配置项"""
    config = load_config()
    return config.get(key, fallback)


def reload():
    """清除缓存，重新加载"""
    global _config_cache
    _config_cache = None
    return load_config()
