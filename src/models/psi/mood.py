# filename: mood.py

class MoodLayer:
    """
    动态心境层：
    1. 维护中期心境平衡 (Valence, Arousal)。
    2. 🌟 核心升级：融合 PSI 必胜信念与“困境放弃意愿”控制。
    """

    def __init__(self, base_valence: float = 0.0, base_arousal: float = 0.0):
        self.baseline_valence = base_valence
        self.baseline_arousal = base_arousal
        self.valence = base_valence
        self.arousal = base_arousal
        self.decay_rate = 0.05

        # === 🌟 核心升级：信念与放弃系统 ===
        self.competence = 0.7  # 必胜信念核心（内在成就感满足度）
        self.faith_shield = 0.0  # 动态坚韧护盾
        self.giving_up_rate = 0.0  # 困境放弃意愿/崩溃度 [0.0, 1.0]，1.0 代表彻底放弃、摆烂

    def update_decay(self, current_hope: float, in_hardship: bool):
        """主时钟 Tick：计算中期信念的消耗，以及无信念者在困境中的放弃速度"""
        self.valence += (self.baseline_valence - self.valence) * self.decay_rate
        self.arousal += (self.baseline_arousal - self.arousal) * self.decay_rate

        # 信念沉淀机制
        if current_hope > 0.4:
            self.competence = min(1.0, self.competence + 0.03)
            self.faith_shield = min(0.8, self.faith_shield + current_hope * 0.5)
        else:
            self.faith_shield = max(0.0, self.faith_shield - 0.04)

        # 🌟 核心机制：有信念 vs 无信念在困境中的分化
        if in_hardship:
            # 只有当坚韧护盾尚存(>0.1)，或者内心极度自信且目前心情还没彻底绝望时，才能坚持
            if self.faith_shield > 0.1 or (self.competence > 0.6 and self.valence > -0.1):
                # 【有信念/有护盾】：在困境中，放弃意愿被强力压制
                self.giving_up_rate = max(0.0, self.giving_up_rate - 0.1)
                self.valence = max(-0.2, self.valence)  # 锁住心情低谷
            else:
                # 【没有信念/护盾耗尽且心情绝望】：放弃意愿开始狂飙，信心也随之雪崩
                self.giving_up_rate = min(1.0, self.giving_up_rate + 0.25)
                self.competence = max(0.0, self.competence - 0.1)  # 信心发生雪崩
                self.valence = max(-1.0, self.valence - 0.2)  # 心情疯狂下坠
        else:
            # 退出困境后，放弃意愿缓慢平复
            self.giving_up_rate = max(0.0, self.giving_up_rate - 0.1)

    def apply_physiological_impact(self, delta_v: float, delta_a: float):
        """外部直接打击：由于信念护盾的存在，可以拦截伤害"""
        if delta_v < 0 and self.faith_shield > 0:
            # 护盾按百分比完全吸收、冲抵痛苦
            mitigated_loss = delta_v * (1.0 - self.faith_shield)
            self.valence = max(-1.0, min(1.0, self.valence + mitigated_loss))
            self.competence = max(0.0, self.competence - 0.005)  # 轻微磨损信心
        else:
            # 毫无防护，肉身接下打击，并受到放弃率的二次暴击放大
            amplified_loss = delta_v * (1.0 + self.giving_up_rate)
            self.valence = max(-1.0, min(1.0, self.valence + amplified_loss))

        self.arousal = max(-1.0, min(1.0, self.arousal + delta_a))

    def get_mood_multiplier(self) -> float:
        """情绪过滤器系数"""
        base_multiplier = 1.0 - (self.valence * 0.5)
        # 如果已经产生了放弃心理，负面感受直接暴增；如果信心满满，则负面感受被大幅缩减
        return base_multiplier * (1.2 - self.competence) * (1.0 + self.giving_up_rate)
