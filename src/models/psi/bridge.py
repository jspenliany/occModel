# filename: psi_bridge.py
from src.models.psi.mood import MoodLayer
from src.models.psi.personality import PersonalityLayer
from src.models.psi.emotion_all import OCCEmotionLayer
from src.logger_singleton import logger


class PSI3DGlassBridge:
    def __init__(self, mbti_type: str, profession: str):
        self.p_layer = PersonalityLayer(mbti_type)
        raw_v = (self.p_layer.get_trait("E") * 0.5 + self.p_layer.get_trait("A") * 0.3 - self.p_layer.get_trait("N") * 0.35) * 1.2
        raw_a = self.p_layer.get_trait("E") * 0.8 + self.p_layer.get_trait("O") * 0.2 - 0.45
        init_v = max(-1.0, min(1.0, raw_v))
        init_a = max(-1.0, min(1.0, raw_a))
        self.m_layer = MoodLayer(self.p_layer.config,base_valence=init_v, base_arousal=init_a)
        self.e_layer = OCCEmotionLayer()

        # 习惯闭环累积器
        self.anger_habit_counter = 0
        self.plasticity_speed = 0.015

        # 标志当前环境是否属于极端困境
        self.in_hardship_flag = False

        self.profession = profession

    def set_environmental_hardship(self, flag: bool):
        """控制环境是否属于困境"""
        self.in_hardship_flag = flag

    def receive_user_stimulus(self, appraisal_data: dict):
        """外部事件输入触发"""
        logger.debug("receive_user_stimulus......begin")
        # 第一步：计算即时爆发（内部已挂载观念强化滤网）
        self.e_layer.calculate_occ_spikes(appraisal_data, self.p_layer, self.m_layer)

        # 第二步：【行为->习惯->观念的自循环】
        # 🌟 优化：无论是愤怒(Anger)还是深深的无力悲伤(Distress)突破 0.5，都会高频累积为黑化习惯
        active_anger = self.e_layer.active_emotions.get("Anger", 0.0)
        active_distress = self.e_layer.active_emotions.get("Distress", 0.0)
        # 检测爆发出的愤怒，如果累积成高频冲突习惯，反向污染底层观念（使其变毒舌A降、焦虑N升）
        if active_anger > 0.5 or active_distress > 0.5:
            self.anger_habit_counter += 1
            if self.anger_habit_counter >= 3:
                # 观念被习惯改造
                print(f"\n🔥 [自循环激活] 持续承受折磨（当前即时 Distress: {active_distress:.2f}），触发基因黑化重塑！")
                # 观念被伤害摧毁：不信任感暴增（宜人性 A 暴跌），焦虑感暴增（神经质 N 暴涨）
                self.p_layer.dynamic_reshape_trait("A", -0.05)  # 黑化步长稍微加大，方便在短跑测试中肉眼可见
                self.p_layer.dynamic_reshape_trait("N", 0.05)
                self.anger_habit_counter = 0
        logger.debug("receive_user_stimulus...end")

    def update_system_clock(self):
        """系统主时钟：推进心境、情感衰减、信念转化、以及困境结算"""
        active_hope = self.e_layer.active_emotions.get("Hope", 0.0)

        # 将当前的 短期希望 与 困境状态 压入心情层，计算是否触发放弃
        self.m_layer.update_decay(current_hope=active_hope, in_hardship=self.in_hardship_flag)
        self.e_layer.update_decay()

    # === 🌟 核心新增需求：外界降维打击/权威权威书籍直击灵魂重塑接口 ===
    def trigger_paradigm_shift_event(self, target_trait: str, text: str, target_absolute_value: float):
        """
        供外部业务调用的特殊终极接口：
        当AI见到了崇拜的人或读到一本书，直接绕过习惯累积，瞬间颠覆反转底层核心观念。
        """
        logger.debug("trigger_paradigm_shift_event...begin")
        self.p_layer.paradigm_shift_by_external_source(
            target_trait=target_trait,
            trigger_text=text,
            force_value=target_absolute_value
        )
        # 颠覆后，由于内心的猛烈顿悟，重置中期心情层的基准与状态
        self.m_layer.valence = 0.5 if target_absolute_value >= 0.5 else -0.5
        self.m_layer.giving_up_rate = 0.0  # 顿悟瞬间清除一切放弃和摆烂心态
        logger.debug("trigger_paradigm_shift_event...end")

    def get_current_avatar_state(self) -> dict:
        return {
            "profession": self.profession,
            "mbti": self.p_layer.mbti,
            "ocean_dna": {k: round(v, 3) for k, v in self.p_layer.ocean.items()},
            "mood_valence": round(self.m_layer.valence, 2),
            "mood_arousal": round(self.m_layer.arousal, 2),
            "competence": round(self.m_layer.competence, 2),
            "giving_up_rate": round(self.m_layer.giving_up_rate, 2),
            "faith_shield": round(self.m_layer.faith_shield, 2),
            "active_emotions": {k: round(v, 2) for k, v in self.e_layer.active_emotions.items() if v > 0.0}
        }
    # 追加入 PSI3DGlassBridge中，实现全状态序列化
    def to_dict(self) -> dict:
        return {
            "profession": self.profession,
            "personality": self.p_layer.to_dict(),
            "mood": self.m_layer.to_dict(),
            "emotion": self.e_layer.to_dict(),
            "anger_habit_counter": self.anger_habit_counter,
            "in_hardship_flag": self.in_hardship_flag
        }

    @classmethod
    def load_bridge(cls, state_dict: dict) -> 'PSI3DGlassBridge':
        bridge = cls.__new__(cls)
        bridge.profession = state_dict["profession"]
        bridge.p_layer = PersonalityLayer.from_dict(state_dict["personality"])
        bridge.m_layer = MoodLayer.from_dict(state_dict["mood"])
        bridge.e_layer = OCCEmotionLayer.from_dict(state_dict["emotion"]) # 内部自动处理物理时间衰减！
        bridge.anger_habit_counter = state_dict["anger_habit_counter"]
        bridge.in_hardship_flag = state_dict["in_hardship_flag"]
        bridge.plasticity_speed = 0.015
        return bridge
