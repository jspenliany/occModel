import pytest
from unittest.mock import MagicMock
from src.models.psi.engine_config import EngineConfig, RelationalProfile
from src.models.psi.personality import PersonalityLayer
from src.models.psi.mood import MoodLayer
from src.models.psi.emotion_all import OCCEmotionLayer
from src.models.psi.bridge import PSI3DGlassBridge
from src.pattern.psi_avatar import PsiAvatar
from src.pattern.avatar_orchestrator import AvatarOrchestrator
from src.prompts.prompt_renderer import LLMPromptRenderer


# ==================== 测试桩 (Test Fixtures & Mocks) ====================

class DummyLoreFactory:
    def create_core_lore(self, profession: str, mbti: str, ocean_dna: dict) -> str:
        return f"Core lore for {profession} ({mbti})"


@pytest.fixture
def default_config():
    return EngineConfig()


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "Mocked response || Bubble 2"
    client.chat.completions.create.return_value = mock_resp
    return client


# ==================== 模块 1: MoodLayer 心境与护盾单元测试 ====================

class TestMoodLayer:

    def test_tc_mood_01_hope_precipitation_and_shield_cap(self, default_config):
        """TC_MOOD_01: 验证高希望度沉淀为信念与护盾，且不超过上限 0.8"""
        mood = MoodLayer(default_config, base_valence=0.0, base_arousal=0.0)
        init_comp = mood.competence

        # 连续注入高希望 (Hope = 0.8 > trigger_threshold 0.4)
        for _ in range(10):
            mood.update_decay(current_hope=0.8, in_hardship=False)

        assert mood.competence > init_comp
        assert mood.competence <= 1.0
        assert mood.faith_shield == pytest.approx(0.8)  # 严格锁定在 max_faith_shield

    def test_tc_mood_02_shield_mitigation_and_wear(self, default_config):
        """TC_MOOD_02: 验证护盾按比例吸收负面打击，并产生轻微信心磨损"""
        mood = MoodLayer(default_config, base_valence=0.0, base_arousal=0.0)
        mood.faith_shield = 0.5  # 护盾抵消 50% 伤害
        init_comp = mood.competence

        mood.apply_physiological_impact(delta_v=-0.4, delta_a=0.2)

        # 预期实际损失 = -0.4 * (1 - 0.5) = -0.2
        assert mood.valence == pytest.approx(-0.2)
        assert mood.arousal == pytest.approx(0.2)
        # 验证信心磨损步长 (0.005)
        assert mood.competence == pytest.approx(init_comp - 0.005)

    def test_tc_mood_03_hardship_resilience_vs_collapse(self, default_config):
        """TC_MOOD_03: 验证困境模式下【有护盾锁底】与【无护盾雪崩】的分化"""
        # 分支 A: 有护盾保护
        protected_mood = MoodLayer(default_config, base_valence=-0.1, base_arousal=0.0)
        protected_mood.faith_shield = 0.4
        protected_mood.giving_up_rate = 0.3
        protected_mood.valence = -0.18

        protected_mood.update_decay(current_hope=0.2, in_hardship=True)
        assert protected_mood.giving_up_rate == pytest.approx(0.2)  # 放弃率被压制下降 0.1
        assert protected_mood.valence >= -0.2                       # 锁定在 valence_floor_protected

        # 分支 B: 无护盾且信念低 -> 触发雪崩
        broken_mood = MoodLayer(default_config, base_valence=-0.2, base_arousal=0.0)
        broken_mood.faith_shield = 0.0
        broken_mood.competence = 0.3  # 低于 min_competence_active (0.6)
        broken_mood.valence = -0.3

        for _ in range(5):
            broken_mood.update_decay(current_hope=0.0, in_hardship=True)

        assert broken_mood.giving_up_rate == 1.0  # 彻底摆烂
        assert broken_mood.competence == 0.0      # 信念归零
        assert broken_mood.valence == -1.0        # 跌入极限谷底

    def test_tc_mood_04_recovery_after_hardship(self, default_config):
        """TC_MOOD_04: 验证脱离困境后放弃意愿的自然冷却恢复"""
        mood = MoodLayer(default_config, base_valence=0.0, base_arousal=0.0)
        mood.giving_up_rate = 0.5

        mood.update_decay(current_hope=0.0, in_hardship=False)
        assert mood.giving_up_rate == pytest.approx(0.4)


