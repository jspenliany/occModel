# filename: mood.py
from src.models.psi.engine_config import EngineConfig

class MoodLayer:
    """
    动态心境层：
    1. 维护中期心境平衡 (Valence, Arousal)。
    2. 🌟 核心升级：融合 PSI 必胜信念与“困境放弃意愿”控制。
    """

    def __init__(self, config: EngineConfig, base_valence: float = None, base_arousal: float = None):
        self.config = config
        state_cfg = config.psychological_state
        # 计算基线与当前情感维度（优先使用显式传递的入参，无入参时动态读取配置项）
        self.baseline_valence = base_valence if base_valence is not None else state_cfg.default_base_valence
        self.baseline_arousal = base_arousal if base_arousal is not None else state_cfg.default_base_arousal
        self.valence = base_valence
        self.arousal = base_arousal
        # 动态加载自然衰减系数
        self.decay_rate = state_cfg.decay_rate

        # === 🌟 核心升级：信念与放弃系统 ===
        self.competence = state_cfg.default_competence  # 必胜信念核心（内在成就感满足度）
        self.faith_shield = state_cfg.initial_faith_shield  # 动态坚韧护盾
        self.giving_up_rate = state_cfg.initial_giving_up_rate  # 困境放弃意愿/崩溃度 [0.0, 1.0]，1.0 代表彻底放弃、摆烂

    def update_decay(self, current_hope: float, in_hardship: bool):
        """主时钟 Tick：计算中期信念的消耗，以及无信念者在困境中的放弃速度"""
        self.valence += (self.baseline_valence - self.valence) * self.decay_rate
        self.arousal += (self.baseline_arousal - self.arousal) * self.decay_rate

        state_cfg = self.config.psychological_state
        hope_cfg = state_cfg.hope_precipitation
        res_cfg = state_cfg.hardship_resilience
        col_cfg = state_cfg.despair_collapse
        rec_cfg = state_cfg.recovery

        # 信念沉淀机制
        if current_hope > hope_cfg.trigger_threshold:
            self.competence = min(1.0, self.competence + hope_cfg.competence_gain)
            self.faith_shield = min(hope_cfg.max_faith_shield, self.faith_shield + current_hope * hope_cfg.faith_shield_multiplier)
        else:
            self.faith_shield = max(0.0, self.faith_shield - hope_cfg.faith_shield_decay)

        # 🌟 核心机制：有信念 vs 无信念在困境中的分化
        if in_hardship:
            has_active_shield = self.faith_shield > res_cfg.min_faith_shield_active
            has_inner_confidence = self.competence > res_cfg.min_competence_active and self.valence > res_cfg.min_valence_active
            # 只有当坚韧护盾尚存(>0.1)，或者内心极度自信且目前心情还没彻底绝望时，才能坚持
            if has_active_shield or has_inner_confidence:
                # 【有信念/有护盾】：在困境中，放弃意愿被强力压制
                self.giving_up_rate = max(0.0, self.giving_up_rate - res_cfg.giving_up_suppression)
                self.valence = max(res_cfg.valence_floor_protected, self.valence)  # 锁住心情低谷
            else:
                # 【没有信念/护盾耗尽且心情绝望】：放弃意愿开始狂飙，信心也随之雪崩
                self.giving_up_rate = min(1.0, self.giving_up_rate + col_cfg.giving_up_avalanche)
                self.competence = max(0.0, self.competence - col_cfg.competence_drain)  # 信心发生雪崩
                self.valence = max(col_cfg.valence_floor_unprotected, self.valence - col_cfg.valence_drain)  # 心情疯狂下坠
        else:
            # 退出困境后，放弃意愿缓慢平复
            self.giving_up_rate = max(0.0, self.giving_up_rate - res_cfg.giving_up_recovery)

    def apply_physiological_impact(self, delta_v: float, delta_a: float):
        """外部直接打击：由于信念护盾的存在，可以拦截伤害"""
        hardship_cfg = self.config.psychological_state.hardship_resilience

        # 🌟 从持有的 config 中动态解构 Tuple 绝对边界
        v_min, v_max = hardship_cfg.valence_absolute_bounds
        a_min, a_max = hardship_cfg.arousal_absolute_bounds
        c_min, _ = hardship_cfg.competence_absolute_bounds

        if delta_v < 0 and self.faith_shield > 0:
            # 护盾按百分比完全吸收、冲抵痛苦
            mitigated_loss = delta_v * (1.0 - self.faith_shield)
            self.valence = max(v_min, min(v_max, self.valence + mitigated_loss))
            self.competence = max(c_min, self.competence - hardship_cfg.competence_wear_step)  # 轻微磨损信心
        else:
            # 毫无防护，肉身接下打击，并受到放弃率的二次暴击放大
            amplified_loss = delta_v * (1.0 + self.giving_up_rate)
            self.valence = max(v_min, min(v_max, self.valence + amplified_loss))

        self.arousal = max(a_min, min(a_max, self.arousal + delta_a))

    def get_mood_multiplier(self) -> float:
        """情绪过滤器系数"""
        hardship_cfg = self.config.psychological_state.hardship_resilience
        base_multiplier = 1.0 - (self.valence * hardship_cfg.mood_valence_impact_factor)
        # 如果已经产生了放弃心理，负面感受直接暴增；如果信心满满，则负面感受被大幅缩减
        # 信心满满 (competence 接近 1.0) 时，(offset - competence) 变小，负面感受被大幅缩减
        # 产生放弃心理 (giving_up_rate 变大) 时，(base_offset + giving_up_rate) 变大，负面感受暴增
        competence_factor = hardship_cfg.mood_competence_offset - self.competence
        giving_up_factor = hardship_cfg.mood_giving_up_base_offset + self.giving_up_rate

        # 融合返回最终乘数
        return base_multiplier * competence_factor * giving_up_factor

    # 追加入 mood.py 的 MoodLayer 类中
    def to_dict(self) -> dict:
        return {
            "baseline_valence": self.baseline_valence,
            "baseline_arousal": self.baseline_arousal,
            "valence": self.valence,
            "arousal": self.arousal,
            "decay_rate": self.decay_rate,
            "competence": self.competence,
            "faith_shield": self.faith_shield,
            "giving_up_rate": self.giving_up_rate
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MoodLayer':
        instance = cls.__new__(cls)
        for key, value in data.items():
            setattr(instance, key, value)
        return instance