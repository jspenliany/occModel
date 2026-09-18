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

class HopePrecipitationConfig(BaseModel):
    """Configuration governing how positive hope impacts internal resilience"""
    trigger_threshold: float = Field(default=0.4, description="高希望度沉淀门槛")
    competence_gain: float = Field(default=0.03, description="信念核心增长步长")
    faith_shield_multiplier: float = Field(default=0.5, description="希望转化为护盾的物理系数")
    max_faith_shield: float = Field(default=0.8, description="动态护盾充电上限")
    faith_shield_decay: float = Field(default=0.04, description="失去希望时护盾自然流失步长")

class HardshipResilienceConfig(BaseModel):
    """Settings managing state protection lines while navigating stressors"""
    min_faith_shield_active: float = Field(default=0.1, description="护盾抗性生效的最低残存阈值")
    min_competence_active: float = Field(default=0.6, description="即便无护盾，维持高抗压的底线信念")
    min_valence_active: float = Field(default=-0.1, description="维持高抗压的最低心情边界值")
    giving_up_suppression: float = Field(default=0.1, description="有信念时困境放弃意愿被压制的压制步长")
    valence_floor_protected: float = Field(default=-0.2, description="有护盾时保护的心情谷底低限")

class DespairCollapseConfig(BaseModel):
    """System degradation metrics for broken, unshielded agents during hardship"""
    giving_up_avalanche: float = Field(default=0.25, description="绝望后放弃意愿狂飙步长")
    competence_drain: float = Field(default=0.1, description="信心雪崩崩塌速度步长")
    valence_drain: float = Field(default=0.2, description="心情疯狂下坠的速度步长")
    valence_floor_unprotected: float = Field(default=-1.0, description="无护盾未受保护的心情极限谷底")

class RecoveryConfig(BaseModel):
    """Calm state calibration after leaving hostile environmental factors"""
    giving_up_recovery: float = Field(default=0.1, description="脱离困境后放弃意愿自然冷却复原速率")

class PsychologicalStateConfig(BaseModel):
    """Configuration data governing emotional baseline decay and internal belief vectors"""
    default_base_valence: float = Field(default=0.0, description="默认初始/基线愉悦度 (Valence)")
    default_base_arousal: float = Field(default=0.0, description="默认初始/基线激活度 (Arousal)")
    decay_rate: float = Field(default=0.05, description="情感向基线状态自然衰减的速度率")

    # 信念与放弃系统
    default_competence: float = Field(default=0.7, description="初始必胜信念核心（内在成就感满足度基准值）")
    initial_faith_shield: float = Field(default=0.0, description="初次启动时的动态坚韧护盾值")
    initial_giving_up_rate: float = Field(default=0.0, description="初次启动时的困境放弃意愿/摆烂度起点")
    hope_precipitation: HopePrecipitationConfig = Field(default_factory=HopePrecipitationConfig)
    hardship_resilience: HardshipResilienceConfig = Field(default_factory=HardshipResilienceConfig)
    despair_collapse: DespairCollapseConfig = Field(default_factory=DespairCollapseConfig)
    recovery: RecoveryConfig = Field(default_factory=RecoveryConfig)

class EngineConfig(BaseModel):
    """全局数字人情感引擎声明式配置中心"""
    mbti_ranges: TraitRangeConfig = Field(default_factory=TraitRangeConfig)
    occ_engine: OccEngineConfig = Field(default_factory=OccEngineConfig)
    psychological_state: PsychologicalStateConfig = Field(default_factory=PsychologicalStateConfig)