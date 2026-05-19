import json
import os
from copy import deepcopy
from workspace_manager import get_config_file_path

# Dynamic config file path based on environment
def _get_config_file():
    return get_config_file_path()

# Default configuration
DEFAULT_CONFIG = {
    "llm": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o",
        "temperature": 0.1,
        "stream": True,
        "timeout": 600,
        "read_timeout": 120
    },
    "llm_presets": {},
    "embedding": {
        "base_url": "https://api.siliconflow.cn/v1/embeddings",
        "api_key": "",
        "model_name": "Pro/BAAI/bge-m3",
        "batch_size": 64
    }
}

LLM_CONFIG_KEYS = ("base_url", "api_key", "model", "temperature", "stream", "timeout", "read_timeout")

def load_config():
    config_file = _get_config_file()
    if not os.path.exists(config_file):
        save_config(DEFAULT_CONFIG)
        return deepcopy(DEFAULT_CONFIG)
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Integrity check for backward compatibility
            if "llm" not in data:
                data["llm"] = deepcopy(DEFAULT_CONFIG["llm"])
            for key, value in DEFAULT_CONFIG["llm"].items():
                if key not in data["llm"]:
                    data["llm"][key] = value
            if "llm_presets" not in data or not isinstance(data["llm_presets"], dict):
                data["llm_presets"] = {}
            if "embedding" not in data:
                data["embedding"] = deepcopy(DEFAULT_CONFIG["embedding"])
            if "api_key" not in data["embedding"]:
                data["embedding"]["api_key"] = ""
            return data
    except:
        return deepcopy(DEFAULT_CONFIG)

def save_config(config_data):
    config_file = _get_config_file()
    # Ensure directory exists
    config_dir = os.path.dirname(config_file)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

def get_llm_presets():
    config = load_config()
    return config.get("llm_presets", {})

def normalize_llm_config(llm_config):
    normalized = deepcopy(DEFAULT_CONFIG["llm"])
    for key in LLM_CONFIG_KEYS:
        if key in llm_config:
            normalized[key] = llm_config[key]
    return normalized

def save_llm_preset(name, llm_config):
    clean_name = str(name or "").strip()
    if not clean_name:
        return False, "Preset name is empty"
    config = load_config()
    config.setdefault("llm_presets", {})
    config["llm_presets"][clean_name] = normalize_llm_config(llm_config)
    save_config(config)
    return True, f"Saved preset: {clean_name}"

def load_llm_preset(name):
    config = load_config()
    preset = config.get("llm_presets", {}).get(name)
    if not preset:
        return False, f"Preset not found: {name}"
    config["llm"].update(normalize_llm_config(preset))
    save_config(config)
    return True, f"Loaded preset: {name}"

def delete_llm_preset(name):
    config = load_config()
    presets = config.setdefault("llm_presets", {})
    if name not in presets:
        return False, f"Preset not found: {name}"
    del presets[name]
    save_config(config)
    return True, f"Deleted preset: {name}"
