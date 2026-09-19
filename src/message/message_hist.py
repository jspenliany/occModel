from typing import Sequence
# 🌟 导入所有的强类型参数
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam
)


class AvatarChatHistory:
    """
    数字人专属强类型对话历史管理器
    1. 动态隔离 System Prompt 与上下文历史。
    2. 严格对齐 OpenAI SDK 的 ChatCompletionMessageParam 联合类型。
    """

    def __init__(self, max_turns: int = 10):
        # 🌟 内部队列只存储用户输入和 AI 的助理回复（不存 system，因为 system 实时在变）
        self.history: list[ChatCompletionUserMessageParam | ChatCompletionAssistantMessageParam] = []
        self.max_turns = max_turns  # 限制历史轮数，防止 Token 爆表

    def add_user_message(self, content: str) -> None:
        """记录当前回合人类用户的输入"""
        self.history.append(
            ChatCompletionUserMessageParam(role="user", content=content)
        )
        self._truncate_history()

    def add_assistant_message(self, content: str) -> None:
        """记录当前回合大模型生成的助理回复"""
        self.history.append(
            ChatCompletionAssistantMessageParam(role="assistant", content=content)
        )
        self._truncate_history()

    def compile_api_messages(self, dynamic_system_prompt: str) -> list[ChatCompletionMessageParam]:
        """
        核心熔炼方法：将【当前最新计算的心理学System提示词】与【对话历史】实时合并
        返回完全符合 SDK 要求的 list[ChatCompletionMessageParam]
        """
        # 1. 动态创建最新的强类型 System 消息
        system_message = ChatCompletionSystemMessageParam(
            role="system",
            content=dynamic_system_prompt
        )

        # 2. 强类型拼接：[System] + [User1, Assistant1, User2...]
        # 显式声明其为标准联合类型的列表，彻底让 IDE 变绿
        compiled_payload: list[ChatCompletionMessageParam] = [system_message]
        compiled_payload.extend(self.history)

        return compiled_payload

    def _truncate_history(self) -> None:
        """滑动窗口裁剪历史，1 turn = 1 user + 1 assistant"""
        while len(self.history) > self.max_turns * 2:
            self.history.pop(0)  # 剔除最早的记忆