# ==================== 模块 2: 认知滤网与黑化/顿悟单元测试 ====================

class TestCognitiveAndEvolution:

    def test_tc_emo_01_mbti_bounds_and_fallback(self):
        """TC_EMO_01: 验证 MBTI 映射区间、格式异常拦截及未知字符的缺省兜底"""
        p = PersonalityLayer("INTP-T")
        assert 0.7 <= p.get_trait("O") <= 0.9
        assert 0.1 <= p.get_trait("A") <= 0.3
        assert 0.7 <= p.get_trait("N") <= 0.95

        # 1. 格式错误（基础编码长度 != 4）应明确抛出 ValueError
        with pytest.raises(ValueError, match="Invalid MBTI format"):
            PersonalityLayer("INVALID")

        # 2. 长度为 4 但包含非标准字符（如 XXXX-Z）应安全回退到 DEFAULT 区间 (0.4, 0.6)
        p_unknown = PersonalityLayer("XXXX-Z")
        for k in ["O", "C", "E", "A", "N"]:
            assert 0.4 <= p_unknown.get_trait(k) <= 0.6


    def test_tc_emo_02_cognitive_filter_distortion(self):
        """TC_EMO_02: 验证悲观派放大坏事 vs 乐天派稀释坏事"""
        b_pess = PSI3DGlassBridge("INTP-T", "dev")
        b_pess.p_layer.ocean = {"O": 0.5, "C": 0.5, "E": 0.0, "A": 0.0, "N": 1.0}
        b_pess.m_layer.valence = 0.0
        b_pess.m_layer.competence = 0.2

        b_opt = PSI3DGlassBridge("ENFJ-A", "dev")
        b_opt.p_layer.ocean = {"O": 0.5, "C": 0.5, "E": 1.0, "A": 1.0, "N": 0.0}
        b_opt.m_layer.valence = 0.0
        b_opt.m_layer.competence = 0.2

        stimulus = {"desirability": -0.3, "prospect_status": "none"}
        b_pess.e_layer.calculate_occ_spikes(stimulus, b_pess.p_layer, b_pess.m_layer)
        b_opt.e_layer.calculate_occ_spikes(stimulus, b_opt.p_layer, b_opt.m_layer)

        assert b_pess.e_layer.active_emotions["Distress"] > b_opt.e_layer.active_emotions["Distress"] * 4

    def test_tc_emo_03_blackening_loop_and_paradigm_shift(self):
        """TC_EMO_03: 验证连续 3 次高怒黑化重塑与外部顿悟反转"""
        bridge = PSI3DGlassBridge("INTP-T", "dev")
        init_a = bridge.p_layer.get_trait("A")
        init_n = bridge.p_layer.get_trait("N")

        bad_event = {"desirability": -1.0, "blameworthiness": -1.0, "prospect_status": "none"}
        for _ in range(3):
            bridge.receive_user_stimulus(bad_event)
            bridge.e_layer.active_emotions["Anger"] = 0.0  # 模拟间隔清零以测试计数累积

        assert bridge.p_layer.get_trait("A") == pytest.approx(max(0.0, init_a - 0.05))
        assert bridge.p_layer.get_trait("N") == pytest.approx(min(1.0, init_n + 0.05))
        assert bridge.anger_habit_counter == 0

        # 触发读书顿悟反转
        bridge.m_layer.giving_up_rate = 0.9
        bridge.trigger_paradigm_shift_event("A", "顿悟书籍", 0.95)
        assert bridge.p_layer.get_trait("A") == 0.95
        assert bridge.m_layer.giving_up_rate == 0.0
        assert bridge.m_layer.valence == 0.5


# ==================== 模块 3: 社交关系契约单元测试 ====================

