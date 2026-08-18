# filename: mood.py

class MoodLayer:
    """
    动态心境与需求层（升级版）：
    融合了 PSI 理论的内在需求（Competence 成就感/必胜信心）。
    核心机制：内心的“希望”与“信心”会形成一层精神护盾，大幅削弱眼前的即时痛苦。
    """

    def __init__(self, base_valence: float = 0.0, base_arousal: float = 0.0):
        self.baseline_valence = base_valence
        self.baseline_arousal = base_arousal

        self.valence = base_valence
        self.arousal = base_arousal
        self.decay_rate = 0.05

        # === 🌟 核心新增：PSI 内在需求与信念系统 ===
        self.competence = 0.8  # 成就感/必胜信心（0.0-1.0）。初始值很高代表内心极其自信强大
        self.faith_shield = 0.0  # 动态信念护盾：由短期“希望”沉淀而来，能抵消眼前的痛苦

    def update_decay(self, current_hope: float):
        """时间步 tick：心情缓慢收敛，同时将短期的 Hope 转化为中期的“信念护盾”"""
        self.valence += (self.baseline_valence - self.valence) * self.decay_rate
        self.arousal += (self.baseline_arousal - self.arousal) * self.decay_rate

        # 【信念构建】：短期的 Hope 会补充内心的 Competence（必胜信心），并维持护盾
        if current_hope > 0.5:
            self.competence = min(1.0, self.competence + 0.02)
            self.faith_shield = min(0.8, self.faith_shield + current_hope * 0.4)  # 希望越大，护盾越厚
        else:
            # 护盾会随时间自然缓慢消耗
            self.faith_shield = max(0.0, self.faith_shield - 0.05)

    def apply_physiological_impact(self, delta_v: float, delta_a: float):
        """外部直接打击"""
        # 如果当前拥有“信念护盾”，眼前的负面打击（delta_v < 0）将会被大幅度削弱！
        if delta_v < 0 and self.faith_shield > 0:
            mitigated_loss = delta_v * (1.0 - self.faith_shield)
            self.valence = max(-1.0, min(1.0, self.valence + mitigated_loss))
            # 信心受到挑战，Competence 消耗微量
            self.competence = max(0.0, self.competence - 0.01)
        else:
            self.valence = max(-1.0, min(1.0, self.valence + delta_v))

        self.arousal = max(-1.0, min(1.0, self.arousal + delta_a))

    def get_mood_multiplier(self) -> float:
        """
        情绪过滤器：如果 Competence（必胜信心）很高，
        即便暂时处于逆境（Valence较低），也会极大地压制负面情绪的爆发！
        """
        base_multiplier = 1.0 - (self.valence * 0.5)
        # 必胜信念（Competence）对负面放大效应具有强力压制作用
        return base_multiplier * (1.2 - self.competence)
