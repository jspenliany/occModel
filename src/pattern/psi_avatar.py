from src.models.psi.bridge import PSI3DGlassBridge
from src.logger_singleton import logger
from src.prompts.prompt_renderer import LLMPromptRenderer
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam
)
from dataclasses import asdict
from src.message.message_hist import AvatarChatHistory
from src.models.memory.memory_node import CoreMemoryNode


class PsiAvatar:
    """封装 PSI 引擎与 Prompt 渲染器，对外暴露统一的生命周期接口"""

    def __init__(self, character_name: str, mbti: str, profession: str, lore_factory, trait_factory):
        self.character_name = character_name
        self.profession = profession

        # 1. 内部组合 PSI 核心与渲染器
        self.engine = PSI3DGlassBridge(mbti, profession)
        self.renderer = LLMPromptRenderer(
            character_name=character_name,
            profession=profession,
            lore_factory=lore_factory,
        )
        self.trait_factory = trait_factory
        self.trait_list = []
        self.core_memories: list[CoreMemoryNode] = []
        self.message_history = AvatarChatHistory()

    def get_reflect_payload(self, context: str, user_input: str) -> list:
        """生成用于让大模型评估情感冲击（OCC Delta）的请求 Payload"""
        current_state = self.engine.get_current_avatar_state()
        reflect_prompt = self.renderer.render_reflect_prompt(current_state)
        logger.debug(f"get_reflect_payload  reflect_prompt: {reflect_prompt}")
        return [
            ChatCompletionSystemMessageParam(role="system", content=reflect_prompt),
            ChatCompletionUserMessageParam(
                role="user",
                content=f"<context>{context}</context>\n<user_input>{user_input}</user_input>"
            ),
        ]

    def get_trait_payload(self, context: str, user_input: str) -> list:
        """生成用于让大模型评估虚拟人特质的请求 Payload"""
        trait_prompt = self.renderer.render_trait_prompt()
        logger.debug(f"get_reflect_payload  reflect_prompt: {trait_prompt}")
        return [
            ChatCompletionSystemMessageParam(role="system", content=trait_prompt),
            ChatCompletionUserMessageParam(
                role="user",
                content=f"<context>{context}</context>\n<user_input>{user_input}</user_input>"
            ),
        ]

    def apply_appraisal_and_tick(self, appraisal_data: dict):
        """内化刺激并推进心理时钟"""
        old_state = self.engine.get_current_avatar_state()
        self.engine.receive_user_stimulus(appraisal_data)
        self.engine.update_system_clock()
        new_state = self.engine.get_current_avatar_state()

        logger.debug(
            f"[{self.character_name} ({self.engine.p_layer.mbti})] OCC State Changed:\nBefore: {old_state}\nAfter: {new_state}")

    def get_common_chat_payload(self, context: str, user_input: str) -> list:
        """基于内化后的新状态，生成用于最终对话回复的 Prompt Payload"""
        current_state = self.engine.get_current_avatar_state()
        system_prompt = self.renderer.render_system_prompt(current_state, self.trait_list)
        logger.debug(f"get_response_payload system_prompt: {system_prompt}")
        self.message_history.add_user_message(user_input)

        return [
            ChatCompletionSystemMessageParam(
                role="system",
                content=f"{system_prompt}\n\n⚠️ CRITICAL OUTPUT CONSTRAINT:\n- Keep your response extremely brief, casual, and punchy.\n- Do NOT exceed 200 words under any circumstances"
            ),
            ChatCompletionUserMessageParam(
                role="user",
                content=f"<context>{context}</context>\n<user_input>{user_input}</user_input>"
            ),
        ]

    def get_charactor_name(self) -> str:
        return self.character_name
    def get_profession(self) -> str:
        return self.profession

    def append_new_trait(self, trait_text: str) -> str:
        message_list = self.get_trait_payload("", trait_text)
        if self.trait_factory is None:
            logger.debug(f"append_new_trait message: {trait_text}")
            return trait_text

        normalized_node = self.trait_factory.normalize_new_chunk(message_list)
        if isinstance(normalized_node.get("normalized_params"), list):
            self.trait_list.extend(normalized_node["normalized_params"])
        else:
            self.trait_list.append(normalized_node["normalized_params"])

        logger.info(f"{self.character_name} 当前特质库总数: {len(self.trait_list)}")
        return "success"

    def export_avatar_state(self) -> dict:
        """将当前智能体的所有运行时状态导出为可持久化的字典"""
        # 1. 获取 PSI 核心引擎的实时扁平状态
        current_psi_state = self.engine.get_current_avatar_state()
        engine_snapshot = self.engine.to_dict()

        # 2. 组装完整的持久化结构
        archive_data = {
            "metadata": {
                "character_name": self.character_name,
                "profession": self.profession,
                "mbti": self.engine.p_layer.mbti,
                "ocean_dna": self.engine.p_layer.ocean
            },
            "psi_live_state": engine_snapshot,
            "trait_memory_bank": self.trait_list,  # 持久化特质库
            "core_memory_bank": [asdict(m) for m in self.core_memories],   # 核心记忆库
            "chat_history": self.message_history.export_history() if hasattr(self.message_history,
                                                                             'export_history') else []
        }
        logger.info(f"Avatar [{self.character_name}] state successfully serialized.")
        return archive_data

    def load_avatar_state(self, archive_data: dict):
        """
        从持久化字典中反序列化，完美恢复元数据、深层 PSI 心理状态、特质库、核心记忆与会话历史
        """
        try:
            # 1. 恢复元数据层身份属性（防止冷启动实例化后属性未同步）
            metadata = archive_data.get("metadata", {})
            self.character_name = metadata.get("character_name", self.character_name)
            self.profession = metadata.get("profession", self.profession)

            # 提取元数据中的基因锚点（MBTI & OCEAN），便于引擎强制对齐
            mbti = metadata.get("mbti", "UNKNOWN")
            ocean_dna = metadata.get("ocean_dna", {})

            # 2. 强行灌入来自 engine.to_dict() 的全量运行时图谱变量
            # 此时的 live_state 包含更深层的未舍入浮点数及 counters / flags 快照
            live_state = archive_data.get("psi_live_state", {})

            # 优先使用强同步接口，将元数据设定与运行时状态树一同揉碎灌入底层各个子 Layer
            if hasattr(self.engine, "force_sync_state"):
                # 组装强同步 payload，确保底层能同步恢复状态图谱与计数器
                full_sync_payload = {
                    "mbti": mbti,
                    "ocean_dna": ocean_dna,
                    **live_state
                }
                self.engine.force_sync_state(full_sync_payload)
            else:
                # 兜底隐式覆写：若底层没有提供强同步 broker，则手动向下水管道属性直接灌入
                logger.warning(
                    "PSI Engine lacks direct force_sync_state method. Attempting regular property hydration.")
                # 恢复基础性格特征
                if hasattr(self.engine, 'p_layer'):
                    self.engine.p_layer.mbti = mbti
                    self.engine.p_layer.ocean = ocean_dna

                # 恢复隐藏标志位与演进计数器（依据底层 bridge 的设计决定）
                if "anger_habit_counter" in live_state:
                    self.engine.anger_habit_counter = live_state["anger_habit_counter"]
                if "in_hardship_flag" in live_state:
                    self.engine.in_hardship_flag = live_state["in_hardship_flag"]

            # 3. 恢复静态特质知识库（已经是纯 dict 列表，安全）
            self.trait_list = archive_data.get("trait_memory_bank", [])

            # 4. 恢复不可磨灭的强类型核心记忆库（通过解包实例化为 CoreMemoryNode 类对象）
            raw_core_mems = archive_data.get("core_memory_bank", [])
            self.core_memories = [CoreMemoryNode(**m) for m in raw_core_mems]

            # 5. 恢复短期近景历史对话会话存根（调用上一轮修复的强类型滑动窗口反序列化器）
            if hasattr(self.message_history, 'load_history') and "chat_history" in archive_data:
                self.message_history.load_history(archive_data["chat_history"])

            logger.info(f"Avatar [{self.character_name}] state and personality metadata successfully reloaded.")
        except Exception as e:
            logger.error(f"Critical error while loading avatar state for {self.character_name}: {e}")
            raise e
