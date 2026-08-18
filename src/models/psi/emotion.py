# filename: emotion.py

class OCCEmotionLayer:
    """
    即时情感层：经典的OCC评估模型实现。
    只负责根据输入的“即时认知评估结果（Appraisal）”爆发短期情绪，并执行高频时间衰减。
    """

    def __init__(self):
        self.active_emotions = {
            "Joy": 0.0, "Distress": 0.0, "Anger": 0.0, "Remorse": 0.0
        }
        self.decay_rate = 0.25  # 情感流逝的速度极快（短期起伏大）

    def update_decay(self):
        """时间步 tick：短期情感高频自然消退"""
        for emo in self.active_emotions:
            self.active_emotions[emo] = max(0.0, self.active_emotions[emo] - self.decay_rate)

    def trigger_internal_spark(self, name: str, intensity: float):
        """允许内部代码绕过评估直接注入情感（例如特定剧本杀代码、技能强制恐惧等）"""
        if name in self.active_emotions:
            self.active_emotions[name] = max(0.0, min(1.0, self.active_emotions[name] + intensity))

    def calculate_occ_spikes(self, appraisal: dict, personality_layer, mood_layer):
        """
        核心OCC评估函数：
        不直接访问硬编码，而是通过传入的 personality_layer 和 mood_layer 实例动态拦截计算。
        """
        desirability = appraisal.get("desirability", 0.0)
        blameworthiness = appraisal.get("blameworthiness", 0.0)
        self_blameworthiness = appraisal.get("self_blameworthiness", 0.0)

        # 从解耦的心情层获取当前的“情绪过滤器”
        mood_multiplier = mood_layer.get_mood_multiplier()

        # 从解耦的性格层获取对应的动态阈值
        joy_threshold = 0.3 * (1.0 - personality_layer.get_trait("E"))
        distress_threshold = 0.3 * (1.0 - personality_layer.get_trait("N"))

        # 1. 触发事件类情感
        if desirability > 0:
            joy_spark = (desirability * (1.0 + personality_layer.get_trait("E"))) * (
                        2.0 - mood_multiplier) - joy_threshold
            self.active_emotions["Joy"] = max(0.0, min(1.0, self.active_emotions["Joy"] + joy_spark))
            # 反向联动：瞬间的狂喜会给中期心情层带来一个正向的推力
            mood_layer.apply_physiological_impact(delta_v=joy_spark * 0.2, delta_a=joy_spark * 0.1)

        elif desirability < 0:
            distress_spark = (abs(desirability) * (
                        1.0 + personality_layer.get_trait("N"))) * mood_multiplier - distress_threshold
            self.active_emotions["Distress"] = max(0.0, min(1.0, self.active_emotions["Distress"] + distress_spark))
            # 反向联动：悲伤会拉低心境，同时提高身体的紧绷度(Arousal)
            mood_layer.apply_physiological_impact(delta_v=-distress_spark * 0.3, delta_a=distress_spark * 0.2)

        # 2. 触发复合动作类情感 (Anger / Remorse)
        if blameworthiness > 0 and desirability < 0:
            anger_spark = ((blameworthiness + abs(desirability)) / 2) * (
                        1.5 - personality_layer.get_trait("A")) * mood_multiplier
            self.active_emotions["Anger"] = max(0.0, min(1.0, self.active_emotions["Anger"] + anger_spark))

        if self_blameworthiness > 0 and desirability < 0:
            remorse_spark = ((self_blameworthiness + abs(desirability)) / 2) * (
                        1.0 + personality_layer.get_trait("C")) * (1.0 + personality_layer.get_trait("N"))
            self.active_emotions["Remorse"] = max(0.0, min(1.0, self.active_emotions["Remorse"] + remorse_spark))
