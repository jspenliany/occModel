from typing import Tuple, Dict
from pydantic import BaseModel, Field

class TraitRangeConfig(BaseModel):
    # 基础 4 轴 8 种倾向的连续浮点数生成区间
    E: Tuple[float, float] = Field(default=(0.7, 0.9), description="外倾型 (Extraversion) 区间")
    I: Tuple[float, float] = Field(default=(0.1, 0.3), description="内倾型 (Introversion) 区间")

    N: Tuple[float, float] = Field(default=(0.7, 0.9), description="直觉型 (Openness) 区间")
    S: Tuple[float, float] = Field(default=(0.1, 0.3), description="感觉型 (Closedness) 区间")

    F: Tuple[float, float] = Field(default=(0.7, 0.9), description="情感型 (Agreeableness) 区间")
    T: Tuple[float, float] = Field(default=(0.1, 0.3), description="思考型 (Disagreeableness) 区间")

    J: Tuple[float, float] = Field(default=(0.7, 0.9), description="独立型 (Conscientiousness) 区间")
    P: Tuple[float, float] = Field(default=(0.1, 0.3), description="感知型 (Unconscientiousness) 区间")

    # 身份尾缀区间
    A_s: Tuple[float, float] = Field(default=(0.05, 0.25), description="自我肯定型 (Low Neuroticism) 区ain")
    T_s: Tuple[float, float] = Field(default=(0.7, 0.95), description="动荡型 (High Neuroticism) 区间")

    # 缺省兜底区间
    DEFAULT: Tuple[float, float] = Field(default=(0.4, 0.6), description="当MBTI字符非法时的中庸兜底区间")

class ThresholdConfig(BaseModel):
    """Configuration for baseline emotional thresholds"""
    base_multiplier: float = Field(..., description="基础阈值系数")
    ocean_trait: str = Field(..., description="关联的 OCEAN 人格特质键名 (O/C/E/A/N)")
    invert_trait: bool = Field(default=False, description="是否对人格特质执行反转计算 (1.0 - trait)")

class CompoundConfig(BaseModel):
    """Configuration for compound emotion coefficients"""
    base_offset: float = Field(default=1.0, description="基础偏移常数")
    ocean_trait: str = Field(..., description="关联的 OCEAN 人格特质键名")
    invert_trait: bool = Field(default=False, description="是否对人格特质执行反转计算")

class EmotionFormulaConfig(BaseModel):
    """Declarative setup for an OCC emotion's math pipeline"""
    threshold: ThresholdConfig = Field(..., description="阈值配置")
    personality_multipliers: list[CompoundConfig] = Field(
        default_factory=list,
        description="应用于原始刺激强度的所有人格加权系数列表"
    )

class OccEngineConfig(BaseModel):
    """Global configuration data for the OCC formula parser"""
    emotions: Dict[str, EmotionFormulaConfig] = Field(
        default_factory=lambda: {
            "Joy": EmotionFormulaConfig(
                threshold=ThresholdConfig(base_multiplier=0.4, ocean_trait="E", invert_trait=True),
                personality_multipliers=[CompoundConfig(base_offset=1.0, ocean_trait="E", invert_trait=False)]
            ),
            "Distress": EmotionFormulaConfig(
                threshold=ThresholdConfig(base_multiplier=0.5, ocean_trait="N", invert_trait=True),
                personality_multipliers=[CompoundConfig(base_offset=1.0, ocean_trait="N", invert_trait=False)]
            ),
            "Anger": EmotionFormulaConfig(
                threshold=ThresholdConfig(base_multiplier=0.6, ocean_trait="A", invert_trait=False),
                personality_multipliers=[
                    CompoundConfig(base_offset=1.5, ocean_trait="A", invert_trait=True),
                    CompoundConfig(base_offset=1.0, ocean_trait="N", invert_trait=False)
                ]
            ),
            "Remorse": EmotionFormulaConfig(
                threshold=ThresholdConfig(base_multiplier=0.5, ocean_trait="C", invert_trait=True),
                personality_multipliers=[
                    CompoundConfig(base_offset=1.0, ocean_trait="C", invert_trait=False),
                    CompoundConfig(base_offset=1.0, ocean_trait="N", invert_trait=False)
                ]
            )
        }
    )

class EngineConfig(BaseModel):
    """全局数字人情感引擎声明式配置中心"""
    mbti_ranges: TraitRangeConfig = Field(default_factory=TraitRangeConfig)
    occ_engine: OccEngineConfig = Field(default_factory=OccEngineConfig)