class TestSocialGraph:

    def test_tc_rel_01_relationship_anchor_and_stranger_fallback(self):
        """TC_REL_01: 验证伴侣关系映射与未知用户自动降级为陌生人"""
        bridge = PSI3DGlassBridge("INTP-T", "dev")
        bridge.p_layer.config.social_graph.register_relation(RelationalProfile(
            target_user_id="wife_01",
            relation_type="spouse",
            intimacy_baseline=0.95,
            emotional_vulnerability=1.8,
            power_dynamic="equal",
            social_contract_lore="伴侣关系"
        ))

        wife_state = bridge.get_current_avatar_state(speaker_id="wife_01")
        assert wife_state["active_relationship"]["relation_type"] == "spouse"
        assert wife_state["active_relationship"]["intimacy"] == 0.95

        stranger_state = bridge.get_current_avatar_state(speaker_id="unknown_999")
        assert stranger_state["active_relationship"]["relation_type"] == "stranger"
        assert stranger_state["active_relationship"]["intimacy"] == 0.0


# ==================== 模块 4: 特质与精细化记忆库单元测试 ====================

class TestTraitAndMemoryBank:

    def test_tc_mem_01_trait_evolution_and_memory_upgrade(self):
        """TC_MEM_01: 验证特质频次累加/态度异变，以及记忆从梦境升级为亲历"""
        avatar = PsiAvatar("cat_meet", "INTP-T", "dev", DummyLoreFactory(), None)

        # 1. 特质去重与态度异变
        t1 = [{"domain": "preference", "topic_tags": ["diet"], "linked_entities": ["cilantro"], "emotional_weight": 0.5, "action_mode": "avoid"}]
        t2 = [{"domain": "preference", "topic_tags": ["diet"], "linked_entities": ["cilantro"], "emotional_weight": 0.8, "action_mode": "approach"}]
        avatar.update_trait(t1, "2026-11-21 10:00:00")
        avatar.update_trait(t2, "2026-11-21 10:05:00")

        assert len(avatar.trait_list) == 1
        assert avatar.trait_list[0]["mention_count"] == 2
        assert avatar.trait_list[0]["action_mode"] == "approach"
        assert avatar.trait_list[0]["emotional_weight"] == 0.8

        # 2. 记忆去重与可信度升级 (dream 0.1 -> experiential 1.0)
        m_dream = [{"fact_summary": "生产库发生死锁", "memory_type": "subconscious_dream", "credibility": 0.1, "involved_entities": ["db"]}]
        m_real = [{"fact_summary": "生产库发生死锁", "memory_type": "episodic_experiential", "credibility": 1.0, "involved_entities": ["db"]}]
        avatar.update_memory(m_dream, "2026-11-21 10:10:00")
        avatar.update_memory(m_real, "2026-11-21 10:20:00")

        assert len(avatar.core_memories) == 1
        mem_obj = avatar.core_memories[0]
        cred = mem_obj.credibility if hasattr(mem_obj, "credibility") else mem_obj["credibility"]
        m_type = mem_obj.memory_type if hasattr(mem_obj, "memory_type") else mem_obj["memory_type"]
        assert cred == 1.0
        assert m_type == "episodic_experiential"

# ==================== 模块 5: Prompt 渲染器分支覆盖测试 ====================

