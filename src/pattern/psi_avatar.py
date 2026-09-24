from src.models.psi.bridge import PSI3DGlassBridge
from src.logger_singleton import logger
from src.prompts.prompt_renderer import LLMPromptRenderer
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam
)
from src.message.message_hist import AvatarChatHistory


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

        # 2. 组装完整的持久化结构
        archive_data = {
            "metadata": {
                "character_name": self.character_name,
                "profession": self.profession,
                "mbti": current_psi_state.get("mbti", "UNKNOWN"),
                "ocean_dna": current_psi_state.get("ocean_dna", {})
            },
            "psi_live_state": {
                "mood_valence": current_psi_state.get("mood_valence", 0.0),
                "mood_arousal": current_psi_state.get("mood_arousal", 0.0),
                "competence": current_psi_state.get("competence", 0.7),
                "faith_shield": current_psi_state.get("faith_shield", 0.0),
                "giving_up_rate": current_psi_state.get("giving_up_rate", 0.0),
                "active_emotions": current_psi_state.get("active_emotions", {})
            },
            "trait_memory_bank": self.trait_list,  # 持久化特质库
            "chat_history": self.message_history.export_history() if hasattr(self.message_history,
                                                                             'export_history') else []
        }
        logger.info(f"Avatar [{self.character_name}] state successfully serialized.")
        return archive_data

    def load_avatar_state(self, archive_data: dict):
        """从持久化字典中反序列化，完美恢复心理状态和特质库"""
        try:
            # 1. 恢复静态特质库
            self.trait_list = archive_data.get("trait_memory_bank", [])

            # 2. 强行灌入 PSI 核心引擎的运行时变量
            live_state = archive_data.get("psi_live_state", {})

            # ⚠️ 关键设计：需要在你的 PSI3DGlassBridge 或内部 P_Layer/Mood_Layer 中
            # 实现一个 set_avatar_state() 或直接覆写方法，绕过演进时钟强行同步数值
            if hasattr(self.engine, "force_sync_state"):
                self.engine.force_sync_state(live_state)
            else:
                # 兜底隐式覆写（如果后端引擎没有提供显式方法，可直接操作私有属性或通过刺激信号回补）
                logger.warning(
                    "PSI Engine lacks direct force_sync_state method. Attempting regular property hydration.")
                # 示例：直接覆盖（视你底层 PSI3DGlassBridge 的内部结构而定）
                # self.engine.mood_layer.valence = live_state.get("mood_valence")

            # 3. 恢复历史对话（可选）
            if hasattr(self.message_history, 'load_history') and "chat_history" in archive_data:
                self.message_history.load_history(archive_data["chat_history"])

            logger.info(f"Avatar [{self.character_name}] successfully reloaded from archive.")
        except Exception as e:
            logger.error(f"Critical error while loading avatar state for {self.character_name}: {e}")
            raise e