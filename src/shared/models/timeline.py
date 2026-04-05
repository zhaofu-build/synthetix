"""
时间线数据结构

用于视频剪辑的时间线、轨道、片段数据模型
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class TimelineClip:
    """时间线片段"""
    id: str
    material_id: int
    material_name: str
    start: float  # 在时间线上的开始时间（秒）
    end: float    # 在时间线上的结束时间（秒）
    trim_start: float = 0.0  # 素材裁剪开始点
    trim_end: float = 0.0    # 素材裁剪结束点
    speed: float = 1.0       # 播放速度
    volume: float = 1.0      # 音量
    effects: List[Dict] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """片段时长"""
        return self.end - self.start

    @property
    def source_duration(self) -> float:
        """源素材使用的时长"""
        return (self.trim_end - self.trim_start) / self.speed

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "material_id": self.material_id,
            "material_name": self.material_name,
            "start": self.start,
            "end": self.end,
            "trim_start": self.trim_start,
            "trim_end": self.trim_end,
            "speed": self.speed,
            "volume": self.volume,
            "effects": self.effects
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TimelineClip":
        return cls(
            id=data["id"],
            material_id=data["material_id"],
            material_name=data["material_name"],
            start=data["start"],
            end=data["end"],
            trim_start=data.get("trim_start", 0.0),
            trim_end=data.get("trim_end", 0.0),
            speed=data.get("speed", 1.0),
            volume=data.get("volume", 1.0),
            effects=data.get("effects", [])
        )


@dataclass
class Track:
    """轨道"""
    id: str
    type: str  # video, audio, subtitle
    name: str
    clips: List[TimelineClip] = field(default_factory=list)
    muted: bool = False
    locked: bool = False

    def add_clip(self, clip: TimelineClip):
        """添加片段"""
        self.clips.append(clip)
        self._sort_clips()

    def remove_clip(self, clip_id: str):
        """移除片段"""
        self.clips = [c for c in self.clips if c.id != clip_id]

    def _sort_clips(self):
        """按开始时间排序"""
        self.clips.sort(key=lambda c: c.start)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "clips": [c.to_dict() for c in self.clips],
            "muted": self.muted,
            "locked": self.locked
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Track":
        return cls(
            id=data["id"],
            type=data["type"],
            name=data["name"],
            clips=[TimelineClip.from_dict(c) for c in data.get("clips", [])],
            muted=data.get("muted", False),
            locked=data.get("locked", False)
        )


@dataclass
class Transition:
    """转场效果"""
    id: str
    type: str  # cut, dissolve, wipe, fade
    position: float  # 转场发生的时间点
    duration: float = 0.5
    params: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "position": self.position,
            "duration": self.duration,
            "params": self.params
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Transition":
        return cls(
            id=data["id"],
            type=data["type"],
            position=data["position"],
            duration=data.get("duration", 0.5),
            params=data.get("params", {})
        )


@dataclass
class Timeline:
    """时间线"""
    id: str
    project_id: int
    video_track: Track = None
    audio_track: Track = None
    subtitle_track: Track = None
    transitions: List[Transition] = field(default_factory=list)
    duration: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if self.video_track is None:
            self.video_track = Track(
                id=f"{self.id}_video",
                type="video",
                name="视频轨道"
            )
        if self.audio_track is None:
            self.audio_track = Track(
                id=f"{self.id}_audio",
                type="audio",
                name="音频轨道"
            )
        if self.subtitle_track is None:
            self.subtitle_track = Track(
                id=f"{self.id}_subtitle",
                type="subtitle",
                name="字幕轨道"
            )

    def add_clip(self, clip: TimelineClip, track_type: str = "video"):
        """添加片段到指定轨道"""
        track = self._get_track(track_type)
        if track:
            track.add_clip(clip)
            self._update_duration()

    def _get_track(self, track_type: str) -> Optional[Track]:
        """获取指定类型的轨道"""
        if track_type == "video":
            return self.video_track
        elif track_type == "audio":
            return self.audio_track
        elif track_type == "subtitle":
            return self.subtitle_track
        return None

    def _update_duration(self):
        """更新总时长"""
        max_end = 0.0
        for track in [self.video_track, self.audio_track, self.subtitle_track]:
            if track and track.clips:
                track_max = max(c.end for c in track.clips)
                max_end = max(max_end, track_max)
        self.duration = max_end

    def add_transition(self, transition: Transition):
        """添加转场"""
        self.transitions.append(transition)
        self.transitions.sort(key=lambda t: t.position)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "duration": self.duration,
            "video_track": self.video_track.to_dict() if self.video_track else None,
            "audio_track": self.audio_track.to_dict() if self.audio_track else None,
            "subtitle_track": self.subtitle_track.to_dict() if self.subtitle_track else None,
            "transitions": [t.to_dict() for t in self.transitions],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict) -> "Timeline":
        timeline = cls(
            id=data["id"],
            project_id=data["project_id"],
            duration=data.get("duration", 0.0),
            transitions=[Transition.from_dict(t) for t in data.get("transitions", [])]
        )
        if data.get("video_track"):
            timeline.video_track = Track.from_dict(data["video_track"])
        if data.get("audio_track"):
            timeline.audio_track = Track.from_dict(data["audio_track"])
        if data.get("subtitle_track"):
            timeline.subtitle_track = Track.from_dict(data["subtitle_track"])
        return timeline


@dataclass
class ClipPlan:
    """剪辑方案"""
    project_id: int
    clips: List[Dict] = field(default_factory=list)
    transitions: List[Dict] = field(default_factory=list)
    audio: Dict = field(default_factory=dict)
    total_duration: float = 0.0
    style: str = "动感"
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        return {
            "project_id": self.project_id,
            "clips": self.clips,
            "transitions": self.transitions,
            "audio": self.audio,
            "total_duration": self.total_duration,
            "style": self.style,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict) -> "ClipPlan":
        return cls(
            project_id=data["project_id"],
            clips=data.get("clips", []),
            transitions=data.get("transitions", []),
            audio=data.get("audio", {}),
            total_duration=data.get("total_duration", 0.0),
            style=data.get("style", "动感")
        )


def generate_id() -> str:
    """生成唯一 ID"""
    import uuid
    return str(uuid.uuid4())[:8]
