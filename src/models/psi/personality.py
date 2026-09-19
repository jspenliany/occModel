# filename: personality.py
import random
from src.models.psi.engine_config import EngineConfig
from src.models.mbti2occ import MBTIToOCCEngine

class PersonalityLayer:
    """
    静态/极慢变性格观念层：
    1. 存储底层认知基因 (OCEAN)。
    2. 具备观念可塑性接口（缓慢自循环）。
    3. 🌟 新增：提供外部降维打击接口（顿悟/权威书籍反转）。
    """

    def __init__(self, mbti_string: str):
        self.config = EngineConfig()
        self.mbti = mbti_string.upper().strip()
        engine_tool = MBTIToOCCEngine()
        self.ocean = engine_tool.convert_mbti_to_ocean(self.mbti, engine_config=self.config)


    def get_trait(self, trait_name: str) -> float:
        return self.ocean.get(trait_name, 0.5)

    def dynamic_reshape_trait(self, trait_name: str, delta: float):
        """【自循环接口】：习惯日积月累，极度缓慢且微弱地修改底层的核心观念。"""
        if trait_name in self.ocean:
            self.ocean[trait_name] = max(0.0, min(1.0, self.ocean[trait_name] + delta))

    # === 🌟 核心新增：外界权威/书籍直击灵魂的观念反转接口 ===
    def paradigm_shift_by_external_source(self, target_trait: str, trigger_text: str, force_value: float):
        """
        降维反转：接收到符合内在某种渴望的文本时，直接跳过缓慢更新，瞬间强制重写观念。
         force_value: 期望转变到的目标绝对数值 [0.0, 1.0]
        """
        if target_trait in self.ocean:
            old_val = self.ocean[target_trait]
            self.ocean[target_trait] = max(0.0, min(1.0, force_value))
            print(f"\n📖 [观念崩塌与重塑] 受到外界核心刺激/阅读书籍。")
            print(f"触发文本: \"{trigger_text}\"")
            print(f"核心观念 [{target_trait}] 发生断裂式突变：{old_val:.2f} ──> {self.ocean[target_trait]:.2f}")

    # 追加入 personality.py 的 PersonalityLayer 类中
    def to_dict(self) -> dict:
        return {
            "mbti": self.mbti,
            "ocean": self.ocean
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PersonalityLayer':
        # 绕过 init 的随机转化，直接还原锁定数值
        instance = cls.__new__(cls)
        instance.mbti = data["mbti"]
        instance.ocean = data["ocean"]
        return instance