from typing import Literal, Optional
from dataclasses import dataclass, asdict
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
    content: str
    timestamp: str        # 什么时候确立为核心记忆的
    associated_actor: str # 和谁相关的类型的事情
    credibility: float    # 该情景的核心可信度
