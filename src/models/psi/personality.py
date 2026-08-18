# filename: personality.py
import random


class PersonalityLayer:
    """
    静态性格层：负责将抽象的性格标签（如MBTI）转换为数字化的基因向量(OCEAN)
    该层一经初始化，在系统运行期间通常是只读的。
    """

    def __init__(self, mbti_string: str):
        self.mbti = mbti_string.upper().strip()
        self.ocean = self._convert_mbti_to_ocean(self.mbti)

    def _convert_mbti_to_ocean(self, mbti: str) -> dict:
        clean = mbti.split('-')
        base = clean[0]
        suffix = clean[1] if len(clean) > 1 else 'A'

        # 严格定义MBTI字母到OCEAN区间范围的映射
        ranges = {
            'E': (0.7, 0.95), 'I': (0.05, 0.3),
            'N': (0.7, 0.95), 'S': (0.05, 0.3),
            'F': (0.7, 0.95), 'T': (0.05, 0.3),
            'J': (0.7, 0.95), 'P': (0.05, 0.3),
            'A_s': (0.05, 0.3), 'T_s': (0.7, 0.95)
        }

        return {
            "O": random.uniform(*ranges.get(base[1], (0.4, 0.6))),
            "C": random.uniform(*ranges.get(base[3], (0.4, 0.6))),
            "E": random.uniform(*ranges.get(base[0], (0.4, 0.6))),
            "A": random.uniform(*ranges.get(base[2], (0.4, 0.6))),
            "N": random.uniform(*ranges.get(f"{suffix}_s", (0.4, 0.6)))
        }

    def get_trait(self, trait_name: str) -> float:
        return self.ocean.get(trait_name, 0.5)
    # === 🌟 核心新增：反向重塑观念的接口 ===
    def dynamic_reshape_trait(self, trait_name: str, delta: float):
        """
        这个接口允许习惯层反向修改性格基因。
        变化率非常微小（例如 0.005），代表“观念极难被轻易改变，需要日积月累”。
        """
        if trait_name in self.ocean:
            # 限制在 [0.0, 1.0] 的合法性格区间内
            self.ocean[trait_name] = max(0.0, min(1.0, self.ocean[trait_name] + delta))