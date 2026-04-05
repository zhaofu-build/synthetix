"""
剪辑规划服务

根据用户描述和素材生成剪辑方案
"""
import json
import logging
from typing import List, Dict, Any, Optional

from src.application.services.llm_adapter import generate_response
from src.shared.models.timeline import ClipPlan, generate_id
from src.shared.utils import string_util

logger = logging.getLogger(__name__)


class ClipPlanner:
    """剪辑规划器"""

    def generate_plan(
        self,
        description: str,
        materials: List[Dict],
        duration: float = 30.0,
        style: str = "动感"
    ) -> ClipPlan:
        """
        生成剪辑方案

        Args:
            description: 用户描述
            materials: 可用素材列表
            duration: 目标时长
            style: 风格偏好

        Returns:
            ClipPlan: 剪辑方案
        """
        # 构建 prompt
        prompt = self._build_prompt(description, materials, duration, style)

        # 调用 LLM
        response = generate_response([{"role": "user", "content": prompt}])

        # 解析响应
        plan_data = self._parse_response(response)

        # 校验并修正总时长
        plan_data = self._enforce_duration(plan_data, duration)

        return ClipPlan(
            project_id=0,  # 临时，后续更新
            clips=plan_data.get("clips", []),
            transitions=plan_data.get("transitions", []),
            audio=plan_data.get("audio", {}),
            total_duration=plan_data.get("total_duration", duration),
            style=style
        )

    def _build_prompt(
        self,
        description: str,
        materials: List[Dict],
        duration: float,
        style: str
    ) -> str:
        """构建提示词"""
        materials_str = "\n".join([
            f"- ID: {m.get('id')}, 名称: {m.get('video_name', m.get('name'))}, "
            f"时长: {m.get('duration', m.get('duration_hms', '未知'))}, "
            f"描述: {m.get('description', '无')}"
            for m in materials[:20]  # 限制数量
        ])

        return f"""你是专业视频剪辑师，请根据以下信息规划剪辑方案。

用户需求：{description}

可用素材：
{materials_str}

目标时长：{duration}秒（所有片段的 end_time - start_time 之和必须严格等于{duration}秒）
风格偏好：{style}

返回 JSON 格式的剪辑方案（不要包含 ```json 标记）：
{{
    "clips": [
        {{
            "material_id": 素材ID,
            "material_name": "文件名",
            "start_time": "00:00:00",
            "end_time": "00:00:05",
            "purpose": "这段用于展示什么内容"
        }}
    ],
    "transitions": [
        {{"type": "dissolve", "duration": 0.5}}
    ],
    "audio": {{
        "background_music": "音乐风格建议",
        "volume": 0.3
    }},
    "total_duration": {duration}
}}

规划原则：
1. 每个片段的 end_time - start_time 就是该片段在最终视频中的时长
2. 所有片段时长之和必须等于目标时长 {duration} 秒，不能多也不能少
3. 单个片段建议 3-10 秒
4. 转场要与内容情感匹配
5. 素材选择要与用户需求呼应
6. start_time 和 end_time 是素材内的裁剪时间点，不要超过素材本身的时长
"""

    def _enforce_duration(self, plan_data: Dict, target_duration: float) -> Dict:
        """校验并修正片段总时长，确保等于目标时长"""
        clips = plan_data.get("clips", [])
        if not clips:
            return plan_data

        # 计算每个片段的实际时长和总时长
        clip_durations = []
        for clip in clips:
            start = self._parse_time_str(clip.get("start_time", "00:00:00"))
            end = self._parse_time_str(clip.get("end_time", "00:00:10"))
            clip_durations.append(end - start)

        actual_total = sum(clip_durations)
        if actual_total <= 0:
            return plan_data

        # 按比例缩放每个片段的时长
        scale = target_duration / actual_total
        for i, clip in enumerate(clips):
            original_start = self._parse_time_str(clip.get("start_time", "00:00:00"))
            new_duration = clip_durations[i] * scale
            new_end = original_start + new_duration
            clip["end_time"] = self._seconds_to_time_str(new_end)

        plan_data["total_duration"] = target_duration
        logger.info(f"时长校验: 目标={target_duration}s, 原始={actual_total:.1f}s, 缩放比例={scale:.3f}")
        return plan_data

    def _parse_time_str(self, time_str: str) -> float:
        """解析 HH:MM:SS 时间字符串为秒数"""
        parts = str(time_str).split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(time_str)

    def _seconds_to_time_str(self, seconds: float) -> str:
        """秒数转 HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"

    def _parse_response(self, response: str) -> Dict:
        """解析 LLM 响应"""
        try:
            # 清理响应
            text = response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            if text.endswith("```"):
                text = text[:-3]

            # 移除 think 标签
            text = string_util.remove_think_tags(text)

            return json.loads(text)

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}, 原始响应: {response[:500]}")
            return {"clips": [], "transitions": [], "audio": {}}

    def optimize_pacing(
        self,
        clips: List[Dict],
        style: str = "dynamic"
    ) -> List[Dict]:
        """
        优化剪辑节奏

        Args:
            clips: 片段列表
            style: 风格 (dynamic/cinematic/documentary)

        Returns:
            优化后的片段列表
        """
        style_guide = {
            "dynamic": "快节奏，片段短促有力，适合短视频",
            "cinematic": "电影感，节奏舒缓，留有呼吸空间",
            "documentary": "纪录片风格，稳重，信息密集"
        }

        prompt = f"""优化以下剪辑片段的节奏，使其更加{style_guide.get(style, style)}。

当前片段：
{json.dumps(clips, ensure_ascii=False, indent=2)}

返回优化后的 JSON 数组，可以：
1. 调整片段顺序
2. 调整开始/结束时间
3. 添加或删除片段
"""

        try:
            response = generate_response([{"role": "user", "content": prompt}])
            return json.loads(response)
        except Exception as e:
            logger.error(f"优化节奏失败: {e}")
            return clips

    def suggest_music(
        self,
        video_mood: str,
        duration: float
    ) -> Dict:
        """
        推荐背景音乐

        Args:
            video_mood: 视频情感基调
            duration: 视频时长

        Returns:
            音乐推荐
        """
        prompt = f"""根据视频情感基调推荐背景音乐。

视频情感: {video_mood}
视频时长: {duration}秒

返回 JSON:
{{
    "genre": "音乐类型",
    "tempo": "节奏(bpm)",
    "mood": "情感描述",
    "search_keywords": ["搜索关键词"],
    "volume_curve": [
        {{"time": 0, "volume": 0.3}},
        {{"time": 10, "volume": 0.8}}
    ]
}}
"""
        try:
            response = generate_response([{"role": "user", "content": prompt}])
            return json.loads(response)
        except Exception as e:
            logger.error(f"推荐音乐失败: {e}")
            return {"genre": "轻音乐", "tempo": "120", "search_keywords": ["背景音乐"]}