class TestPromptRenderer:

    def test_tc_rnd_01_mood_grid_and_mbti_mask(self):
        """TC_RND_01: 验证九宫格消除中间态盲区及 16 型人格面具拼接"""
        renderer = LLMPromptRenderer("cat_meet", "dev", DummyLoreFactory())
        state = {
            "mbti": "INTP-T",
            "mood_valence": -0.25,
            "mood_arousal": 0.01,  # 处于原本容易漏判的中间区间
            "giving_up_rate": 0.0,
            "competence": 0.7
        }
        mood_text = renderer._interpret_mood(state)
        assert "Irritated" in mood_text
        assert "Behavioral Expression (INTP-T)" in mood_text
        assert "Calm, balanced" not in mood_text

    def test_tc_rnd_02_four_way_pacing_routing(self):
        """TC_RND_02: 验证四向自我涉入度气口路由（雷区长文 vs 微情绪涟漪 vs 低唤醒短句）"""
        renderer = LLMPromptRenderer("cat_meet", "dev", DummyLoreFactory())

        # 1. 雷区高怒 -> 禁用 || 分隔符，输出长文
        high_anger_state = {"active_emotions": {"Anger": 0.8}, "mood_arousal": 0.5,
                            "active_relationship": {"intimacy": 0.0}}
        assert "ABANDON the \"||\"" in renderer._format_self_involvement_model(high_anger_state)
        # 2. 微情绪涟漪 (0.35) -> 2~3 句自然展开
        ripple_state = {"active_emotions": {"Liking": 0.35}, "mood_arousal": 0.05}
        assert "ENGAGED CONVERSATIONAL RIPPLE" in renderer._format_self_involvement_model(ripple_state)
        # 3. 低唤醒日常 -> 1~2 句极简短气泡
        casual_state = {"active_emotions": {"Liking": 0.1}, "mood_arousal": -0.1}
        assert "CASUAL LEAP-FROG CHAT" in renderer._format_self_involvement_model(casual_state)

    def test_tc_rnd_03_memory_source_monitoring_labels(self):
        """TC_RND_03: 验证记忆渲染正确区分梦境幻觉与亲身经历"""
        renderer = LLMPromptRenderer("cat_meet", "dev", DummyLoreFactory())
        memories = [
            {"fact_summary": "梦见中了彩票", "memory_type": "subconscious_dream", "credibility": 0.1},
            {"fact_summary": "昨晚修复了内存泄漏", "memory_type": "episodic_experiential", "credibility": 1.0}
        ]
        rendered = renderer._format_memories(memories)
        assert "梦境/潜意识幻觉" in rendered
        assert "亲身经历/铁证事实" in rendered


#==================== 模块 6: 持久化往返与引用一致性测试 ====================

class TestSerializationRoundTrip:
    def test_tc_ser_01_save_and_cold_reload_consistency(self, tmp_path, mock_llm_client):
        """TC_SER_01: 验证全状态存档 -> 冷启动重载 -> 共享配置引用 -> 继续 Tick 无异常"""
        orch = AvatarOrchestrator(llm_client=mock_llm_client)
        orch.storage_dir = str(tmp_path)
        avatar = PsiAvatar("cat_meet", "INTP-T", "dev", DummyLoreFactory(), None)
        avatar.register_relationship(RelationalProfile(
            target_user_id="dad_01",
            relation_type="parent",
            intimacy_baseline=0.85,
            emotional_vulnerability=1.3,
            power_dynamic="superior",
            social_contract_lore="父亲"
        ))
        avatar.engine.m_layer.faith_shield = 0.55
        avatar.message_history.add_user_message("测试持久化时间线", speaker="dad_01")
        orch.register_avatar("cat_meet", avatar)
        orch.save_all_avatars()
        # 模拟进程重启后的全新 Orchestrator 冷启动加载
        new_orch = AvatarOrchestrator(llm_client=mock_llm_client)
        new_orch.storage_dir = str(tmp_path)
        assert new_orch.load_avatar_from_storage("cat_meet", DummyLoreFactory()) is True
        restored = new_orch.avatars["cat_meet"]
        # 1. 验证浮点数精度与社交图谱完整保留
        assert restored.engine.m_layer.faith_shield == pytest.approx(0.55)
        rel = restored.engine.p_layer.config.social_graph.get_relation("dad_01")
        assert rel.relation_type == "parent"
        # 2. 验证 MoodLayer 与 PersonalityLayer 严格共享同一份 config 实例
        assert restored.engine.m_layer.config is restored.engine.p_layer.config
        # 3. 验证冷启动恢复后继续执行刺激结算不抛任何 AttributeError
        restored.apply_appraisal_and_tick({"desirability": -0.3, "prospect_status": "none"}, speaker_id="dad_01")
