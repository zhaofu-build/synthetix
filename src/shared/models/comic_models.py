"""
漫剧数据模型 — Pydantic 请求/响应模型
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CharacterDef(BaseModel):
    """角色定义"""
    id: Optional[str] = None
    name: str = Field(..., description="角色名称")
    appearance: Optional[str] = Field(default=None, description="外貌描述（发色/发型/眼色/服装等）")
    gender: Optional[str] = Field(default=None, description="性别")
    personality: Optional[str] = Field(default=None, description="性格特点")
    voice_description: Optional[str] = Field(default=None, description="音色描述")
    reference_image: Optional[str] = Field(default=None, description="参考图路径")
    voice_id: Optional[str] = Field(default=None, description="TTS speaker ID")


class StoryboardPanel(BaseModel):
    """分镜面板"""
    sequence: int = Field(default=0, description="分镜序号")
    scene_description: str = Field(..., description="场景视觉描述（用于AI图片生成）")
    background_description: Optional[str] = Field(default=None, description="背景描述")
    characters: Optional[List[str]] = Field(default=None, description="出镜角色名称列表")
    dialogues: Optional[List[Dict[str, str]]] = Field(default=None, description="对白 [{character_id, text, emotion}]")
    narration: Optional[str] = Field(default=None, description="旁白文本")
    emotion: str = Field(default="neutral", description="情绪: happy/sad/angry/neutral/tense/romantic")
    duration: float = Field(default=3.0, description="持续秒数")
    transition: str = Field(default="cut", description="转场: cut/fade/dissolve/wipe/zoom")
    camera: Optional[str] = Field(default=None, description="镜头: 特写/近景/中景/全景/远景")
    generated_image_path: Optional[str] = Field(default=None, description="生成的图片路径")
    generated_video_path: Optional[str] = Field(default=None, description="生成的视频路径")
    generated_audio_paths: Optional[List[str]] = Field(default=None, description="生成的语音路径列表")


class ComicScript(BaseModel):
    """漫剧脚本"""
    title: Optional[str] = None
    synopsis: Optional[str] = None
    genre: Optional[str] = None
    scenes: Optional[List[StoryboardPanel]] = None


# ==================== API 请求模型 ====================

class CreateComicProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    genre: Optional[str] = None


class UpdateComicProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    script_data: Optional[Dict[str, Any]] = None
    characters: Optional[List[Dict[str, Any]]] = None
    panels: Optional[List[Dict[str, Any]]] = None
    audio_config: Optional[Dict[str, Any]] = None
    bgm_config: Optional[Dict[str, Any]] = None
    current_step: Optional[int] = None
    status: Optional[str] = None


class GenerateScriptRequest(BaseModel):
    description: str = Field(..., description="故事设定/大纲")
    genre: Optional[str] = Field(default="drama", description="类型")
    num_panels: int = Field(default=10, ge=3, le=50, description="分镜数量")
    characters: Optional[List[Dict[str, Any]]] = None


class GeneratePanelImageRequest(BaseModel):
    panel_index: int = Field(..., ge=0, description="分镜索引")
    scene_description: Optional[str] = None


class GeneratePanelAudioRequest(BaseModel):
    panel_index: int = Field(..., ge=0, description="分镜索引")
    text: Optional[str] = None
    voice_id: Optional[str] = None
