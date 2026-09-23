import re, json
from datetime import datetime
from zoneinfo import ZoneInfo

def extract_and_parse_json(text: str) -> dict:
    # 尝试匹配 ```json ... ``` 或 ``` ... ``` 内部的内容
    json_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_block_match:
        text_to_parse = json_block_match.group(1)
    else:
        # 如果没有 Markdown 标记，尝试直接匹配最外层的第一个 { 到最后一个 }
        just_json_match = re.search(r'(\{.*\})', text, re.DOTALL)
        text_to_parse = just_json_match.group(1) if just_json_match else text

    # 将字符串转为 Python 字典
    return json.loads(text_to_parse)

def extract_and_parse_json_list(text: str) -> list:
    """专门用于提取和解析 JSON 数组 [...] 的方法"""
    try:
        text = text.strip()
        # 1. 尝试匹配 ```json ... ``` 或 ``` ... ``` 内部的 [ ... ] 内容
        json_block_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
        if json_block_match:
            text_to_parse = json_block_match.group(1)
        else:
            # 2. 如果没有 Markdown 标记，尝试直接匹配最外层的第一个 [ 到最后一个 ]
            just_json_match = re.search(r'(\[.*\])', text, re.DOTALL)
            text_to_parse = just_json_match.group(1) if just_json_match else text

        # 3. 将字符串转为 Python 列表
        return json.loads(text_to_parse)
    except Exception as e:
        # 优雅回退：解析失败时返回空列表，防止上层流水线崩塌
        return []

def get_now_time():
    tz = ZoneInfo("Asia/Shanghai")
    now = datetime.now(tz)

    # 2. 精确到秒（去掉微秒）
    now_sec = now.replace(microsecond=0)
    return now_sec