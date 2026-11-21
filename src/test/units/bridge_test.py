import pytest
from src.models.psi.bridge import PSI3DGlassBridge
from src.models.psi.engine_config import RelationalProfile


class TestPSI3DGlassBridge:

    def test_tc_brg_01_initialization_and_shared_config(self):
        """TC_BRG_01: 验证门面初始化、初始心境边界钳制及跨层共享同一 config 实例"""
        bridge = PSI3DGlassBridge(mbti_type="INTP-T", profession="software engineer")

        assert bridge.profession == "software engineer"
        assert bridge.anger_habit_counter == 0
        assert bridge.in_hardship_flag is False

        # 验证初始心境严格落在 [-1.0, 1.0] 范围内
        assert -1.0 <= bridge.m_layer.valence <= 1.0
        assert -1.0 <= bridge.m_layer.arousal <= 1.0

        # 验证性格层与心境层严格共享同一个 EngineConfig 引用
        assert bridge.m_layer.config is bridge.p_layer.config

    def test_tc_brg_02_stimulus_to_habit_blackening_loop(self, capsys):
        """TC_BRG_02: 验证【情绪刺激 -> 习惯累积 -> 基因黑化重塑】全链路闭环"""
        bridge = PSI3DGlassBridge(mbti_type="INTP-T", profession="software engineer")
        init_a = bridge.p_layer.get_trait("A")
        init_n = bridge.p_layer.get_trait("N")

        # 1. 微弱刺激（Anger/Distress <= 0.5）：不增加黑化计数器
        mild_stimulus = {"desirability": -0.05, "blameworthiness": -0.05, "prospect_status": "none"}
        bridge.receive_user_stimulus(mild_stimulus)
        assert bridge.anger_habit_counter == 0

        # 2. 连续 3 次强烈负面冲击（Anger 或 Distress > 0.5）
        severe_stimulus = {"desirability": -1.0, "blameworthiness": -1.0, "prospect_status": "none"}

        bridge.receive_user_stimulus(severe_stimulus)
        assert bridge.anger_habit_counter == 1
        bridge.e_layer.active_emotions.update({"Anger": 0.0, "Distress": 0.0})

        bridge.receive_user_stimulus(severe_stimulus)
        assert bridge.anger_habit_counter == 2
        bridge.e_layer.active_emotions.update({"Anger": 0.0, "Distress": 0.0})

        # 第 3 次触发基因黑化并清零计数器
        bridge.receive_user_stimulus(severe_stimulus)
        assert bridge.anger_habit_counter == 0
        assert bridge.p_layer.get_trait("A") == pytest.approx(max(0.0, init_a - 0.05))
        assert bridge.p_layer.get_trait("N") == pytest.approx(min(1.0, init_n + 0.05))

        captured = capsys.readouterr()
        assert "[自循环激活]" in captured.out

    def test_tc_brg_03_system_clock_hope_shield_vs_hardship(self):
        """TC_BRG_03: 验证主时钟推进中【希望充电护盾】与【困境结算/脱离恢复】"""
        bridge = PSI3DGlassBridge(mbti_type="INTP-T", profession="software engineer")

        # 1. 注入高 Hope (> 0.4)，推进主时钟转化为护盾
        bridge.e_layer.active_emotions["Hope"] = 0.8
        bridge.update_system_clock()

        assert bridge.m_layer.faith_shield > 0.0
        # 验证 e_layer 同步执行了自然衰减 (0.8 - 0.25 = 0.55)
        assert bridge.e_layer.active_emotions["Hope"] == pytest.approx(0.55)

        # 2. 开启困境模式，有护盾保护下摆烂率受压制且心情锁底
        bridge.set_environmental_hardship(True)
        bridge.m_layer.giving_up_rate = 0.3
        bridge.update_system_clock()
        assert bridge.m_layer.giving_up_rate < 0.3
        assert bridge.m_layer.valence >= -0.2

        # 3. 撤掉护盾与信心，困境中触发雪崩
        bridge.m_layer.faith_shield = 0.0
        bridge.m_layer.competence = 0.2
        bridge.m_layer.valence = -0.3
        bridge.e_layer.active_emotions["Hope"] = 0.0
        bridge.update_system_clock()
        assert bridge.m_layer.giving_up_rate > 0.2

        # 4. 解除困境，摆烂率开始缓慢恢复
        prev_giving_up = bridge.m_layer.giving_up_rate
        bridge.set_environmental_hardship(False)
        bridge.update_system_clock()
        assert bridge.m_layer.giving_up_rate < prev_giving_up

    def test_tc_brg_04_paradigm_shift_event_reversal(self):
        """TC_BRG_04: 验证降维顿悟接口对基因、心境及摆烂率的强制重置"""
        bridge = PSI3DGlassBridge(mbti_type="INTP-T", profession="software engineer")
        bridge.m_layer.giving_up_rate = 0.85
        bridge.m_layer.valence = -0.7

        # 1. 正向顿悟 (force_value >= 0.5) -> valence 设为 0.5，清零放弃率
        bridge.trigger_paradigm_shift_event("A", "阅读哲学典籍", 0.88)
        assert bridge.p_layer.get_trait("A") == 0.88
        assert bridge.m_layer.valence == 0.5
        assert bridge.m_layer.giving_up_rate == 0.0

        # 2. 负向黑化颠覆 (force_value < 0.5) -> valence 设为 -0.5
        bridge.trigger_paradigm_shift_event("A", "遭遇重大背叛", 0.1)
        assert bridge.p_layer.get_trait("A") == 0.1
        assert bridge.m_layer.valence == -0.5

    def test_tc_brg_05_get_current_avatar_state_and_speaker_routing(self):
        """TC_BRG_05: 验证状态字典导出格式、浮点数舍入精度、零值情绪过滤及关系路由"""
        bridge = PSI3DGlassBridge(mbti_type="INTP-T", profession="software engineer")
        bridge.p_layer.ocean["O"] = 0.8123456
        bridge.e_layer.active_emotions["Joy"] = 0.4567
        bridge.e_layer.active_emotions["Fear"] = 0.0  # 零值应被过滤

        bridge.p_layer.config.social_graph.register_relation(RelationalProfile(
            target_user_id="spouse_01",
            relation_type="spouse",
            intimacy_baseline=0.95,
            emotional_vulnerability=1.8,
            power_dynamic="equal",
            social_contract_lore="伴侣契约"
        ))

        state = bridge.get_current_avatar_state(speaker_id="spouse_01")

        # 验证精度舍入与过滤
        assert state["ocean_dna"]["O"] == 0.812
        assert state["active_emotions"] == {"Joy": 0.46}
        assert "Fear" not in state["active_emotions"]

        # 验证关系路由透传
        assert state["active_relationship"]["relation_type"] == "spouse"
        assert state["active_relationship"]["intimacy"] == 0.95

    def test_tc_brg_06_to_dict_and_load_bridge_round_trip(self):
        """TC_BRG_06: 验证 to_dict -> load_bridge 完整还原三层状态、计数器与单例 config 引用"""
        bridge = PSI3DGlassBridge(mbti_type="INTJ-A", profession="architect")
        bridge.anger_habit_counter = 2
        bridge.set_environmental_hardship(True)
        bridge.m_layer.faith_shield = 0.65
        bridge.e_layer.active_emotions["Pride"] = 0.72
        bridge.p_layer.config.social_graph.register_relation(RelationalProfile(
            target_user_id="boss_01",
            relation_type="colleague",
            intimacy_baseline=0.2,
            emotional_vulnerability=1.2,
            power_dynamic="superior",
            social_contract_lore="上级"
        ))

        snapshot = bridge.to_dict()
        restored = PSI3DGlassBridge.load_bridge(snapshot)

        assert restored.profession == "architect"
        assert restored.anger_habit_counter == 2
        assert restored.in_hardship_flag is True
        assert restored.m_layer.faith_shield == pytest.approx(0.65)
        assert restored.e_layer.active_emotions["Pride"] == pytest.approx(0.72)
        assert restored.p_layer.ocean == bridge.p_layer.ocean

        # 关键断言：确保读档后心境层与性格层共享同一份 config 实例
        assert restored.m_layer.config is restored.p_layer.config
        assert restored.p_layer.config.social_graph.get_relation("boss_01").power_dynamic == "superior"

        # 继续推进主时钟验证无 AttributeError
        restored.update_system_clock()

    def test_tc_brg_07_force_sync_state_and_flat_fallback(self):
        """TC_BRG_07: 验证 force_sync_state 全量同步及扁平元数据兜底覆盖"""
        bridge = PSI3DGlassBridge(mbti_type="INTP-T", profession="dev")

        # 1. 扁平元数据兜底强灌（不含完整 personality 子字典）
        flat_payload = {
            "profession": "senior architect",
            "mbti": "ENTJ-A",
            "ocean_dna": {"O": 0.9, "C": 0.9, "E": 0.8, "A": 0.4, "N": 0.2},
            "anger_habit_counter": 1,
            "in_hardship_flag": True
        }
        bridge.force_sync_state(flat_payload)

        assert bridge.profession == "senior architect"
        assert bridge.p_layer.mbti == "ENTJ-A"
        assert bridge.p_layer.get_trait("C") == 0.9
        assert bridge.anger_habit_counter == 1
        assert bridge.in_hardship_flag is True

        # 2. 全量快照强同步，验证共享 config 引用
        source_bridge = PSI3DGlassBridge(mbti_type="ISFJ-T", profession="nurse")
        source_bridge.m_layer.competence = 0.88
        bridge.force_sync_state(source_bridge.to_dict())

        assert bridge.profession == "nurse"
        assert bridge.p_layer.mbti == "ISFJ-T"
        assert bridge.m_layer.competence == pytest.approx(0.88)
        assert bridge.m_layer.config is bridge.p_layer.config
