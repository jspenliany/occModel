# filename: emotion.py

class OCCEmotionLayer:
    """
    完备的即时情感层：严格实现 OCC 情感模型标准的全部 22 种具体情感。
    分类依据：事件结果（12种）、智能体行为（4种）、对象属性（2种）、复合情感（4种）。
    """

    def __init__(self):
        # 严格初始化全部 22 种情感状态值（范围 0.0 到 1.0）
        self.active_emotions = {
            # --- 1. 与事件结果相关的情感 (Event-Based) ---
            # 1.1 针对自身 (Well-Being)
            "Joy": 0.0,  # 高兴：对合意事件的愉悦
            "Distress": 0.0,  # 悲伤：对不合意事件的沮丧

            # 1.2 针对未来预期 (Prospect)
            "Hope": 0.0,  # 希望：对合意事件可能发生的预期
            "Fear": 0.0,  # 恐惧：对不合意事件可能发生的预期
            "Satisfaction": 0.0,  # 满足：对合意预期得到证实的愉悦
            "Fears_Confirmed": 0.0,  # 恐惧证实：对不合意预期得到证实的沮丧
            "Relief": 0.0,  # 宽慰：对不合意预期未发生的愉悦
            "Disappointment": 0.0,  # 失望：对合意预期未发生的沮丧

            # 1.3 针对他人遭遇 (Fortunes of Others)
            "Happy_For": 0.0,  # 为他人高兴：别人遇到了好事情
            "Pity": 0.0,  # 怜悯/同情：别人遇到了坏事情
            "Resentment": 0.0,  # 怨恨/嫉妒：别人遇到了好事情（但我不平衡）
            "Gloating": 0.0,  # 幸灾乐祸：别人遇到了坏事情（但我很高兴）

            # --- 2. 与智能体行为相关的情感 (Agent-Based) ---
            # 2.1 针对自身行为 (Self)
            "Pride": 0.0,  # 自豪：赞赏自己的高尚/正确行为
            "Shame": 0.0,  # 羞耻：责备自己的错误/低劣行为

            # 2.2 针对他人行为 (Other)
            "Admiration": 0.0,  # 仰慕：赞赏他人的高尚/正确行为
            "Reproach": 0.0,  # 责备：非议他人的错误/低劣行为

            # --- 3. 与对象属性相关的情感 (Object-Based) ---
            "Liking": 0.0,  # 喜欢/爱慕：被吸引、觉得对象很有魅力
            "Disliking": 0.0,  # 厌恶/反感：被排斥、觉得对象很丑陋/恶心

            # --- 4. 复合情感 (Compound Emotions: 行为 + 结果) ---
            # 4.1 针对他人行为导致的自身结果
            "Gratitude": 0.0,  # 感激：他人做出了值得赞赏的事 + 带给我合意的结果 (Admiration + Joy)
            "Anger": 0.0,  # 生气：他人做出了应受责备的事 + 带给我不合意的结果 (Reproach + Distress)

            # 4.2 针对自己行为导致的自身结果
            "Gratification": 0.0,  # 欣慰/得意：自己做出了正确的事 + 带来了合意的结果 (Pride + Joy)
            "Remorse": 0.0  # 悔恨：自己做出了错误的事 + 带来了不合意的结果 (Shame + Distress)
        }

        # 情感衰减率：短期情绪在 Tick 推进时自然流逝的速度
        self.decay_rate = 0.25

    def update_decay(self):
        """时间步 tick：所有 22 种短期情感高频自然消退"""
        for emo in self.active_emotions:
            self.active_emotions[emo] = max(0.0, self.active_emotions[emo] - self.decay_rate)

    def trigger_internal_spark(self, name: str, intensity: float):
        """API Hook: 允许业务层或剧情本绕过评估，直接强制注入/增加某种特定的情绪值"""
        if name in self.active_emotions:
            self.active_emotions[name] = max(0.0, min(1.0, self.active_emotions[name] + intensity))

    def calculate_occ_spikes(self, appraisal: dict, personality_layer, mood_layer):
        """
        全量 OCC 评估函数：
        根据外部输入的丰富 appraisal 认知字典，结合性格(OCEAN)和心情过滤器，
        全量吞吐并计算 22 种情感的瞬间脉冲（Spikes）。
        """
        # --- 基础认知评估参数提取 ---
        desirability = appraisal.get("desirability", 0.0)  # 事件合意度 [-1.0, 1.0]
        prospect_status = appraisal.get("prospect_status",
                                        "none")  # 预期状态: "none", "expected", "confirmed", "disconfirmed"

        other_desirability = appraisal.get("other_desirability", 0.0)  # 该事件对别人的合意度 [-1.0, 1.0]
        other_relationship = appraisal.get("other_relationship", 0.0)  # 我与该他人的关系亲疏度 [-1.0, 1.0] (正数为朋友，负数为敌人)

        blameworthiness = appraisal.get("blameworthiness", 0.0)  # 他人行为的应受责备度/赞赏度 [-1.0, 1.0] (正数赞赏，负数责备)
        self_blameworthiness = appraisal.get("self_blameworthiness", 0.0)  # 自身行为的应受责备度/赞赏度 [-1.0, 1.0]

        appealingness = appraisal.get("appealingness", 0.0)  # 对象属性的吸引力/排斥力 [-1.0, 1.0]

        # --- 提取性格与心情过滤器 ---
        mood_multiplier = mood_layer.get_mood_multiplier()
        trait_O = personality_layer.get_trait("O")
        trait_C = personality_layer.get_trait("C")
        trait_E = personality_layer.get_trait("E")
        trait_A = personality_layer.get_trait("A")
        trait_N = personality_layer.get_trait("N")

        # =========================================================================
        # 类别 1: 与事件结果相关的情感 (Event-Based)
        # =========================================================================

        # 1.1 自身结果 (Well-Being) & 1.2 预期结果 (Prospect)
        if prospect_status == "expected":
            # 未发生的预期：触发 希望 / 恐惧
            if desirability > 0:
                hope_spark = (desirability * (1.0 + trait_E)) * (2.0 - mood_multiplier)
                self.active_emotions["Hope"] = max(0.0, min(1.0, self.active_emotions["Hope"] + hope_spark))
            elif desirability < 0:
                fear_spark = (abs(desirability) * (1.0 + trait_N)) * mood_multiplier
                self.active_emotions["Fear"] = max(0.0, min(1.0, self.active_emotions["Fear"] + fear_spark))

        elif prospect_status == "confirmed":
            # 预期被证实：触发 满足 / 恐惧证实
            if desirability > 0:
                sat_spark = desirability * (1.0 + trait_E)
                self.active_emotions["Satisfaction"] = max(0.0,
                                                           min(1.0, self.active_emotions["Satisfaction"] + sat_spark))
            elif desirability < 0:
                fc_spark = abs(desirability) * (1.0 + trait_N)
                self.active_emotions["Fears_Confirmed"] = max(0.0, min(1.0, self.active_emotions[
                    "Fears_Confirmed"] + fc_spark))

        elif prospect_status == "disconfirmed":
            # 预期被落空（打破）：触发 宽慰 / 失望
            if desirability > 0:  # 原本期待的好事没发生 -> 失望
                dis_spark = desirability * (1.0 + trait_N) * mood_multiplier
                self.active_emotions["Disappointment"] = max(0.0, min(1.0, self.active_emotions[
                    "Disappointment"] + dis_spark))
            elif desirability < 0:  # 原本担忧的坏事没发生 -> 宽慰
                rel_spark = abs(desirability) * (1.0 + trait_E) * (2.0 - mood_multiplier)
                self.active_emotions["Relief"] = max(0.0, min(1.0, self.active_emotions["Relief"] + rel_spark))

        else:  # prospect_status == "none" (即时发生的确定事件)
            # 触发 基础高兴 / 基础悲伤
            if desirability > 0:
                joy_spark = (desirability * (1.0 + trait_E)) * (2.0 - mood_multiplier)
                self.active_emotions["Joy"] = max(0.0, min(1.0, self.active_emotions["Joy"] + joy_spark))
                mood_layer.apply_physiological_impact(delta_v=joy_spark * 0.2, delta_a=joy_spark * 0.1)
            elif desirability < 0:
                distress_spark = (abs(desirability) * (1.0 + trait_N)) * mood_multiplier
                self.active_emotions["Distress"] = max(0.0, min(1.0, self.active_emotions["Distress"] + distress_spark))
                mood_layer.apply_physiological_impact(delta_v=-distress_spark * 0.2, delta_a=distress_spark * 0.1)

        # 1.3 他人遭遇 (Fortunes of Others)
        if other_desirability != 0:
            if other_relationship >= 0:  # 对方是我的朋友/亲近的人
                if other_desirability > 0:  # 朋友遇到了好事 -> 为他人高兴
                    hf_spark = other_desirability * (1.0 + trait_A) * other_relationship
                    self.active_emotions["Happy_For"] = max(0.0, min(1.0, self.active_emotions["Happy_For"] + hf_spark))
                else:  # 朋友遇到了坏事 -> 同情怜悯
                    pity_spark = abs(other_desirability) * (1.0 + trait_A) * other_relationship
                    self.active_emotions["Pity"] = max(0.0, min(1.0, self.active_emotions["Pity"] + pity_spark))
            else:  # 对方是我的敌人/讨厌的人 (other_relationship < 0)
                abs_rel = abs(other_relationship)
                if other_desirability > 0:  # 敌人遇到了好事 -> 怨恨嫉妒
                    res_spark = other_desirability * (1.5 - trait_A) * abs_rel * mood_multiplier
                    self.active_emotions["Resentment"] = max(0.0,
                                                             min(1.0, self.active_emotions["Resentment"] + res_spark))
                else:  # 敌人遇到了坏事 -> 幸灾乐祸
                    gloat_spark = abs(other_desirability) * (1.5 - trait_A) * abs_rel * (2.0 - mood_multiplier)
                    self.active_emotions["Gloating"] = max(0.0,
                                                           min(1.0, self.active_emotions["Gloating"] + gloat_spark))

        # =========================================================================
        # 类别 2: 与智能体行为相关的情感 (Agent-Based)
        # =========================================================================

        # 2.1 他人行为评估
        if blameworthiness > 0:  # 他人做出了值得赞赏的行为 -> 仰慕
            adm_spark = blameworthiness * (1.0 + trait_A)
            self.active_emotions["Admiration"] = max(0.0, min(1.0, self.active_emotions["Admiration"] + adm_spark))
        elif blameworthiness < 0:  # 他人做出了应受责备的行为 -> 非议/责备
            rep_spark = abs(blameworthiness) * (1.5 - trait_A) * mood_multiplier
            self.active_emotions["Reproach"] = max(0.0, min(1.0, self.active_emotions["Reproach"] + rep_spark))

        # 2.2 自身行为评估
        if self_blameworthiness > 0:  # 自己做出了正确自律的行为 -> 自豪
            pride_spark = self_blameworthiness * (1.0 + trait_C)
            self.active_emotions["Pride"] = max(0.0, min(1.0, self.active_emotions["Pride"] + pride_spark))
        elif self_blameworthiness < 0:  # 自己做出了错误内疚的行为 -> 羞耻
            shame_spark = abs(self_blameworthiness) * (1.0 + trait_N) * mood_multiplier
            self.active_emotions["Shame"] = max(0.0, min(1.0, self.active_emotions["Shame"] + shame_spark))

        # =========================================================================
        # 类别 3: 与对象属性相关的情感 (Object-Based)
        # =========================================================================
        if appealingness > 0:  # 遇到有吸引力、美好的事物 -> 喜欢
            like_spark = appealingness * (1.0 + trait_O) * (2.0 - mood_multiplier)
            self.active_emotions["Liking"] = max(0.0, min(1.0, self.active_emotions["Liking"] + like_spark))
        elif appealingness < 0:  # 遇到排斥、不快的事物 -> 厌恶
            dislike_spark = abs(appealingness) * (1.0 + trait_N) * mood_multiplier
            self.active_emotions["Disliking"] = max(0.0, min(1.0, self.active_emotions["Disliking"] + dislike_spark))
        # =========================================================================
        # 类别 4: 复合情感 (Compound Emotions - 联合评估)
        # =========================================================================
        # 4.1 别人的行为 + 对我的结果# 他人让我获益(desirability > 0) 且 其行为值得赞赏(blameworthiness > 0) -> 感激 (Gratitude)
        if desirability > 0 and blameworthiness > 0:
            grat_spark = (desirability + blameworthiness) / 2 * (1.0 + trait_A)
            self.active_emotions["Gratitude"] = max(0.0, min(1.0, self.active_emotions["Gratitude"] + grat_spark))
        # 他人让我受损(desirability < 0) 且 其行为应受责备(blameworthiness < 0) -> 生气 (Anger)
        if desirability < 0 and blameworthiness < 0:
            anger_spark = (abs(desirability) + abs(blameworthiness)) / 2 * (1.5 - trait_A) * mood_multiplier
            self.active_emotions["Anger"] = max(0.0, min(1.0, self.active_emotions["Anger"] + anger_spark))
        # 4.2 自己的行为 + 对我的结果# 自己让我获益(desirability > 0) 且 行为值得自豪(self_blameworthiness > 0) -> 欣慰/得意 (Gratification)
        if desirability > 0 and self_blameworthiness > 0:
            gratification_spark = (desirability + self_blameworthiness) / 2 * (1.0 + trait_C)
            self.active_emotions["Gratification"] = max(0.0, min(1.0, self.active_emotions["Gratification"] + gratification_spark))
        # 自己让我受损(desirability < 0) 且 行为令我羞耻(self_blameworthiness < 0) -> 悔恨/自责 (Remorse)
        if desirability < 0 and self_blameworthiness < 0:
            remorse_spark = (abs(desirability) + abs(self_blameworthiness)) / 2 * (1.0 + trait_C) * (1.0 + trait_N) * mood_multiplier
            self.active_emotions["Remorse"] = max(0.0, min(1.0, self.active_emotions["Remorse"] + remorse_spark))