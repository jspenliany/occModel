from typing import Tuple, Dict, List
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
    # 各状态轴的上下限三元组/二元组边界配置（采用 Tuple 形式生成）
    valence_absolute_bounds: Tuple[float, float] = Field(
        default=(-1.0, 1.0), description="愉悦度 (Valence) 的全系统绝对物理区间"
    )
    arousal_absolute_bounds: Tuple[float, float] = Field(
        default=(-1.0, 1.0), description="激活度 (Arousal) 的全系统绝对物理区间"
    )
    competence_absolute_bounds: Tuple[float, float] = Field(
        default=(0.0, 1.0), description="信念核心 (Competence) 的全系统绝对物理区间"
    )
    competence_wear_step: float = Field(
        default=0.005, description="护盾拦截伤害时，轻微磨损信心的步长"
    )
    mood_valence_impact_factor: float = Field(
        default=0.5, description="愉悦度 (Valence) 转化为基础过滤器系数的物理权重（原 0.5）"
    )
    mood_competence_offset: float = Field(
        default=1.2, description="信心核心 (Competence) 对负面感受缩减计算的基准偏移量（原 1.2）"
    )
    mood_giving_up_base_offset: float = Field(
        default=1.0, description="放弃意愿 (Giving-up Rate) 对负面感受二次暴击放大的基准偏移量（原 1.0）"
    )

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

class FactionWeightConfig(BaseModel):
    """
    【派系引力强度矩阵配置】
    用于定义大五人格（OCEAN）中哪些特征的极化会引发该心理学派系的觉醒。
    """
    trait_formula: List[Tuple[str, bool]] = Field(
        ...,
        description=(
            "用于连乘计算派系强度的特征元组列表。 "
            "格式: (特质名 'O'/'C'/'E'/'A'/'N', 是否执行 1.0 - trait 的反转计算)。"
            "连乘机制使得所有特征同时极化时，该派系的话语权会发生指数级暴击。"
        )
    )


class DistortionEffectConfig(BaseModel):
    """
    【事件认知扭曲/暴击系数配置】
    定义不同的核心心理学派系在遭遇“好事”或“坏事”时，在主观层面上对伤害或收益的放大/缩小系数。
    """
    pessimist: float = Field(
        ...,
        description="多疑悲观派（Pessimist）的扭曲系数。原硬编码中：好事为 0.4 倍缩水，坏事为 2.0 倍放大。"
    )
    optimist: float = Field(
        ...,
        description="盲目乐天派（Optimist）的扭曲系数。原硬编码中：好事为 1.5 倍爆放大，坏事为 0.2 倍稀释钝化。"
    )
    detachment: float = Field(
        ...,
        description="冷漠孤僻派（Detachment）的扭曲系数。原硬编码中：无论好事坏事，强行稀释为 0.1 倍，表现为极度麻木。"
    )


class AttributionBiasConfig(BaseModel):
    """
    【归因偏误与责任内化配置】
    处理当遭遇负面刺激时，个体的心理防御机制如何扭曲责任归属。
    """
    victim_blame_multiplier: float = Field(
        default=1.5,
        description="偏执受害者（Victim）倾向越强，越倾向于无中生有地指责外界，将坏事转化为外部责备（Blameworthiness）的乘数。"
    )
    narcissist_self_shame_multiplier: float = Field(
        default=1.2,
        description="完美主义自恋派（Narcissist）在坏事发生时，疯狂引发内心自我羞耻（Self-Blameworthiness）的内化乘数。"
    )
    narcissist_external_blame_multiplier: float = Field(
        default=0.8,
        description="完美主义自恋派出于自尊心受挫、本能产生反向防御攻击他人（外部责备）的乘数。"
    )


class CognitiveFilterConfig(BaseModel):
    """
    【全局认知滤网声明式配置中心】
    彻底干掉底层 OCC 结算引擎中的硬编码和魔术数字，实现千人千面的动态性格认知过滤器。
    """

    # 1. 五大派系引力公式默认配置
    factions: Dict[str, FactionWeightConfig] = Field(
        default_factory=lambda: {
            # 多疑悲观派: 神经质高(N) & 宜人性低(1-A) & 外倾性低(1-E)
            "pessimist": FactionWeightConfig(trait_formula=[("N", False), ("A", True), ("E", True)]),
            # 盲目乐天派: 外倾性高(E) & 宜人性高(A) & 神经质低(1-N)
            "optimist": FactionWeightConfig(trait_formula=[("E", False), ("A", False), ("N", True)]),
            # 偏执受害者: 神经质高(N) & 宜人性低(1-A) & 开放性低(1-O)
            "victim": FactionWeightConfig(trait_formula=[("N", False), ("A", True), ("O", True)]),
            # 冷漠孤僻派: 外倾性低(1-E) & 神经质低(1-N) & 宜人性低(1-A)
            "detachment": FactionWeightConfig(trait_formula=[("E", True), ("N", True), ("A", True)]),
            # 自恋完美派: 尽责性高(C) & 宜人性低(1-A) & 神经质高(N)
            "narcissist": FactionWeightConfig(trait_formula=[("C", False), ("A", True), ("N", False)]),
        },
        description="系统内置的五大核心精神派系特征连乘链公式配置。"
    )

    # 2. 好事发生时的内化扭曲参数 (raw_desirability > 0)
    good_event_distortion: DistortionEffectConfig = Field(
        default_factory=lambda: DistortionEffectConfig(pessimist=0.4, optimist=1.5, detachment=0.1),
        description="好事（Desirability > 0）输入时，悲观派、乐天派和冷漠派的话语权放大/缩小系数。"
    )

    # 3. 坏事发生时的内化扭曲参数 (raw_desirability < 0)
    bad_event_distortion: DistortionEffectConfig = Field(
        default_factory=lambda: DistortionEffectConfig(pessimist=2.0, optimist=0.2, detachment=0.1),
        description="坏事（Desirability < 0）输入时，悲观派、乐天派和冷漠派的伤害放大/钝化稀释系数。"
    )

    # 4. 归因偏误乘数配置
    attribution_bias: AttributionBiasConfig = Field(
        default_factory=AttributionBiasConfig,
        description="坏事发生时，受害者派系与自恋完美派系引发的反向甩锅和自责内省乘数配置。"
    )

    # 5. 外部非议与指责的特殊过滤乘数 (raw_blameworthiness < 0)
    criticism_pessimist_multiplier: float = Field(
        default=2.0,
        description="被人非议或严厉责备时，多疑悲观派双倍放大他人指责和敌意的系数。"
    )
    criticism_detachment_multiplier: float = Field(
        default=0.1,
        description="被人非议或严厉责备时，冷漠孤僻派强行屏蔽、降维抹平情绪伤害的降噪系数。"
    )

class EngineConfig(BaseModel):
    """全局数字人情感引擎声明式配置中心"""
    mbti_ranges: TraitRangeConfig = Field(default_factory=TraitRangeConfig)
    occ_engine: OccEngineConfig = Field(default_factory=OccEngineConfig)
    psychological_state: PsychologicalStateConfig = Field(default_factory=PsychologicalStateConfig)
    cognitive_filter: CognitiveFilterConfig = Field(default_factory=CognitiveFilterConfig)