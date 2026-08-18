# filename: emotion.py

class OCCEmotionLayer:
    """
    终极完全版即时情感层：
    1. 严格完备地实现了标准 OCC 模型的全部 22 种具体情感。
    2. 深度融入了 PSI 理论中的“前瞻性未来愿景拦截机制”与“内在必胜信心过滤”。
    """

    def __init__(self):
        # 初始化全部 22 种情感状态值（范围 0.0 到 1.0）
        self.active_emotions = {
            # --- 1. 与事件结果相关的情感 (Event-Based) ---
            # 1.1 针对自身 (Well-Being)
            "Joy": 0.0,  # 高兴
            "Distress": 0.0,  # 悲伤

            # 1.2 针对未来预期 (Prospect)
            "Hope": 0.0,  # 希望
            "Fear": 0.0,  # 恐惧
            "Satisfaction": 0.0,  # 满足
            "Fears_Confirmed": 0.0,  # 恐惧证实
            "Relief": 0.0,  # 宽慰
            "Disappointment": 0.0,  # 失望

            # 1.3 针对他人遭遇 (Fortunes of Others)
            "Happy_For": 0.0,  # 为他人高兴
            "Pity": 0.0,  # 怜悯/同情
            "Resentment": 0.0,  # 怨恨/嫉妒
            "Gloating": 0.0,  # 幸灾乐祸

            # --- 2. 与智能体行为相关的情感 (Agent-Based) ---
            "Pride": 0.0,  # 自豪（自身）
            "Shame": 0.0,  # 羞耻（自身）
            "Admiration": 0.0,  # 仰慕（他人）
            "Reproach": 0.0,  # 责责（他人）

            # --- 3. 与对象属性相关的情感 (Object-Based) ---
            "Liking": 0.0,  # 喜欢/爱慕
            "Disliking": 0.0,  # 厌恶/反感

            # --- 4. 复合情感 (Compound Emotions: 行为 + 结果) ---
            "Gratitude": 0.0,  # 感激 (Admiration + Joy)
            "Anger": 0.0,  # 生气 (Reproach + Distress)
            "Gratification": 0.0,  # 欣慰/得意 (Pride + Joy)
            "Remorse": 0.0  # 悔恨/自责 (Shame + Distress)
        }
        self.decay_rate = 0.25

    def update_decay(self):
        """时间步 tick：所有 22 种短期情感高频自然消退"""
        for emo in self.active_emotions:
            self.active_emotions[emo] = max(0.0, self.active_emotions[emo] - self.decay_rate)

    def trigger_internal_spark(self, name: str, intensity: float):
        """API Hook: 允许强制注入特定情绪值"""
        if name in self.active_emotions:
            self.active_emotions[name] = max(0.0, min(1.0, self.active_emotions[name] + intensity))

    def calculate_occ_spikes(self, appraisal: dict, personality_layer, mood_layer):
        """
        核心评估矩阵：绝无省略地吞吐 22 种情感，并运用心理信念进行输入拦截。
        """
        # --- 基础认知评估参数提取 ---
        desirability = appraisal.get("desirability", 0.0)  # 事件即时合意度 [-1.0, 1.0]
        future_desirability = appraisal.get("future_desirability", 0.0)  # 🌟 远期宏大目标合意度 [0.0, 1.0]
        prospect_status = appraisal.get("prospect_status",
                                        "none")  # 预期状态: "none", "expected", "confirmed", "disconfirmed"

        other_desirability = appraisal.get("other_desirability", 0.0)  # 该事件对别人的合意度 [-1.0, 1.0]
        other_relationship = appraisal.get("other_relationship", 0.0)  # 我与该他人的关系亲疏度 [-1.0, 1.0]

        blameworthiness = appraisal.get("blameworthiness", 0.0)  # 他人行为的应受责备度/赞赏度 [-1.0, 1.0]
        self_blameworthiness = appraisal.get("self_blameworthiness", 0.0)  # 自身行为的应受责备度/赞赏度 [-1.0, 1.0]

        appealingness = appraisal.get("appealingness", 0.0)  # 对象属性的吸引力/排斥力 [-1.0, 1.0]

        # --- 提取静态性格基因与动态心情过滤器 ---
        # 🌟 注意：这里的 mood_multiplier 已经在升级版的 mood.py 中被 Competence（必胜信心）弱化了
        mood_multiplier = mood_layer.get_mood_multiplier()
        trait_O = personality_layer.get_trait("O")
        trait_C = personality_layer.get_trait("C")
        trait_E = personality_layer.get_trait("E")
        trait_A = personality_layer.get_trait("A")
        trait_N = personality_layer.get_trait("N")

        # === 🌟 核心机制加入：前瞻性未来评估（博取美好未来的必胜信念） ===
        if future_desirability > 0:
            # 即使眼前再难，只要认知到未来有宏大价值，就会爆发强烈的 Hope，去浇灌心情层的信念护盾
            hope_spark = future_desirability * (1.0 + trait_E) * (1.5 - trait_N)
            self.active_emotions["Hope"] = max(0.0, min(1.0, self.active_emotions["Hope"] + hope_spark))

        # =========================================================================
        # 类别 1: 与事件结果相关的情感 (Event-Based)
        # =========================================================================

        # 1.1 自身结果 & 1.2 预期结果 (Prospect)
        if prospect_status == "expected":
            # 针对未来预期未发生的情况
            if desirability > 0:
                hope_spark = (desirability * (1.0 + trait_E)) * (2.0 - mood_multiplier)
                self.active_emotions["Hope"] = max(0.0, min(1.0, self.active_emotions["Hope"] + hope_spark))
            elif desirability < 0:
                fear_spark = (abs(desirability) * (1.0 + trait_N)) * mood_multiplier
                self.active_emotions["Fear"] = max(0.0, min(1.0, self.active_emotions["Fear"] + fear_spark))

        elif prospect_status == "confirmed":
            # 预期被证实
            if desirability > 0:
                sat_spark = desirability * (1.0 + trait_E)
                self.active_emotions["Satisfaction"] = max(0.0,
                                                           min(1.0, self.active_emotions["Satisfaction"] + sat_spark))
            elif desirability < 0:
                fc_spark = abs(desirability) * (1.0 + trait_N)
                self.active_emotions["Fears_Confirmed"] = max(0.0, min(1.0, self.active_emotions[
                    "Fears_Confirmed"] + fc_spark))

        elif prospect_status == "disconfirmed":
            # 预期被打破/落空
            if desirability > 0:
                dis_spark = desirability * (1.0 + trait_N) * mood_multiplier
                self.active_emotions["Disappointment"] = max(0.0, min(1.0, self.active_emotions[
                    "Disappointment"] + dis_spark))
            elif desirability < 0:
                rel_spark = abs(desirability) * (1.0 + trait_E) * (2.0 - mood_multiplier)
                self.active_emotions["Relief"] = max(0.0, min(1.0, self.active_emotions["Relief"] + rel_spark))

        else:  # prospect_status == "none" (即时发生的事情)
            if desirability > 0:
                joy_spark = (desirability * (1.0 + trait_E)) * (2.0 - mood_multiplier)
                self.active_emotions["Joy"] = max(0.0, min(1.0, self.active_emotions["Joy"] + joy_spark))
                mood_layer.apply_physiological_impact(delta_v=joy_spark * 0.2, delta_a=joy_spark * 0.1)
            elif desirability < 0:
                # 🌟 隐忍核心：如果心中饱含必胜信心，这里的 mood_multiplier 就会很小，
                # 从而导致即时痛苦（Distress）和接下来的生气（Anger）爆发值被极大地压制！
                distress_spark = (abs(desirability) * (1.0 + trait_N)) * mood_multiplier
                self.active_emotions["Distress"] = max(0.0, min(1.0, self.active_emotions["Distress"] + distress_spark))
                mood_layer.apply_physiological_impact(delta_v=-distress_spark * 0.2, delta_a=distress_spark * 0.1)

        # 1.3 他人遭遇 (Fortunes of Others)
        if other_desirability != 0:
            if other_relationship >= 0:  # 朋友遇到了好事/坏事
                if other_desirability > 0:
                    hf_spark = other_desirability * (1.0 + trait_A) * other_relationship
                    self.active_emotions["Happy_For"] = max(0.0, min(1.0, self.active_emotions["Happy_For"] + hf_spark))
                else:
                    pity_spark = abs(other_desirability) * (1.0 + trait_A) * other_relationship
                    self.active_emotions["Pity"] = max(0.0, min(1.0, self.active_emotions["Pity"] + pity_spark))
            else:  # 敌人遇到了好事/坏事
                abs_rel = abs(other_relationship)
                if other_desirability > 0:
                    res_spark = other_desirability * (1.5 - trait_A) * abs_rel * mood_multiplier
                    self.active_emotions["Resentment"] = max(0.0,
                                                             min(1.0, self.active_emotions["Resentment"] + res_spark))
                else:
                    gloat_spark = abs(other_desirability) * (1.5 - trait_A) * abs_rel * (2.0 - mood_multiplier)
                    self.active_emotions["Gloating"] = max(0.0,
                                                           min(1.0, self.active_emotions["Gloating"] + gloat_spark))

        # =========================================================================
        # 类别 2: 与智能体行为相关的情感 (Agent-Based)
        # =========================================================================
        # 2.1 他人行为评估
        if blameworthiness > 0:
            adm_spark = blameworthiness * (1.0 + trait_A)
            self.active_emotions["Admiration"] = max(0.0, min(1.0, self.active_emotions["Admiration"] + adm_spark))
        elif blameworthiness < 0:
            rep_spark = abs(blameworthiness) * (1.5 - trait_A) * mood_multiplier
            self.active_emotions["Reproach"] = max(0.0, min(1.0, self.active_emotions["Reproach"] + rep_spark))

        # 2.2 自身行为评估
        if self_blameworthiness > 0:
            pride_spark = self_blameworthiness * (1.0 + trait_C)
            self.active_emotions["Pride"] = max(0.0, min(1.0, self.active_emotions["Pride"] + pride_spark))
        elif self_blameworthiness < 0:
            shame_spark = abs(self_blameworthiness) * (1.0 + trait_N) * mood_multiplier
            self.active_emotions["Shame"] = max(0.0, min(1.0, self.active_emotions["Shame"] + shame_spark))

        # =========================================================================
        # 类别 3: 与对象属性相关的情感 (Object-Based) —— 绝无丢弃，完整保留
        # =========================================================================
        if appealingness > 0:
            like_spark = appealingness * (1.0 + trait_O) * (2.0 - mood_multiplier)
            self.active_emotions["Liking"] = max(0.0, min(1.0, self.active_emotions["Liking"] + like_spark))
        elif appealingness < 0:
            dislike_spark = abs(appealingness) * (1.0 + trait_N) * mood_multiplier
            self.active_emotions["Disliking"] = max(0.0, min(1.0, self.active_emotions["Disliking"] + dislike_spark))
        # =========================================================================
        # 类别 4: 复合情感 (Compound Emotions - 联合评估)
        # =========================================================================
        # 4.1 别人的行为 + 对我的结果# 他人让我获益(desirability > 0) 且 其行为值得赞赏(blameworthiness > 0) -> 感激 (Gratitude)
        if desirability > 0 and blameworthiness > 0:
            grat_spark = ((desirability + blameworthiness) / 2) * (1.0 + trait_A)
            self.active_emotions["Gratitude"] = max(0.0, min(1.0, self.active_emotions["Gratitude"] + grat_spark))
        # 他人让我受损(desirability < 0) 且 其行为应受责备(blameworthiness < 0) -> 生气 (Anger)
        if desirability < 0 and blameworthiness < 0:
            # 🌟 隐忍联动：Anger 也会因为心中强大的必胜信念（mood_multiplier变小）而大幅降低
            anger_spark = ((abs(desirability) + abs(blameworthiness)) / 2) * (1.5 - trait_A) * mood_multiplier
            self.active_emotions["Anger"] = max(0.0, min(1.0, self.active_emotions["Anger"] + anger_spark))
        # 4.2 自己的行为 + 对我的结果# 自己让我获益(desirability > 0) 且 行为值得自豪(self_blameworthiness > 0) -> 欣慰/得意 (Gratification)
        if desirability > 0 and self_blameworthiness > 0:
            gratification_spark = ((desirability + self_blameworthiness) / 2) * (1.0 + trait_C)
            self.active_emotions["Gratification"] = max(0.0, min(1.0, self.active_emotions["Gratification"] + gratification_spark))
        # 自己让我受损(desirability < 0) 且 行为令我羞耻(self_blameworthiness < 0) -> 悔恨/自责 (Remorse)
        if desirability < 0 and self_blameworthiness < 0:
            remorse_spark = ((abs(desirability) + abs(self_blameworthiness)) / 2) * (1.0 + trait_C) * (1.0 + trait_N) * mood_multiplier
            self.active_emotions["Remorse"] = max(0.0, min(1.0, self.active_emotions["Remorse"] + remorse_spark))