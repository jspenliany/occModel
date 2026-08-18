# filename: psi_bridge.py
from src.models.psi.mood import MoodLayer
from src.models.psi.personality import PersonalityLayer
from src.models.psi.emotion import OCCEmotionLayer


class PSI3DGlassBridge:
    """
    中央调度桥梁：
    负责将性格、心情、情感三个完全解耦的文件组装成一个生命体。
    外部业务代码（如LLM、渲染层、生理状态层）只需要跟这个桥接器打交道。
    """

    def __init__(self, mbti_type: str):
        # 1. 组装第一层：性格层
        self.p_layer = PersonalityLayer(mbti_type)

        # 根据静态性格基因，计算出心情层的中性初始基准线
        init_v = (self.p_layer.get_trait("E") - self.p_layer.get_trait("N")) * 0.3
        init_a = (self.p_layer.get_trait("E") + self.p_layer.get_trait("N") - 1.0) * 0.2

        # 2. 组装第二层：心情层
        self.m_layer = MoodLayer(base_valence=init_v, base_arousal=init_a)

        # 3. 组装第三层：情感层
        self.e_layer = OCCEmotionLayer()

    def update_system_clock(self):
        """系统主时钟 Tick 推进：各层自行处理自身的时间衰减"""
        self.m_layer.update_decay()
        self.e_layer.update_decay()

    def receive_user_stimulus(self, appraisal_data: dict):
        """外部事件输入接口：传递给内部OCC评估，并自动拉取性格和心情作为计算上下文"""
        self.e_layer.calculate_occ_spikes(
            appraisal=appraisal_data,
            personality_layer=self.p_layer,
            mood_layer=self.m_layer
        )

    # --- 开放给外部物理/生理系统的API Hooks ---
    def hook_internal_needs_drain(self, loss_v: float, loss_a: float):
        """例：生理系统发现NPC三天没吃饭，直接调用此接口扣除心情层的 Valence"""
        self.m_layer.apply_physiological_impact(loss_v, loss_a)

    def hook_force_emotion(self, emo_name: str, val: float):
        """例：剧情系统强制给角色注入恐惧或惊喜"""
        self.e_layer.trigger_internal_spark(emo_name, val)

    # --- 开放给大模型Prompt层或表现层的输出接口 ---
    def get_current_avatar_state(self) -> dict:
        """打包输出当前全层级状态快照"""
        return {
            "mbti": self.p_layer.mbti,
            "ocean_dna": {k: round(v, 2) for k, v in self.p_layer.ocean.items()},
            "current_mood": {"valence": round(self.m_layer.valence, 2), "arousal": round(self.m_layer.arousal, 2)},
            "active_emotions": {k: round(v, 2) for k, v in self.e_layer.active_emotions.items()}
        }


# ==========================================
# 独立运行与集成验证
# ==========================================
if __name__ == "__main__":
    # 创建一个虚拟人：高冷严谨的 INTJ-A
    avatar = PSI3DGlassBridge("INTJ-A")
    print("【系统初始化】虚拟人创建成功。")
    print(avatar.get_current_avatar_state())

    # 模拟外部事件：犯了严重的错误被用户责备
    print("\n【外部遭遇】角色犯错后，遭遇了用户的严厉批评...")
    avatar.receive_user_stimulus({"desirability": -0.8, "blameworthiness": 0.7, "self_blameworthiness": 0.8})
    print(avatar.get_current_avatar_state())

    # 模拟物理生理系统：系统电池不足/NPC过度疲劳
    print("\n【生理消耗】系统检测到 NPC 处于严重缺乏能量状态...")
    avatar.hook_internal_needs_drain(loss_v=-0.3, loss_a=0.2)
    print(avatar.get_current_avatar_state())

    # 模拟时间流逝
    print("\n【时间推进】主时钟向前推进一个 Tick...")
    avatar.update_system_clock()
    print(avatar.get_current_avatar_state())
