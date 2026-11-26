# filename: emotion_all.py
from typing import Dict
from src.logger_singleton import logger


class _DirectedEmotionProxy(dict):
    """
    向后兼容的实时情绪字典代理视图：
    - 读取/遍历时展示 `global_emotions + directed_emotions[last_speaker_id]` 的完整 22 维快照；
    - 外部直接赋值（如单测 `e_layer.active_emotions["Anger"] = 0.0` 或 `["Hope"] = 0.8`）时，
      自动路由写回底层全局池或当前 `last_speaker_id` 专属靶向桶。
    """

    def __init__(self, owner: "OCCEmotionLayer"):
        super().__init__()
        self._owner = owner

    def sync_from_owner(self) -> None:
        merged = self._owner.get_emotions_for_speaker(self._owner.last_speaker_id)
        super().clear()
        super().update(merged)

    def __setitem__(self, key: str, value: float) -> None:
        fval = float(value)
        super().__setitem__(key, fval)
        self._owner._set_emotion_value(key, fval, speaker_id=self._owner.last_speaker_id)

    def update(self, *args, **kwargs) -> None:
        incoming = dict(*args, **kwargs)
        for k, v in incoming.items():
            self[k] = v


class OCCEmotionLayer:
    """
    完备即时情感层（双池指向性隔离升级版）：
    1. 实现全量 22 种 OCC 情感：
       - 12 种【自身境遇与自我归因情绪 (GLOBAL_EMOTION_NAMES)】：全局共享，跨对话者延续；
       - 10 种【人际靶向情绪 (DIRECTED_EMOTION_NAMES)】：按 speaker_id 独立分桶存储，彻底消除跨人串味。
    2. 实现基于大五人格连续矩阵的五大派系“观念内化过滤”扭曲网。
    3. 支持提取针对第三方的残余负面摩擦（External Lingering Emotions），供下游转化为“合理吐槽而非误伤眼前人”。
    """
    ALL_EMOTION_NAMES = [
        "Joy", "Distress", "Hope", "Fear", "Satisfaction", "Fears_Confirmed",
        "Relief", "Disappointment", "Happy_For", "Pity", "Resentment", "Gloating",
        "Pride", "Shame", "Admiration", "Reproach", "Liking", "Disliking",
        "Gratitude", "Anger", "Gratification", "Remorse"
    ]

    # 12 种无特定外部人际靶向的自身境遇/自我评价情绪（跨人延续）
    GLOBAL_EMOTION_NAMES = (
        "Joy", "Distress", "Hope", "Fear", "Satisfaction", "Fears_Confirmed",
        "Relief", "Disappointment", "Pride", "Shame", "Gratification", "Remorse"
    )

    # 10 种强对象指向性的人际情绪（按 speaker_id 分桶物理隔离）
    DIRECTED_EMOTION_NAMES = (
        "Happy_For", "Pity", "Resentment", "Gloating",
        "Admiration", "Reproach", "Liking", "Disliking",
        "Gratitude", "Anger"
    )

    # 跨对话者切换时需要做“归因隔离/可向亲密关系吐槽”提示的负向人际情绪
    NEGATIVE_DIRECTED_NAMES = ("Anger", "Reproach", "Disliking", "Resentment")

    def __init__(self):
        self.global_emotions: Dict[str, float] = {name: 0.0 for name in self.GLOBAL_EMOTION_NAMES}
        self.directed_emotions: Dict[str, Dict[str, float]] = {}
        self.last_speaker_id: str = "unknown_stranger"
        self.decay_rate: float = 0.25

        # 维护兼容旧调用方的动态代理字典
        self.active_emotions: _DirectedEmotionProxy = _DirectedEmotionProxy(self)
        self.active_emotions.sync_from_owner()

    def _ensure_speaker_bucket(self, speaker_id: str) -> Dict[str, float]:
        uid = speaker_id or "unknown_stranger"
        if uid not in self.directed_emotions:
            self.directed_emotions[uid] = {name: 0.0 for name in self.DIRECTED_EMOTION_NAMES}
        return self.directed_emotions[uid]

    def _set_emotion_value(self, emo_name: str, value: float, speaker_id: str = "unknown_stranger") -> None:
        clamped = max(0.0, min(1.0, float(value)))
        if emo_name in self.GLOBAL_EMOTION_NAMES:
            self.global_emotions[emo_name] = clamped
        elif emo_name in self.DIRECTED_EMOTION_NAMES:
            uid = speaker_id or "unknown_stranger"
            if clamped <= 0.0 and uid not in self.directed_emotions:
                return
            bucket = self._ensure_speaker_bucket(uid)
            bucket[emo_name] = clamped
            if all(v <= 0.0 for v in bucket.values()):
                self.directed_emotions.pop(uid, None)

    def _add_emotion_spark(self, emo_name: str, delta: float, speaker_id: str = "unknown_stranger") -> None:
        if delta <= 0.0:
            return
        if emo_name in self.GLOBAL_EMOTION_NAMES:
            cur = self.global_emotions.get(emo_name, 0.0)
            self.global_emotions[emo_name] = max(0.0, min(1.0, cur + delta))
        elif emo_name in self.DIRECTED_EMOTION_NAMES:
            bucket = self._ensure_speaker_bucket(speaker_id)
            bucket[emo_name] = max(0.0, min(1.0, bucket.get(emo_name, 0.0) + delta))

    def get_emotions_for_speaker(self, speaker_id: str = "unknown_stranger") -> Dict[str, float]:
        """
        合成指定对话者视角下的完整 22 维情绪字典：
        全局自身情绪池 + 该 speaker_id 专属的人际靶向桶（自动屏蔽其他人的靶向情绪）。
        """
        uid = speaker_id or "unknown_stranger"
        speaker_bucket = self.directed_emotions.get(uid, {})
        result: Dict[str, float] = {}
        for name in self.ALL_EMOTION_NAMES:
            if name in self.GLOBAL_EMOTION_NAMES:
                result[name] = self.global_emotions.get(name, 0.0)
            else:
                result[name] = speaker_bucket.get(name, 0.0)
        return result

    def get_external_lingering_emotions(
        self,
        exclude_speaker_id: str = "unknown_stranger",
        min_intensity: float = 0.35,
    ) -> Dict[str, Dict[str, float]]:
        """
        提取针对【非当前说话人】的未消退强负面人际情绪余波（如刚被同事惹毛后面对伴侣）：
        返回格式: {"colleague_01": {"Reproach": 0.8, "Anger": 0.75}}
        """
        uid_exclude = exclude_speaker_id or "unknown_stranger"
        lingering: Dict[str, Dict[str, float]] = {}
        for other_uid, bucket in self.directed_emotions.items():
            if other_uid == uid_exclude:
                continue
            neg_hits = {
                emo: round(val, 2)
                for emo in self.NEGATIVE_DIRECTED_NAMES
                if (val := bucket.get(emo, 0.0)) >= min_intensity
            }
            if neg_hits:
                lingering[other_uid] = neg_hits
        return lingering

    def update_decay(self):
        """推进全局情绪池与所有人际分桶的自然衰减，并自动回收归零的空桶防内存膨胀"""
        for emo in self.GLOBAL_EMOTION_NAMES:
            self.global_emotions[emo] = max(0.0, self.global_emotions[emo] - self.decay_rate)

        empty_uids = []
        for uid, bucket in self.directed_emotions.items():
            for emo in self.DIRECTED_EMOTION_NAMES:
                bucket[emo] = max(0.0, bucket.get(emo, 0.0) - self.decay_rate)
            if all(v <= 0.0 for v in bucket.values()):
                empty_uids.append(uid)

        for uid in empty_uids:
            del self.directed_emotions[uid]

        self.active_emotions.sync_from_owner()

    def calculate_occ_spikes(self, raw_appraisal: dict, personality_layer, mood_layer, speaker_id: str = "unknown_stranger"):
        """
        完备即时情感层结算中心：
        1. 基于大五人格连续矩阵的五大派系复合加权认知扭曲；
        2. 将爆发出的情绪精准路由至【全局自身池】与【当前 speaker_id 靶向池】。
        """
        logger.debug("calculate_occ_spikes......begin")
        uid = speaker_id or "unknown_stranger"
        self.last_speaker_id = uid

        # 提取当前说话人的关系契约
        rel_profile = personality_layer.config.social_graph.get_relation(uid)
        # 1. 提取当前底层的 OCEAN 核心观念基因 (皆为 0.0 ~ 1.0 之间的浮点数)
        trait_O = personality_layer.get_trait("O")
        trait_C = personality_layer.get_trait("C")
        trait_E = personality_layer.get_trait("E")
        trait_A = personality_layer.get_trait("A")
        trait_N = personality_layer.get_trait("N")

        cfg = personality_layer.config.cognitive_filter
        w_factions = {}
        for fac_name, fac_cfg in cfg.factions.items():
            weight = 1.0
            for trait_name, invert in fac_cfg.trait_formula:
                val = personality_layer.get_trait(trait_name)
                weight *= (1.0 - val) if invert else val
            w_factions[fac_name] = weight

        # 解构提取计算好的派系引力
        w_pessimist = w_factions["pessimist"]
        w_optimist = w_factions["optimist"]
        w_victim = w_factions["victim"]
        w_detachment = w_factions["detachment"]
        w_narcissist = w_factions["narcissist"]

        # 3. 提取原始评估输入
        raw_des = raw_appraisal.get("desirability", 0.0)
        raw_blame = raw_appraisal.get("blameworthiness", 0.0)

        # 初始化内化过滤字典
        filtered_appraisal = {k: v for k, v in raw_appraisal.items()}
        filtered_appraisal.setdefault("desirability", 0.0)
        filtered_appraisal.setdefault("blameworthiness", 0.0)
        filtered_appraisal.setdefault("self_blameworthiness", 0.0)
        filtered_appraisal.setdefault("future_desirability", 0.0)
        filtered_appraisal.setdefault("prospect_status", "none")
        filtered_appraisal.setdefault("other_desirability", 0.0)
        filtered_appraisal.setdefault("other_relationship", rel_profile.intimacy_baseline)
        filtered_appraisal.setdefault("appealingness", 0.0)
        logger.debug(f"filtered_appraisal: {filtered_appraisal}")

        # 4. 执行全连续动态扭曲（各派系按权重撕扯原始输入）
        # --- 维度 A：好事 (raw_des > 0) 的认知内化 ---
        if raw_des > 0:
            logger.debug(f"happy forever case: {raw_appraisal}")
            dis_cfg = cfg.good_event_distortion
            pessimist_effect = w_pessimist * (raw_des * dis_cfg.pessimist)
            optimist_effect = w_optimist * (raw_des * dis_cfg.optimist)
            detachment_effect = w_detachment * (raw_des * dis_cfg.detachment)

            w_rest = max(0.0, 1.0 - (w_pessimist + w_optimist + w_detachment))
            rest_effect = w_rest * raw_des

            filtered_appraisal["desirability"] = pessimist_effect + optimist_effect + detachment_effect + rest_effect

        # --- 维度 B：坏事 (raw_des <= 0) 的认知内化 ---
        else:
            logger.debug(f"doubt forever case: {raw_appraisal}")
            dis_cfg = cfg.bad_event_distortion
            pessimist_effect = w_pessimist * (raw_des * dis_cfg.pessimist)
            optimist_effect = w_optimist * (raw_des * dis_cfg.optimist)
            detachment_effect = w_detachment * (raw_des * dis_cfg.detachment)

            w_rest = max(0.0, 1.0 - (w_pessimist + w_optimist + w_detachment))
            rest_effect = w_rest * raw_des

            filtered_appraisal["desirability"] = pessimist_effect + optimist_effect + detachment_effect + rest_effect

        # --- 维度 C：归因偏误与责任内化 (Blameworthiness & Self-Blame) ---
        bias_cfg = cfg.attribution_bias
        # 偏执受害者(victim)喜欢甩锅，会把“坏事带来的痛苦”强行转化为“外界对我的针对(外部责备)”
        if raw_des < 0:
            logger.debug(f"hurt forever case: {raw_appraisal}")
            # 受害者倾向越强，越倾向于无中生有地指责外界
            filtered_appraisal["blameworthiness"] += (w_victim * raw_des * bias_cfg.victim_blame_multiplier)
            # 完美主义自恋派(narcissist)在坏事发生时，既疯狂引发自我羞耻(自责)，又因为自尊心反向攻击别人
            filtered_appraisal["self_blameworthiness"] += (w_narcissist * raw_des * bias_cfg.narcissist_self_shame_multiplier)
            filtered_appraisal["blameworthiness"] += (w_narcissist * raw_des * bias_cfg.narcissist_external_blame_multiplier)

        # 被人非议责备时 (raw_blame < 0)
        if raw_blame < 0:
            logger.debug(f"negative forever case: {raw_appraisal}")
            # 多疑悲观派双倍放大别人的指责，冷漠孤僻派强行降维抹平
            filtered_appraisal["blameworthiness"] = (
                w_pessimist * (raw_blame * cfg.criticism_pessimist_multiplier) +
                w_detachment * (raw_blame * cfg.criticism_detachment_multiplier) +
                (max(0.0, 1.0 - w_pessimist - w_detachment)) * raw_blame
            )

        # --- 结束滤网，以下使用过滤后的内化数据进行双池路由 OCC 22 模型结算 ---
        desirability = filtered_appraisal["desirability"]
        future_desirability = filtered_appraisal["future_desirability"]
        prospect_status = filtered_appraisal["prospect_status"]
        blameworthiness = filtered_appraisal["blameworthiness"]
        self_blameworthiness = filtered_appraisal["self_blameworthiness"]
        other_desirability = filtered_appraisal["other_desirability"]
        other_relationship = filtered_appraisal["other_relationship"]
        appealingness = filtered_appraisal["appealingness"]

        # 覆盖基准关系亲疏度（优先使用配置中心里的真实关系基准）
        if rel_profile.relation_type != "stranger":
            # 若已登记为亲属/伴侣，以关系图谱中的亲密度为准，防止大模型单次误判
            other_relationship = rel_profile.intimacy_baseline

        mood_multiplier = mood_layer.get_mood_multiplier()

        # 0. 远期未来前瞻 -> [全局自身池]
        if future_desirability > 0:
            hope_spark = future_desirability * (1.0 + trait_E) * (1.5 - trait_N)
            self._add_emotion_spark("Hope", hope_spark, uid)

        # 1.1 & 1.2 预期类与突发事件结果类 -> [全局自身池]
        if prospect_status == "expected":
            if desirability > 0:
                self._add_emotion_spark("Hope", desirability * (1.0 + trait_E), uid)
            elif desirability < 0:
                self._add_emotion_spark("Fear", abs(desirability) * (1.0 + trait_N), uid)
        elif prospect_status == "confirmed":
            if desirability > 0:
                self._add_emotion_spark("Satisfaction", desirability, uid)
            elif desirability < 0:
                self._add_emotion_spark("Fears_Confirmed", abs(desirability), uid)
        elif prospect_status == "disconfirmed":
            if desirability > 0:
                self._add_emotion_spark("Disappointment", desirability * mood_multiplier, uid)
            elif desirability < 0:
                self._add_emotion_spark("Relief", abs(desirability), uid)
        else:  # "none"
            if desirability > 0:
                joy_spark = (desirability * (1.0 + trait_E)) * (2.0 - mood_multiplier)
                self._add_emotion_spark("Joy", joy_spark, uid)
                mood_layer.apply_physiological_impact(delta_v=joy_spark * 0.2, delta_a=joy_spark * 0.1)
            elif desirability < 0:
                distress_spark = (abs(desirability) * (1.0 + trait_N)) * mood_multiplier
                self._add_emotion_spark("Distress", distress_spark, uid)
                mood_layer.apply_physiological_impact(delta_v=-distress_spark * 0.2, delta_a=distress_spark * 0.1)

        # 1.3 他人遭遇 -> [按 speaker_id 隔离的人际靶向池]
        if other_desirability != 0:
            if other_relationship >= 0:
                if other_desirability > 0:
                    self._add_emotion_spark("Happy_For", other_desirability * trait_A, uid)
                else:
                    self._add_emotion_spark("Pity", abs(other_desirability) * trait_A, uid)
            else:
                if other_desirability > 0:
                    self._add_emotion_spark("Resentment", other_desirability * mood_multiplier, uid)
                else:
                    self._add_emotion_spark("Gloating", abs(other_desirability), uid)

        # 2. 行为类：他人行为 -> [靶向池]，自身行为 -> [全局池]
        if blameworthiness > 0:
            self._add_emotion_spark("Admiration", blameworthiness, uid)
        elif blameworthiness < 0:
            self._add_emotion_spark("Reproach", abs(blameworthiness) * mood_multiplier, uid)

        if self_blameworthiness > 0:
            self._add_emotion_spark("Pride", self_blameworthiness * trait_C, uid)
        elif self_blameworthiness < 0:
            self._add_emotion_spark("Shame", abs(self_blameworthiness) * trait_N, uid)

        # 3. 对象属性类 -> [靶向池]
        if appealingness > 0:
            self._add_emotion_spark("Liking", appealingness * trait_O, uid)
        elif appealingness < 0:
            self._add_emotion_spark("Disliking", abs(appealingness) * trait_N, uid)

        # 4. 复合类：Gratitude/Anger -> [靶向池]，Gratification/Remorse -> [全局池]
        if desirability > 0 and blameworthiness > 0:
            self._add_emotion_spark("Gratitude", (desirability + blameworthiness) / 2 * trait_A, uid)
        if desirability < 0 and blameworthiness < 0:
            anger_spark = ((abs(desirability) + abs(blameworthiness)) / 2) * (1.5 - trait_A) * mood_multiplier
            self._add_emotion_spark("Anger", anger_spark, uid)
        if desirability > 0 and self_blameworthiness > 0:
            self._add_emotion_spark("Gratification", (desirability + self_blameworthiness) / 2, uid)
        if desirability < 0 and self_blameworthiness < 0:
            self._add_emotion_spark("Remorse", (abs(desirability) + abs(self_blameworthiness)) / 2 * trait_N, uid)

        # 同步刷新兼容代理视图
        self.active_emotions.sync_from_owner()
        logger.debug("calculate_occ_spikes......end")

    def to_dict(self):
        return {
            "global_emotions": dict(self.global_emotions),
            "directed_emotions": {
                uid: dict(bucket) for uid, bucket in self.directed_emotions.items()
                if any(v > 0.0 for v in bucket.values())
            },
            "last_speaker_id": self.last_speaker_id,
            # 保留旧版快照兼容字段
            "emotions": self.get_emotions_for_speaker(self.last_speaker_id),
            "decay_rate": self.decay_rate,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'OCCEmotionLayer':
        instance = cls()
        instance.decay_rate = float(data.get("decay_rate", 0.25))
        instance.last_speaker_id = str(data.get("last_speaker_id", "unknown_stranger"))

        # 1. 优先恢复新版双池隔离结构
        if "global_emotions" in data or "directed_emotions" in data:
            raw_global = data.get("global_emotions", {})
            if isinstance(raw_global, dict):
                for emo_name, emo_val in raw_global.items():
                    if emo_name in instance.GLOBAL_EMOTION_NAMES:
                        instance.global_emotions[emo_name] = max(0.0, min(1.0, float(emo_val)))

            raw_directed = data.get("directed_emotions", {})
            if isinstance(raw_directed, dict):
                for uid, bucket in raw_directed.items():
                    if isinstance(bucket, dict):
                        clean_bucket = {
                            name: max(0.0, min(1.0, float(bucket.get(name, 0.0))))
                            for name in cls.DIRECTED_EMOTION_NAMES
                        }
                        if any(v > 0.0 for v in clean_bucket.values()):
                            instance.directed_emotions[str(uid)] = clean_bucket
        else:
            # 2. 无损兼容旧版扁平存档 ("emotions" 或 "active_emotions")
            saved_emotions = data.get("emotions") if "emotions" in data else data.get("active_emotions", {})
            if isinstance(saved_emotions, dict):
                for emo_name, emo_val in saved_emotions.items():
                    instance._set_emotion_value(emo_name, float(emo_val), speaker_id=instance.last_speaker_id)

        instance.active_emotions.sync_from_owner()
        return instance
