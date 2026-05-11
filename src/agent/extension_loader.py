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
    mode: str = "all"  # video / comic / all
    level: str = "user"  # system / user（系统级不可编辑/禁用/删除）
    pipeline: dict = None  # 流水线模板定义（Phase 2）


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
                mode=data.get("mode", "all"),
                level=data.get("level", "user"),
                pipeline=data.get("pipeline"),
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


def get_extensions_prompt_section(current_mode: str = "video", active_extensions: list = None) -> str:
    """生成扩展注入的提示词段落。

    - level="system" 的扩展始终注入（常驻）
    - level="user" 的扩展仅在 active_extensions 列表中时注入（按需）
    - 按 mode 过滤
    """
    if not _extensions:
        load_extensions()
    active_set = set(active_extensions or [])
    parts = []
    for ext in _extensions.values():
        if not ext.enabled or not ext.system_prompt:
            continue
        if ext.mode != "all" and ext.mode != current_mode:
            continue
        # system 级常驻注入，user 级按需注入
        if ext.level == "system" or ext.name in active_set:
            parts.append(f"### 扩展: {ext.name}\n{ext.system_prompt}")
    return "\n\n".join(parts) if parts else ""


def list_extensions() -> List[Dict[str, Any]]:
    """列出所有扩展"""
    if not _extensions:
        load_extensions()
    return [
        {"name": e.name, "version": e.version, "description": e.description,
         "enabled": e.enabled, "system_prompt": e.system_prompt, "mode": e.mode,
         "level": e.level}
        for e in _extensions.values()
    ]


def get_extension_tools(extension_name: str) -> set:
    """获取扩展所需的工具名称集合（从 pipeline.steps 和 required_tools 提取）"""
    if not _extensions:
        load_extensions()
    ext = _extensions.get(extension_name)
    if not ext or not ext.pipeline:
        return set()
    tools = set()
    # 从 pipeline.steps 提取工具名
    for step in ext.pipeline.get("steps", []):
        tool_name = step.get("tool")
        if tool_name:
            tools.add(tool_name)
    # 从 required_tools 提取（显式声明）
    for name in ext.pipeline.get("required_tools", []):
        tools.add(name)
    return tools


def toggle_extension(name: str, enabled: bool) -> bool:
    """启用/禁用扩展（持久化到 manifest.json）"""
    ext = _extensions.get(name)
    if not ext:
        return False
    if ext.level == "system":
        logger.warning(f"系统级扩展 {name} 不可切换状态")
        return False
    ext.enabled = enabled
    # 写回 manifest.json
    manifest_path = EXTENSIONS_DIR / name / "manifest.json"
    if manifest_path.is_file():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data["enabled"] = enabled
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"持久化扩展状态失败: {e}")
    return True


def create_extension(name: str, description: str, system_prompt: str, mode: str = "all") -> Dict[str, Any]:
    """创建新扩展"""
    import shutil
    ext_dir = EXTENSIONS_DIR / name
    if ext_dir.exists():
        return {"success": False, "error": f"扩展 {name} 已存在"}

    ext_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "version": "1.0.0",
        "description": description,
        "entry": "",
        "system_prompt": system_prompt,
        "enabled": True,
        "mode": mode,
    }
    manifest_path = ext_dir / "manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    ext = Extension(
        name=name,
        version="1.0.0",
        description=description,
        entry="",
        system_prompt=system_prompt,
        enabled=True,
        mode=mode,
    )
    _extensions[name] = ext
    logger.info(f"创建扩展: {name}")
    return {"success": True, "name": name, "description": description}


def update_extension(name: str, description: str = None, system_prompt: str = None, mode: str = None) -> bool:
    """更新扩展的描述、提示词和模式"""
    ext = _extensions.get(name)
    if not ext:
        return False
    if ext.level == "system":
        logger.warning(f"系统级扩展 {name} 不可编辑")
        return False

    if description is not None:
        ext.description = description
    if system_prompt is not None:
        ext.system_prompt = system_prompt
    if mode is not None:
        ext.mode = mode

    # 持久化到 manifest.json
    manifest_path = EXTENSIONS_DIR / name / "manifest.json"
    if manifest_path.is_file():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if description is not None:
                data["description"] = description
            if system_prompt is not None:
                data["system_prompt"] = system_prompt
            if mode is not None:
                data["mode"] = mode
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"持久化扩展更新失败: {e}")
    return True


def delete_extension(name: str) -> bool:
    """删除扩展"""
    import shutil
    ext = _extensions.get(name)
    if not ext:
        return False
    if ext.level == "system":
        logger.warning(f"系统级扩展 {name} 不可删除")
        return False

    ext_dir = EXTENSIONS_DIR / name
    if ext_dir.is_dir():
        shutil.rmtree(ext_dir, ignore_errors=True)

    del _extensions[name]
    logger.info(f"删除扩展: {name}")
    return True


def list_pipelines(current_mode: str = "video") -> List[Dict[str, Any]]:
    """列出所有启用的流水线模板，按 mode 过滤"""
    if not _extensions:
        load_extensions()
    pipelines = []
    for ext in _extensions.values():
        if ext.enabled and ext.pipeline:
            if ext.mode == "all" or ext.mode == current_mode:
                pipelines.append({
                    "name": ext.name,
                    "description": ext.description,
                    "version": ext.version,
                    "mode": ext.mode,
                    **ext.pipeline,
                })
    return pipelines
