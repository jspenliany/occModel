# filename: emotion.py

class OCCEmotionLayer:
    """
    完备即时情感层：
    1. 实现全量 22 种情感。
    2. 🌟 核心升级：实现“观念内化过滤”，让 AI 产生自我证实、自我强化的滤网。
    """

    def __init__(self):
        self.active_emotions = {name: 0.0 for name in [
            "Joy", "Distress", "Hope", "Fear", "Satisfaction", "Fears_Confirmed",
            "Relief", "Disappointment", "Happy_For", "Pity", "Resentment", "Gloating",
            "Pride", "Shame", "Admiration", "Reproach", "Liking", "Disliking",
            "Gratitude", "Anger", "Gratification", "Remorse"
        ]}
        self.decay_rate = 0.25

    def update_decay(self):
        for emo in self.active_emotions:
            self.active_emotions[emo] = max(0.0, self.active_emotions[emo] - self.decay_rate)

    def calculate_occ_spikes(self, raw_appraisal: dict, personality_layer, mood_layer):
        """
        全量评估矩阵。
        🌟 核心前置机制：【观念的自我强化】。
        AI 不会客观接收 raw_appraisal，而是用底层性格观念对原始输入数据打上滤网。
        """
        trait_A = personality_layer.get_trait("A")
        trait_N = personality_layer.get_trait("N")
        trait_E = personality_layer.get_trait("E")
        trait_O = personality_layer.get_trait("O")
        trait_C = personality_layer.get_trait("C")

        # --- 🌟 开始执行观念内化滤网 (Confirmation Bias Filtering) ---
        # 一个低宜人(A)、高神经质(N)的多疑者，会主动放大外界的恶劣和责备度，强行缩减外界的善意合意度
        filtered_appraisal = {}

        raw_des = raw_appraisal.get("desirability", 0.0)
        if raw_des > 0:
            # 乐天派放大好事，多疑悲观派内化敷衍好事
            filtered_appraisal["desirability"] = raw_des * (trait_E * 1.2)
        else:
            # 敏感焦虑派(High N)会极度放大和内化苦难与伤害
            filtered_appraisal["desirability"] = raw_des * (1.0 + trait_N)

        raw_blame = raw_appraisal.get("blameworthiness", 0.0)
        if raw_blame < 0:  # 被人非议责备
            # 讨厌、防备他人的人(Low A)会双倍放大别人对他的指责度，认定别人是故意害他（观念自我证实）
            filtered_appraisal["blameworthiness"] = raw_blame * (1.5 - trait_A)
        else:
            filtered_appraisal["blameworthiness"] = raw_blame * (0.5 + trait_A)

        # 继承其他参数
        filtered_appraisal["future_desirability"] = raw_appraisal.get("future_desirability", 0.0)
        filtered_appraisal["prospect_status"] = raw_appraisal.get("prospect_status", "none")
        filtered_appraisal["self_blameworthiness"] = raw_appraisal.get("self_blameworthiness", 0.0)
        filtered_appraisal["other_desirability"] = raw_appraisal.get("other_desirability", 0.0)
        filtered_appraisal["other_relationship"] = raw_appraisal.get("other_relationship", 0.0)
        filtered_appraisal["appealingness"] = raw_appraisal.get("appealingness", 0.0)

        # --- 结束滤网，以下使用过滤后的内化数据进行 OCC 22 模型结算 ---
        desirability = filtered_appraisal["desirability"]
        future_desirability = filtered_appraisal["future_desirability"]
        prospect_status = filtered_appraisal["prospect_status"]
        blameworthiness = filtered_appraisal["blameworthiness"]
        self_blameworthiness = filtered_appraisal["self_blameworthiness"]
        other_desirability = filtered_appraisal["other_desirability"]
        other_relationship = filtered_appraisal["other_relationship"]
        appealingness = filtered_appraisal["appealingness"]

        mood_multiplier = mood_layer.get_mood_multiplier()

        # 0. 远期未来前瞻
        if future_desirability > 0:
            hope_spark = future_desirability * (1.0 + trait_E) * (1.5 - trait_N)
            self.active_emotions["Hope"] = max(0.0, min(1.0, self.active_emotions["Hope"] + hope_spark))

        # 1.1 & 1.2 预期类
        if prospect_status == "expected":
            if desirability > 0:
                self.active_emotions["Hope"] = max(0.0, min(1.0, self.active_emotions["Hope"] + desirability * (
                            1.0 + trait_E)))
            elif desirability < 0:
                self.active_emotions["Fear"] = max(0.0, min(1.0, self.active_emotions["Fear"] + abs(desirability) * (
                            1.0 + trait_N)))
        elif prospect_status == "confirmed":
            if desirability > 0:
                self.active_emotions["Satisfaction"] = max(0.0, min(1.0, self.active_emotions[
                    "Satisfaction"] + desirability))
            elif desirability < 0:
                self.active_emotions["Fears_Confirmed"] = max(0.0, min(1.0,
                                                                       self.active_emotions["Fears_Confirmed"] + abs(
                                                                           desirability)))
        elif prospect_status == "disconfirmed":
            if desirability > 0:
                self.active_emotions["Disappointment"] = max(0.0, min(1.0, self.active_emotions[
                    "Disappointment"] + desirability * mood_multiplier))
            elif desirability < 0:
                self.active_emotions["Relief"] = max(0.0, min(1.0, self.active_emotions["Relief"] + abs(desirability)))
        else:  # "none"
            if desirability > 0:
                joy_spark = (desirability * (1.0 + trait_E)) * (2.0 - mood_multiplier)
                self.active_emotions["Joy"] = max(0.0, min(1.0, self.active_emotions["Joy"] + joy_spark))
                mood_layer.apply_physiological_impact(delta_v=joy_spark * 0.2, delta_a=joy_spark * 0.1)
            elif desirability < 0:
                # 🌟 放弃与隐忍抉择：这里受到了经过信念过滤后的 mood_multiplier 拦截影响
                distress_spark = (abs(desirability) * (1.0 + trait_N)) * mood_multiplier
                self.active_emotions["Distress"] = max(0.0, min(1.0, self.active_emotions["Distress"] + distress_spark))
                mood_layer.apply_physiological_impact(delta_v=-distress_spark * 0.2, delta_a=distress_spark * 0.1)

        # 1.3 他人遭遇
        if other_desirability != 0:
            if other_relationship >= 0:
                if other_desirability > 0:
                    self.active_emotions["Happy_For"] = max(0.0, min(1.0, self.active_emotions[
                        "Happy_For"] + other_desirability * trait_A))
                else:
                    self.active_emotions["Pity"] = max(0.0, min(1.0, self.active_emotions["Pity"] + abs(
                        other_desirability) * trait_A))
            else:
                if other_desirability > 0:
                    self.active_emotions["Resentment"] = max(0.0, min(1.0, self.active_emotions[
                        "Resentment"] + other_desirability * mood_multiplier))
                else:
                    self.active_emotions["Gloating"] = max(0.0, min(1.0, self.active_emotions["Gloating"] + abs(
                        other_desirability)))

        # 2. 行为类
        if blameworthiness > 0:
            self.active_emotions["Admiration"] = max(0.0,
                                                     min(1.0, self.active_emotions["Admiration"] + blameworthiness))
        elif blameworthiness < 0:
            self.active_emotions["Reproach"] = max(0.0, min(1.0, self.active_emotions["Reproach"] + abs(
                blameworthiness) * mood_multiplier))

        if self_blameworthiness > 0:
            self.active_emotions["Pride"] = max(0.0, min(1.0, self.active_emotions[
                "Pride"] + self_blameworthiness * trait_C))
        elif self_blameworthiness < 0:
            self.active_emotions["Shame"] = max(0.0, min(1.0, self.active_emotions["Shame"] + abs(
                self_blameworthiness) * trait_N))

        # 3. 对象属性类
        if appealingness > 0:
            self.active_emotions["Liking"] = max(0.0,
                                                 min(1.0, self.active_emotions["Liking"] + appealingness * trait_O))
        elif appealingness < 0:
            self.active_emotions["Disliking"] = max(0.0, min(1.0, self.active_emotions["Disliking"] + abs(
                appealingness) * trait_N))

        # 4. 复合类
        if desirability > 0 and blameworthiness > 0:
            self.active_emotions["Gratitude"] = max(0.0, min(1.0, self.active_emotions["Gratitude"] + (
                        desirability + blameworthiness) / 2 * trait_A))
        if desirability < 0 and blameworthiness < 0:
            anger_spark = ((abs(desirability) + abs(blameworthiness)) / 2) * (1.5 - trait_A) * mood_multiplier
            self.active_emotions["Anger"] = max(0.0, min(1.0, self.active_emotions["Anger"] + anger_spark))
        if desirability > 0 and self_blameworthiness > 0:
            self.active_emotions["Gratification"] = max(0.0, min(1.0, self.active_emotions["Gratification"] + (
                        desirability + self_blameworthiness) / 2))
        if desirability < 0 and self_blameworthiness < 0:
            self.active_emotions["Remorse"] = max(0.0, min(1.0, self.active_emotions["Remorse"] + (
                        abs(desirability) + abs(self_blameworthiness)) / 2 * trait_N))
