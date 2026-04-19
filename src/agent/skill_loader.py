"""
Skills 技能加载器

自动扫描 skills/ 目录下的 .md 文件，加载技能定义。
技能会注入到 Agent 系统提示词中，让 LLM 知道有哪些可用技能。

Markdown 格式：
  # 技能名称（必须）
  描述文本（第一段非空非标题文本）
  **所需工具**: tool1, tool2（可选）
  ## 执行流程（后续内容为 prompt）
"""
import re
import logging
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent / "skills"


@dataclass
class Skill:
    name: str
    description: str
    tools: List[str]
    prompt: str


_skills: Dict[str, Skill] = {}


def _parse_md(text: str) -> Skill:
    """解析 Markdown 格式的技能文件"""
    lines = text.split('\n')

    # 第一行 # 标题作为名称
    name = ""
    for line in lines:
        if line.startswith('# '):
            name = line[2:].strip()
            break

    # 提取所需工具
    tools: List[str] = []
    for line in lines:
        m = re.match(r'\*\*所需工具\*\*\s*[:：]\s*(.+)', line.strip())
        if m:
            tools = [t.strip() for t in m.group(1).split(',') if t.strip()]
            break

    # 找到第一个 ## 标题，其后续内容作为 prompt
    prompt_lines: List[str] = []
    in_prompt = False
    for line in lines:
        if re.match(r'^##\s', line):
            in_prompt = True
            continue
        if in_prompt:
            prompt_lines.append(line)
    prompt = '\n'.join(prompt_lines).strip()

    # 描述：第一个非空、非标题、非工具声明的行（在 ## 之前）
    description = ""
    for line in lines:
        s = line.strip()
        if not s or s.startswith('#') or s.startswith('**所需工具'):
            continue
        if s.startswith('##'):
            break
        description = s
        break

    return Skill(name=name, description=description, tools=tools, prompt=prompt)


def load_skills() -> Dict[str, Skill]:
    """扫描 skills/ 目录，加载所有 .md 技能文件"""
    global _skills
    _skills.clear()

    if not SKILLS_DIR.is_dir():
        logger.info("skills 目录不存在，跳过技能加载")
        return _skills

    for md_file in SKILLS_DIR.glob("*.md"):
        try:
            text = md_file.read_text(encoding='utf-8')
            skill = _parse_md(text)
            if not skill.name:
                logger.warning(f"技能文件缺少标题: {md_file}")
                continue
            _skills[skill.name] = skill
            logger.info(f"加载技能: {skill.name}")
        except Exception as e:
            logger.warning(f"加载技能文件失败 {md_file}: {e}")

    return _skills


def get_skill(name: str) -> Skill:
    if not _skills:
        load_skills()
    return _skills.get(name)


def list_skills() -> List[Skill]:
    if not _skills:
        load_skills()
    return list(_skills.values())


def get_skills_prompt_section() -> str:
    """生成注入到系统提示词中的技能描述段落"""
    if not _skills:
        load_skills()
    if not _skills:
        return ""

    parts = ["## 可用技能", ""]
    for skill in _skills.values():
        tools_str = ", ".join(skill.tools) if skill.tools else "无"
        parts.append(f"### {skill.name}")
        parts.append(f"描述: {skill.description}")
        parts.append(f"所需工具: {tools_str}")
        if skill.prompt:
            parts.append(f"执行流程:\n{skill.prompt}")
        parts.append("")

    return "\n".join(parts)


def get_skill_names() -> List[str]:
    if not _skills:
        load_skills()
    return list(_skills.keys())
