from typing import Literal, cast

from src.models.memory.memory_node import ChatTurnNode
from src.utils.util_json import get_now_time
from dataclasses import asdict

class AvatarChatHistory:
    """
    数字人专属强类型对话历史管理器
    1. 动态隔离 System Prompt 与上下文历史。
    2. 严格对齐 OpenAI SDK 的 ChatCompletionMessageParam 联合类型。
    """

    def __init__(self, max_turns: int = 10):
        # 🌟 内部队列只存储用户输入和 AI 的助理回复（不存 system，因为 system 实时在变）
        self.history: list[ChatTurnNode] = []
        self.max_turns = max_turns  # 限制历史轮数，防止 Token 爆表

    def add_user_message(self, content: str, speaker="no init", credibility=1.0) -> None:
        """记录当前回合人类用户的输入"""
        self.history.append(
            ChatTurnNode(role="user", content=content, timestamp=get_now_time(), speaker=speaker, credibility=credibility)
        )
        self._truncate_history()

    def add_assistant_message(self, content: str, speaker="the machine", credibility=0.75) -> None:
        """记录当前回合大模型生成的助理回复"""
        self.history.append(
            ChatTurnNode(role="assistant", content=content, timestamp=get_now_time(), speaker=speaker, credibility=credibility)
        )
        self._truncate_history()

    def _truncate_history(self) -> None:
        """滑动窗口裁剪历史，1 turn = 1 user + 1 assistant"""
        while len(self.history) > self.max_turns * 2:
            self.history.pop(0)  # 剔除最早的记忆

    def export_history(self) -> list[dict]:
        """
        Flattens the ChatTurnNode objects into a list of pure dictionaries.
        Ensures perfect, crash-free json.dump compatibility.
        """
        # If ChatTurnNode is a standard class, use vars(node) or node.to_dict()
        # If ChatTurnNode is a @dataclass, asdict(node) is the most bulletproof approach
        try:
            return [asdict(node) for node in self.history]
        except TypeError:
            # Fallback if ChatTurnNode is a plain python class rather than a dataclass
            return [
                {
                    "role": node.role,
                    "content": node.content,
                    "timestamp": str(node.timestamp),  # Convert datetime/ZoneInfo objects to safe string
                    "speaker": node.speaker,
                    "credibility": node.credibility
                }
                for node in self.history
            ]

    def load_history(self, history_data: list[dict]) -> None:
        """
        Hydrates incoming flat raw JSON dictionaries back into
        strongly-typed ChatTurnNode objects to restore immediate short-term memory.
        """
        if not history_data:
            self.history = []
            return

        self.history = [
            ChatTurnNode(
                role=cast(Literal["user", "assistant"], data.get("role", "user")),
                content=data.get("content", ""),
                timestamp=data.get("timestamp"),  # Keep as string or parse back via datetime depending on core rules
                speaker=data.get("speaker", "unknown"),
                credibility=data.get("credibility", 1.0)
            )
            for data in history_data
        ]