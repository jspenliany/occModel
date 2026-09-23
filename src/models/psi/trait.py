import json
from src.logger_singleton import logger
from src.utils.util_json import extract_and_parse_json, get_now_time


class TraitNormalizer:
    def __init__(self, llm_client, model_name="google/gemma-4-31b-it"):
        self.llm_client = llm_client
        self.model_name = model_name

    def normalize_new_chunk(self, messages: list) -> dict:
        """
        接收散落特质碎片，通过 LLM 降维标准化，最终返回用于混合存储的完整对象
        """
        logger.debug(f"trait normalization ...begin")
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.4,
            )
            raw_text = response.choices[0].message.content.strip()
            appraisal_data = extract_and_parse_json(raw_text)

            # 拼装双轨制最终存储实体（原文承载语感，参数用于精准硬检索）
            trait_memory_node = {
                "avatar_id": "not_init",
                "raw_text": raw_text.strip(),
                "normalized_params": appraisal_data,
                "timestamp": get_now_time()  # 系统当前主时钟时间戳
            }
            logger.info("Trait normalization successfully synced to memory block.")
            return trait_memory_node

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Ti-Engine Guard Triggered! Normalization output invalid: {e}")
            # 优雅的错误回退机制
            return {
                "avatar_id": "not_init",
                "raw_text": "no raw text",
                "normalized_params": {
                    "domain": "preference",
                    "topic_tags": ["unknown"],
                    "linked_entities": [],
                    "emotional_weight": 0.5,
                    "action_mode": "neutral"
                },
                "timestamp": get_now_time()
            }
