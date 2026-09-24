from pyexpat.errors import messages
import os,json
from src.models.psi.trait import TraitNormalizer
from src.pattern.psi_avatar import PsiAvatar
from src.logger_singleton import logger
from src.utils.util_json import extract_and_parse_json

class AvatarOrchestrator:
    """管理多个数字生命，统一驱动流水线"""
    def __init__(self, llm_client, model_name="google/gemma-4-31b-it", storage_dir="storage/avatars"):
        self.llm_client = llm_client
        self.model_name = model_name
        self.avatars = {}
        self.trait_normalizer = TraitNormalizer(llm_client)
        self.storage_dir = storage_dir

    def register_avatar(self, key: str, avatar: PsiAvatar):
        self.avatars[key] = avatar
        avatar.trait_factory = self.trait_normalizer

    def process_pipeline(self, user_message: str, message_hist: str) -> dict:
        """核心批处理流：一键让所有注册的智能体感知外部世界并准备好状态"""
        for key, avatar in self.avatars.items():
            logger.info(f"Processing {key} character_name {avatar.get_charactor_name()} profession {avatar.get_profession()}")
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

    def generate_responses(self, context: str, user_message: str) -> dict:
        """批量生成所有角色的文本回复"""
        responses = {}
        for key, avatar in self.avatars.items():
            logger.info(f"Processing {key} character_name {avatar.get_charactor_name()} profession {avatar.get_profession()}")
            try:
                messages = avatar.get_common_chat_payload(context,user_message)
                response = self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.4,
                )
                responses[key] = response.choices[0].message.content.strip()
            except Exception as e:
                responses[key] = f"Generation Error: {e}"
        return responses

    def append_trait(self, key: str, trait_text: str) -> dict:
        """添加特质"""
        if key not in self.avatars:
            logger.info(f"No avatar found for {key}")
            return {}

        if self.avatars[key]:
            self.avatars[key].append_new_trait(trait_text)
        return {}

    def save_all_avatars(self):
        """批量将所有注册的虚拟人状态持久化到本地磁盘"""
        for key, avatar in self.avatars.items():
            try:
                archive_data = avatar.export_avatar_state()
                file_path = os.path.join(self.storage_dir, f"{key}_psyche.json")

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(archive_data, f, ensure_ascii=False, indent=2)

                logger.info(f"Successfully saved persistence file for avatar key: {key}")
            except Exception as e:
                logger.error(f"Failed to save archive for {key}: {e}")

    def load_avatar_from_storage(self, key: str, lore_factory) -> bool:
        """从本地磁盘读取数据，动态重建或恢复某个特定的虚拟人"""
        file_path = os.path.join(self.storage_dir, f"{key}_psyche.json")
        if not os.path.exists(file_path):
            logger.warning(f"No persistence file found for key: {key} at {file_path}")
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)

            metadata = archive_data.get("metadata", {})

            # 1. 如果运行时实例不存在，利用元数据执行“冷启动”实例化
            if key not in self.avatars:
                logger.info(f"Cold starting avatar instance for key: {key} ...")
                from src.pattern.psi_avatar import PsiAvatar
                new_avatar = PsiAvatar(
                    character_name=metadata.get("character_name"),
                    mbti=metadata.get("mbti"),
                    profession=metadata.get("profession"),
                    lore_factory=lore_factory,
                    trait_factory=self.trait_normalizer
                )
                self.register_avatar(key, new_avatar)

            # 2. 状态强行灌入（恢复内存与动态心情）
            self.avatars[key].load_avatar_state(archive_data)
            return True

        except Exception as e:
            logger.error(f"Critical error during loading avatar from database/file: {e}")
            return False