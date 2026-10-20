import json
from typing import TypedDict
from src.logger_singleton import logger
from src.utils.util_json import extract_and_parse_json_list, get_now_time
class NodeDict(TypedDict):
    avatar_id: str
    raw_text: str
    normalized_params: list
    node_type: str
    timestamp: str

def empty_node() -> NodeDict:
    return {
        "avatar_id": "",
        "raw_text": "",
        "normalized_params": [],
        "node_type": "",
        "timestamp": ""
    }

class TraitNormalizer:
    def __init__(self, llm_client, model_name="google/gemma-4-31b-it"):
        self.llm_client = llm_client
        self.model_name = model_name

    def normalize_new_chunk(self, messages: list, temperature: float=0.4) -> tuple[NodeDict,NodeDict]:
        """
        接收散落特质碎片，通过 LLM 降维标准化，最终返回用于混合存储的完整对象
        """
        logger.debug(f"trait normalization ...begin")
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
            )
            raw_text = response.choices[0].message.content.strip()
            logger.info(f"trait normalization successfully synced to memory block. \n{raw_text}\n")
            trait_and_memory = json.loads(raw_text)
            if trait_and_memory:
                trait_list = trait_and_memory.get("extracted_traits")
                memory_list = trait_and_memory.get("extracted_memories")
                logger.debug(f"{trait_list}....{memory_list}")
                # 拼装双轨制最终存储实体（原文承载语感，参数用于精准硬检索）
                trait_node:NodeDict = {
                    "avatar_id": "not_init",
                    "raw_text": raw_text.strip(),
                    "normalized_params": trait_list,
                    "node_type": "trait_node",
                    "timestamp": get_now_time()  # 系统当前主时钟时间戳
                }
                memory_node:NodeDict = {
                    "avatar_id": "not_init",
                    "raw_text": raw_text.strip(),
                    "normalized_params": memory_list,
                    "node_type": "memory_node",
                    "timestamp": get_now_time()  # 系统当前主时钟时间戳
                }
                logger.info("Trait normalization successfully synced to memory block.")
                return trait_node, memory_node
            else:
                logger.debug(f"trait normalization failed. \n{raw_text}\n")
                trait_node = empty_node()
                trait_node["raw_text"] = raw_text.strip()
                trait_node["node_type"] = "trait_node"
                trait_node["timestamp"] = get_now_time()  # 系统当前主时钟时间戳

                memory_node = empty_node()
                memory_node["raw_text"] = raw_text.strip()
                memory_node["node_type"] = "memory_node"
                memory_node["timestamp"] = get_now_time()  # 系统当前主时钟时间戳

                return trait_node,memory_node

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Ti-Engine Guard Triggered! Normalization output invalid: {e}")
            # 优雅的错误回退机制
            trait_node = empty_node()
            trait_node["raw_text"] = "error"
            trait_node["node_type"] = "trait_node"
            trait_node["timestamp"] = get_now_time()  # 系统当前主时钟时间戳
            memory_node = empty_node()
            memory_node["raw_text"] = "error"
            memory_node["node_type"] = "memory_node"
            memory_node["timestamp"] = get_now_time()  # 系统当前主时钟时间戳
            return trait_node,memory_node
