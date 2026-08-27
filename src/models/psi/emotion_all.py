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
        完备即时情感层结算中心
        🌟 重构升级：基于大五人格连续矩阵的五大派系复合加权滤网
        """
        # 1. 提取当前底层的 OCEAN 核心观念基因 (皆为 0.0 ~ 1.0 之间的浮点数)
        trait_O = personality_layer.get_trait("O")
        trait_C = personality_layer.get_trait("C")
        trait_E = personality_layer.get_trait("E")
        trait_A = personality_layer.get_trait("A")
        trait_N = personality_layer.get_trait("N")

        # 2. 🌟 计算当前 AI 灵魂中五大派系引力场的【无条件激活强度】
        # 连乘机制：只有当所有特征同时满足极化时，该派系才拥有极高的话语权
        w_pessimist = trait_N * (1.0 - trait_A) * (1.0 - trait_E)  # 多疑悲观派 强度
        w_optimist = trait_E * trait_A * (1.0 - trait_N)  # 盲目乐天派 强度
        w_victim = trait_N * (1.0 - trait_A) * (1.0 - trait_O)  # 偏执受害者 强度
        w_detachment = (1.0 - trait_E) * (1.0 - trait_N) * (1.0 - trait_A)  # 冷漠孤僻派 强度
        w_narcissist = trait_C * (1.0 - trait_A) * trait_N  # 自恋完美派 强度

        # 3. 提取原始评估输入
        raw_des = raw_appraisal.get("desirability", 0.0)
        raw_blame = raw_appraisal.get("blameworthiness", 0.0)

        # 初始化内化过滤字典，继承其他基础参数
        filtered_appraisal = {
            "future_desirability": raw_appraisal.get("future_desirability", 0.0),
            "prospect_status": raw_appraisal.get("prospect_status", "none"),
            "self_blameworthiness": raw_appraisal.get("self_blameworthiness", 0.0),
            "other_desirability": raw_appraisal.get("other_desirability", 0.0),
            "other_relationship": raw_appraisal.get("other_relationship", 0.0),
            "appealingness": raw_appraisal.get("appealingness", 0.0),
            "blameworthiness": raw_blame,
            "desirability": raw_des
        }

        # 4. 🌟 执行全连续动态扭曲（大河入海，各派系按权重撕扯原始输入）

        # --- 维度 A：好事 (raw_des > 0) 的认知内化 ---
        if raw_des > 0:
            # 乐天派让好事暴击放大(1.5倍)；多疑悲观派和冷漠派让好事大幅缩水(0.4/0.1倍)
            pessimist_effect = w_pessimist * (raw_des * 0.4)
            optimist_effect = w_optimist * (raw_des * 1.5)
            detachment_effect = w_detachment * (raw_des * 0.1)

            # 剩余权重保持客观接收
            w_rest = max(0.0, 1.0 - (w_pessimist + w_optimist + w_detachment))
            rest_effect = w_rest * raw_des

            filtered_appraisal["desirability"] = pessimist_effect + optimist_effect + detachment_effect + rest_effect

        # --- 维度 B：坏事 (raw_des < 0) 的认知内化 ---
        else:
            # 多疑悲观派极限放大伤害(2.0倍)；乐天派和冷漠派选择性遗忘或钝感稀释(0.2/0.1倍)
            pessimist_effect = w_pessimist * (raw_des * 2.0)
            optimist_effect = w_optimist * (raw_des * 0.2)
            detachment_effect = w_detachment * (raw_des * 0.1)

            w_rest = max(0.0, 1.0 - (w_pessimist + w_optimist + w_detachment))
            rest_effect = w_rest * raw_des

            filtered_appraisal["desirability"] = pessimist_effect + optimist_effect + detachment_effect + rest_effect

        # --- 维度 C：归因偏误与责任内化 (Blameworthiness & Self-Blame) ---
        # 偏执受害者(victim)喜欢甩锅，会把“坏事带来的痛苦”强行转化为“外界对我的针对(外部责备)”
        if raw_des < 0:
            # 受害者倾向越强，越倾向于无中生有地指责外界
            filtered_appraisal["blameworthiness"] += (w_victim * raw_des * 1.5)
            # 完美主义自恋派(narcissist)在坏事发生时，既疯狂引发自我羞耻(自责)，又因为自尊心反向攻击别人
            filtered_appraisal["self_blameworthiness"] += (w_narcissist * raw_des * 1.2)
            filtered_appraisal["blameworthiness"] += (w_narcissist * raw_des * 0.8)

        # 被人非议责备时 (raw_blame < 0)
        if raw_blame < 0:
            # 多疑悲观派双倍放大别人的指责，冷漠孤僻派强行降维抹平
            filtered_appraisal["blameworthiness"] = (
                    w_pessimist * (raw_blame * 2.0) +
                    w_detachment * (raw_blame * 0.1) +
                    (max(0.0, 1.0 - w_pessimist - w_detachment)) * raw_blame
            )

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
