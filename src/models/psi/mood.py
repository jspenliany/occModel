# filename: mood.py

class MoodLayer:
    """
    动态心境层：基于2D维度的心情模型（Valence愉悦度, Arousal激活度）
    负责处理中期的情绪平移、生理/物理状态（如PSI模型中的能量、健康度）对心情的消耗。
    """

    def __init__(self, base_valence: float = 0.0, base_arousal: float = 0.0):
        # 理论基准线（由性格决定）
        self.baseline_valence = base_valence
        self.baseline_arousal = base_arousal

        # 当前实际心情状态
        self.valence = base_valence
        self.arousal = base_arousal

        self.decay_rate = 0.05  # 心情恢复到基准线的速度（中期变动慢）

    def update_decay(self):
        """时间步 tick：心情缓慢向性格基准线收敛"""
        self.valence += (self.baseline_valence - self.valence) * self.decay_rate
        self.arousal += (self.baseline_arousal - self.arousal) * self.decay_rate

    def apply_physiological_impact(self, delta_v: float, delta_a: float):
        """生理需求/物理接口（如PSI中的精力耗尽、身体受损）对中短期心境的直接打击"""
        self.valence = max(-1.0, min(1.0, self.valence + delta_v))
        self.arousal = max(-1.0, min(1.0, self.arousal + delta_a))

    def get_mood_multiplier(self) -> float:
        """提供给外部的拦截器系数：负向心境会放大负面体验"""
        return 1.0 - (self.valence * 0.5)
