"""
扩展/插件系统

扩展通过 manifest.json 声明名称、入口、注入的系统提示词。
扩展可注册自定义工具到 tool_registry。
"""
import json
import logging
import sys
import importlib
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

EXTENSIONS_DIR = Path(__file__).parent.parent / "extensions"


@dataclass
class Extension:
    """扩展定义"""
    name: str
    version: str
    description: str
    entry: str  # Python 模块路径（如 extensions.subtitle_style.main）
    system_prompt: str = ""
    enabled: bool = True
    tools_registered: bool = False


_extensions: Dict[str, Extension] = {}


def load_extensions() -> List[Extension]:
    """扫描 extensions/ 目录，加载所有扩展"""
    global _extensions
    _extensions.clear()

    if not EXTENSIONS_DIR.is_dir():
        return list(_extensions.values())

    for ext_dir in EXTENSIONS_DIR.iterdir():
        if not ext_dir.is_dir():
            continue
        manifest_path = ext_dir / "manifest.json"
        if not manifest_path.is_file():
            continue

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            ext = Extension(
                name=data.get("name", ext_dir.name),
                version=data.get("version", "1.0.0"),
                description=data.get("description", ""),
                entry=data.get("entry", ""),
                system_prompt=data.get("system_prompt", ""),
                enabled=data.get("enabled", True),
            )
            _extensions[ext.name] = ext
            logger.info(f"加载扩展: {ext.name} v{ext.version}")

        except Exception as e:
            logger.warning(f"加载扩展失败 {ext_dir}: {e}")

    return list(_extensions.values())


def register_extension_tools():
    """注册所有已启用扩展的工具"""
    ext_parent = str(EXTENSIONS_DIR.parent)
    if ext_parent not in sys.path:
        sys.path.insert(0, ext_parent)
    for ext in _extensions.values():
        if not ext.enabled or ext.tools_registered or not ext.entry:
            continue
        try:
            module = importlib.import_module(ext.entry)
            if hasattr(module, 'register_tools'):
                module.register_tools()
                ext.tools_registered = True
                logger.info(f"扩展 {ext.name} 工具已注册")
        except Exception as e:
            logger.warning(f"扩展 {ext.name} 工具注册失败: {e}")


def get_extensions_prompt_section() -> str:
    """生成扩展注入的提示词段落"""
    if not _extensions:
        load_extensions()
    parts = []
    for ext in _extensions.values():
        if ext.enabled and ext.system_prompt:
            parts.append(f"### 扩展: {ext.name}\n{ext.system_prompt}")
    return "\n\n".join(parts) if parts else ""


def list_extensions() -> List[Dict[str, Any]]:
    """列出所有扩展"""
    if not _extensions:
        load_extensions()
    return [
        {"name": e.name, "version": e.version, "description": e.description, "enabled": e.enabled}
        for e in _extensions.values()
    ]


def toggle_extension(name: str, enabled: bool) -> bool:
    """启用/禁用扩展"""
    ext = _extensions.get(name)
    if not ext:
        return False
    ext.enabled = enabled
    return True
