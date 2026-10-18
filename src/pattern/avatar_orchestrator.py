import os,json
from src.models.psi.trait import TraitNormalizer
from src.pattern.psi_avatar import PsiAvatar
from src.logger_singleton import logger
from src.utils.util_json import extract_and_parse_json
from datetime import datetime
import zoneinfo

class DateTimeEncoder(json.JSONEncoder):
    """
    自定义的 JSON 编码器，专门拦截并自动序列化 datetime 对象。
    如果遭遇常规数据则正常移交系统底层处理。
    """
    def default(self, obj):
        if isinstance(obj, datetime):
            # 序列化为 ISO 格式字符串，例如: "2026-10-18T06:52:09+08:00"
            return obj.isoformat()
        return super().default(obj)

class AvatarOrchestrator:
    """管理多个数字生命，统一驱动流水线"""
    def __init__(self, llm_client, model_name="google/gemma-4-31b-it", storage_dir="data/psyche_storage"):
        self.llm_client = llm_client
        self.model_name = model_name
        self.avatars = {}
        self.trait_normalizer = TraitNormalizer(llm_client)
        #获取当前 avatar_orchestrator.py 所在的绝对目录 (即 src/pattern/)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 向上跳两层：src/pattern/ -> src/ -> 项目根目录
        project_root = os.path.abspath(os.path.join(current_dir, "../.."))
        #拼接指向根目录下的 data/psyche_storage
        self.storage_dir = os.path.join(project_root, "data", "psyche_storage")
        #确保目录被自动创建
        os.makedirs(self.storage_dir, exist_ok=True)

        logger.info(f"Strict path hydration complete: {self.storage_dir}")

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

    def chat_turn(self, key: str, context: str, user_message: str) -> str:
        avatar = self.avatars[key]

        # 1. 情感反射阶段：让 LLM 评估当前事件对该角色的 OCC 冲击
        reflect_payload = avatar.get_reflect_payload(context, user_message)
        response = self.llm_client.chat.completions.create(
            model=self.model_name, messages=reflect_payload, temperature=0.4
        )
        appraisal_data = extract_and_parse_json(response.choices[0].message.content.strip())

        # 2. 状态内化与时钟演进阶段（让心理时钟真正 Tick 起来！）
        avatar.apply_appraisal_and_tick(appraisal_data)

        # 3. 此时基于最新自然衰减、危机结算后的心理状态，生成文本回复
        chat_payload = avatar.get_common_chat_payload(context, user_message)
        chat_response = self.llm_client.chat.completions.create(
            model=self.model_name, messages=chat_payload, temperature=0.4
        )
        return chat_response.choices[0].message.content.strip()

    def append_trait(self, key: str, trait_text: str) -> dict:
        """添加特质"""
        logger.debug(f"Appending {key} to trait text: {trait_text}...begin")
        if key not in self.avatars:
            logger.info(f"No avatar found for {key}")
            return {}

        if self.avatars[key]:
            self.avatars[key].append_new_trait(trait_text)
        logger.debug(f"Successfully appended {key} to trait text: {trait_text}")
        return {}

    def save_all_avatars(self):
        """批量将所有注册的虚拟人状态持久化到本地磁盘"""
        for key, avatar in self.avatars.items():
            try:
                archive_data = avatar.export_avatar_state()
                file_path = os.path.join(self.storage_dir, f"{key}_psyche.json")
                logger.debug(f"Saving archive for {key}: {archive_data}")
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(archive_data, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)

                logger.info(f"Successfully saved persistence file for avatar key: {key}")
            except Exception as e:
                logger.error(f"Failed to save archive for {key}: {e}")

    def load_avatar_state(self, archive_data: dict) -> None:
        """
        Deep re-hydration of the digital soul's memory state graph.
        Defensively parses serialised ISO string timestamps back into timezone-aware datetimes.
        """
        try:
            logger.info(f"Initiating state hydration graph for avatar: {self.get_charactor_name()}")

            # 1. Recover core operational profiles & system structural layers
            # Assuming your existing bridge instantiation or sync looks like this:
            if "psi_live_state" in archive_data:
                # If your PSI3DGlassBridge has force_sync_state implemented:
                if hasattr(self, "psi_engine") and self.psi_engine:
                    self.psi_engine.force_sync_state(archive_data["psi_live_state"])
                else:
                    logger.error(f"psi_engine not found in psi_live_state: {archive_data}")
            else:
                logger.error(f"psi_live_state not found in archive_data: {archive_data}")

            # 2. Re-hydrate banks
            if "trait_memory_bank" in archive_data:
                self.trait_memory_bank = archive_data["trait_memory_bank"]
            else:
                logger.error(f"trait_memory_bank not found in archive_data: {archive_data}")
            if "core_memory_bank" in archive_data:
                self.core_memory_bank = archive_data["core_memory_bank"]
            else:
                logger.error(f"core_memory_bank not found in archive_data: {archive_data}")

            # 3. 🌟 CORE PATCH: Defensive Chat History Timeline Re-hydration
            raw_history = archive_data.get("chat_history", [])
            hydrated_history = []

            for turn in raw_history:
                # Defensively copy the dictionary payload to avoid modifying unexpected references
                clean_turn = {k: v for k, v in turn.items()}

                timestamp_raw = clean_turn.get("timestamp")

                if timestamp_raw:
                    if isinstance(timestamp_raw, str):
                        try:
                            # 1. Standard ISO-8601 parser (handles "+08:00" offsets automatically)
                            clean_turn["timestamp"] = datetime.fromisoformat(timestamp_raw)
                        except ValueError:
                            try:
                                # 2. Fallback parser for legacy formats missing explicit standard structures
                                clean_turn["timestamp"] = datetime.strptime(timestamp_raw, "%Y-%m-%d %H:%M:%S")
                                # Fall back safely to target system timezone configuration if offset is completely stripped
                                clean_turn["timestamp"] = clean_turn["timestamp"].replace(
                                    tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")
                                )
                            except Exception as inner_e:
                                logger.error(f"Failed parsing string timestamp '{timestamp_raw}': {inner_e}")
                                # Secondary safety net: fallback directly to system execution wall clock time
                                clean_turn["timestamp"] = datetime.now(zoneinfo.ZoneInfo("Asia/Shanghai"))
                    elif isinstance(timestamp_raw, datetime):
                        # Safeguard in case payload already contains runtime objects
                        pass
                else:
                    # Tertiary safety net if data keys are corrupted or absent
                    clean_turn["timestamp"] = datetime.now(zoneinfo.ZoneInfo("Asia/Shanghai"))

                hydrated_history.append(clean_turn)

            # Assign fully verified timeline graph back to runtime memory context
            self.chat_history = hydrated_history
            logger.info(f"Successfully re-hydrated {len(hydrated_history)} historical turns into state memory.")

        except Exception as e:
            logger.critical(f"Fatal error during cold re-hydration of agent state data: {e}")
            raise e