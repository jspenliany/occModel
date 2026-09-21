from src.pattern.psi_avatar import PsiAvatar
from src.logger_singleton import logger
from src.utils.util_json import extract_and_parse_json

class AvatarOrchestrator:
    """管理多个数字生命，统一驱动流水线"""
    def __init__(self, llm_client, model_name="google/gemma-4-31b-it"):
        self.llm_client = llm_client
        self.model_name = model_name
        self.avatars = {}

    def register_avatar(self, key: str, avatar: PsiAvatar):
        self.avatars[key] = avatar

    def process_pipeline(self, user_message: str, message_hist: str) -> dict:
        """核心批处理流：一键让所有注册的智能体感知外部世界并准备好状态"""
        for key, avatar in self.avatars.items():
            try:
                # 1. 情感反射阶段：让 LLM 评估当前事件对该角色的 OCC 冲击
                messages = avatar.get_reflect_payload(message_hist, user_message)
                response = self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.4,
                )
                raw_text = response.choices[0].message.content.strip()
                appraisal_data = extract_and_parse_json(raw_text)

                # 2. 状态内化与时钟演进阶段
                avatar.apply_appraisal_and_tick(appraisal_data)

            except Exception as e:
                logger.error(f"Error processing emotional reflection for {key}: {e}")

    def generate_responses(self, user_message: str) -> dict:
        """批量生成所有角色的文本回复"""
        responses = {}
        for key, avatar in self.avatars.items():
            try:
                messages = avatar.get_response_payload(user_message)
                response = self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.4,
                )
                responses[key] = response.choices[0].message.content.strip()
            except Exception as e:
                responses[key] = f"Generation Error: {e}"
        return responses
