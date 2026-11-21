from typing import Literal, List, Dict, Any
from dataclasses import dataclass, asdict, field, fields
from src.utils.util_json import get_now_time


@dataclass
class ChatTurnNode:
    role: Literal["user", "assistant"]
    content: str
    timestamp: str          # 刚性时间戳
    speaker: str            # 说话人标识
    credibility: float = 1.0 # 本次回话内容的初始可信度

@dataclass
class CoreMemoryNode:
    """
    数字生命精细化核心记忆节点：
    承载带本体类型（经历/目击/传闻/梦境）、可信度权重与视角标签的客观事实。
    """
    fact_summary: str
    memory_type: str = "episodic_experiential"  # episodic_experiential | episodic_observed | semantic_hearsay | subconscious_dream
    credibility: float = 1.0                    # 可信度 [0.0, 1.0]: 亲历/目击 1.0, 传闻 0.4~0.7, 梦境 0.1
    perspective_focus: str = "first_person"     # first_person | user_centric | third_party
    involved_entities: List[str] = field(default_factory=list)
    time_indicator: str = "past"                # past | implied_current | future_planned
    mention_count: int = 1
    created_at: str = ""
    last_updated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CoreMemoryNode':
        """安全反序列化：自动过滤未定义的旧版冗余字段，缺失字段使用默认值兜底"""
        if isinstance(data, cls):
            return data
        valid_keys = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        # 兼容旧存档可能使用的 'content' 或 'summary' 字段名
        if "fact_summary" not in filtered_data:
            filtered_data["fact_summary"] = data.get("content") or data.get("summary", "")
        return cls(**filtered_data)

    def get(self, key: str, default: Any = None) -> Any:
        """提供字典风格的 .get() 兼容访问，防止调用方误当 dict 处理时报错"""
        return getattr(self, key, default)