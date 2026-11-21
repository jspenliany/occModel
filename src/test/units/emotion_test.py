import os
import json
import pytest
from unittest.mock import MagicMock
from datetime import datetime
import zoneinfo

from src.models.psi.engine_config import EngineConfig, RelationalProfile
from src.models.psi.personality import PersonalityLayer
from src.models.psi.mood import MoodLayer
from src.models.psi.emotion_all import OCCEmotionLayer
from src.models.psi.bridge import PSI3DGlassBridge
from src.pattern.psi_avatar import PsiAvatar
from src.pattern.avatar_orchestrator import AvatarOrchestrator


# ==================== 测试桩 (Mocks) ====================

class DummyLoreFactory:
    def create_core_lore(self, profession: str, mbti: str, ocean_dna: dict) -> str:
        return f"Test lore for {profession} ({mbti})"


@pytest.fixture
def mock_llm_client():
    """屏蔽外部真实大模型 API 调用，确保单元测试毫秒级确定性执行"""
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Mocked response || Bubble 2"
    client.chat.completions.create.return_value = mock_response
    return client


@pytest.fixture
def clean_bridge():
    """提供标准 INTP-T 初始化的心理引擎桥接器"""
    return PSI3DGlassBridge(mbti_type="INTP-T", profession="software engineer")


# ==================== 1. 性格基因与配置中心测试 ====================

def test_tc01_personality_bounds_and_invalid_mbti():
    """TC_01: 验证正常 MBTI 映射区间及非法 MBTI 字符的缺省兜底机制"""
    p_intp = PersonalityLayer("INTP-T")
    assert 0.7 <= p_intp.get_trait("O") <= 0.9   # N -> Openness
    assert 0.1 <= p_intp.get_trait("C") <= 0.3   # P -> Conscientiousness
    assert 0.1 <= p_intp.get_trait("E") <= 0.3   # I -> Extraversion
    assert 0.1 <= p_intp.get_trait("A") <= 0.3   # T -> Agreeableness
    assert 0.7 <= p_intp.get_trait("N") <= 0.95  # -T suffix -> Neuroticism

    # 边界测试：非法 MBTI 字符串应回退到 DEFAULT 区间 (0.4, 0.6)
    p_invalid = PersonalityLayer("XXXX-Z")
    for trait in ["O", "C", "E", "A", "N"]:
        assert 0.4 <= p_invalid.get_trait(trait) <= 0.6


# ==================== 2. 认知扭曲滤网测试 ====================

def test_tc02_cognitive_filter_pessimist_vs_optimist():
    """TC_02: 验证多疑悲观派放大坏事、盲目乐天派稀释坏事的数学扭曲"""
    # 构造极端多疑悲观派 (N=1.0, A=0.0, E=0.0 -> w_pessimist = 1.0)
    bridge_pess = PSI3DGlassBridge("INTP-T", "tester")
    bridge_pess.p_layer.ocean = {"O": 0.5, "C": 0.5, "E": 0.0, "A": 0.0, "N": 1.0}
    bridge_pess.m_layer.valence = 0.0
    bridge_pess.m_layer.competence = 0.2  # 使 mood_multiplier 基准为 1.0

    # 构造极端盲目乐天派 (E=1.0, A=1.0, N=0.0 -> w_optimist = 1.0)
    bridge_opt = PSI3DGlassBridge("ENFJ-A", "tester")
    bridge_opt.p_layer.ocean = {"O": 0.5, "C": 0.5, "E": 1.0, "A": 1.0, "N": 0.0}
    bridge_opt.m_layer.valence = 0.0
    bridge_opt.m_layer.competence = 0.2

    bad_stimulus = {"desirability": -0.4, "prospect_status": "none"}
    bridge_pess.e_layer.calculate_occ_spikes(bad_stimulus, bridge_pess.p_layer, bridge_pess.m_layer)
    bridge_opt.e_layer.calculate_occ_spikes(bad_stimulus, bridge_opt.p_layer, bridge_opt.m_layer)

    distress_pess = bridge_pess.e_layer.active_emotions["Distress"]
    distress_opt = bridge_opt.e_layer.active_emotions["Distress"]

    # 悲观派伤痛值必须显著高于乐天派
    assert distress_pess > distress_opt * 5


# ==================== 3. 社交关系图谱契约测试 ====================

def test_tc03_social_graph_relationship_routing(clean_bridge):
    """TC_03: 验证注册伴侣与未注册陌生人传入同一事件时的关系锚定与降级"""
    spouse_profile = RelationalProfile(
        target_user_id="user_wife",
        relation_type="spouse",
        intimacy_baseline=0.95,
        emotional_vulnerability=1.8,
        power_dynamic="equal",
        social_contract_lore="伴侣契约"
    )
    clean_bridge.p_layer.config.social_graph.register_relation(spouse_profile)

    # 1. 验证伴侣身份读取
    state_wife = clean_bridge.get_current_avatar_state(speaker_id="user_wife")
    assert state_wife["active_relationship"]["relation_type"] == "spouse"
    assert state_wife["active_relationship"]["intimacy"] == 0.95

    # 2. 验证未登记 ID 安全降级为 stranger，不抛 KeyError
    state_stranger = clean_bridge.get_current_avatar_state(speaker_id="random_guy_999")
    assert state_stranger["active_relationship"]["relation_type"] == "stranger"
    assert state_stranger["active_relationship"]["intimacy"] == 0.0


# ==================== 4. 抗压护盾与困境摆烂雪崩测试 ====================

def test_tc04_hardship_shield_protection_vs_despair_collapse():
    """TC_04: 验证困境模式下【有护盾保护】与【无护盾雪崩摆烂】的分化"""
    # --- 分支 A: 无护盾 + 信念耗尽 -> 触发绝望雪崩 ---
    bridge_weak = PSI3DGlassBridge("INTP-T", "worker")
    bridge_weak.m_layer.faith_shield = 0.0
    bridge_weak.m_layer.competence = 0.2  # 低于 min_competence_active (0.6)
    bridge_weak.m_layer.valence = -0.3
    bridge_weak.set_environmental_hardship(True)

    # 连续推进 5 个时钟周期
    for _ in range(5):
        bridge_weak.update_system_clock()

    assert bridge_weak.m_layer.giving_up_rate == 1.0  # 摆烂率打满
    assert bridge_weak.m_layer.competence == 0.0      # 必胜信念崩塌归零

    # --- 分支 B: 高希望沉淀护盾 -> 困境锁底保护 ---
    bridge_strong = PSI3DGlassBridge("INTP-T", "worker")
    bridge_strong.m_layer.faith_shield = 0.6  # 有效护盾 (> 0.1)
    bridge_strong.m_layer.giving_up_rate = 0.3
    bridge_strong.m_layer.valence = -0.15
    bridge_strong.set_environmental_hardship(True)

    bridge_strong.update_system_clock()

    # 护盾压制放弃率下降，且心情被锁定在 protected_floor (-0.2) 之上
    assert bridge_strong.m_layer.giving_up_rate < 0.3
    assert bridge_strong.m_layer.valence >= -0.2


# ==================== 5. 黑化自循环与降维顿悟测试 ====================

def test_tc05_habit_blackening_and_paradigm_shift(clean_bridge):
    """TC_05: 验证连续 3 次高怒触发基因黑化，以及外部顿悟接口瞬间反转"""
    init_A = clean_bridge.p_layer.get_trait("A")
    init_N = clean_bridge.p_layer.get_trait("N")

    # 构造极端恶劣刺激，确保每次 Anger > 0.5
    severe_insult = {"desirability": -1.0, "blameworthiness": -1.0, "prospect_status": "none"}

    for _ in range(3):
        clean_bridge.receive_user_stimulus(severe_insult)
        # 每次模拟间隔微弱衰减，保持 counter 累计
        clean_bridge.e_layer.active_emotions["Anger"] = 0.0

    # 验证第 3 次触发基因黑化：宜人性 A 下降 0.05，神经质 N 上升 0.05，计数器清零
    assert clean_bridge.p_layer.get_trait("A") == pytest.approx(max(0.0, init_A - 0.05))
    assert clean_bridge.p_layer.get_trait("N") == pytest.approx(min(1.0, init_N + 0.05))
    assert clean_bridge.anger_habit_counter == 0

    # 模拟陷入摆烂后遭遇“降维顿悟”
    clean_bridge.m_layer.giving_up_rate = 0.85
    clean_bridge.trigger_paradigm_shift_event("A", "阅读《非暴力沟通》顿悟", 0.90)

    assert clean_bridge.p_layer.get_trait("A") == 0.90
    assert clean_bridge.m_layer.giving_up_rate == 0.0
    assert clean_bridge.m_layer.valence == 0.5


# ==================== 6. 特质与精细化记忆去重升级测试 ====================

def test_tc06_trait_evolution_and_memory_credibility_upgrade(mock_llm_client):
    """TC_06: 验证重复特质计数累加、态度异变，以及记忆从梦境升级为亲历"""
    avatar = PsiAvatar("cat_meet", "INTP-T", "engineer", DummyLoreFactory(), None)

    # 1. 测试特质合并与态度异变
    t1 = [{"domain": "preference", "topic_tags": ["diet_habit"], "linked_entities": ["cilantro"], "emotional_weight": 0.6, "action_mode": "avoid"}]
    t2 = [{"domain": "preference", "topic_tags": ["diet_habit"], "linked_entities": ["cilantro"], "emotional_weight": 0.9, "action_mode": "approach"}]

    avatar.update_trait(t1, "2026-11-20 10:00:00")
    assert len(avatar.trait_list) == 1
    assert avatar.trait_list[0]["mention_count"] == 1

    avatar.update_trait(t2, "2026-11-20 10:05:00")
    assert len(avatar.trait_list) == 1
    assert avatar.trait_list[0]["mention_count"] == 2
    assert avatar.trait_list[0]["action_mode"] == "approach"      # 态度发生演进
    assert avatar.trait_list[0]["emotional_weight"] == 0.9         # 权重取最大值

    # 2. 测试精细化记忆去重与可信度升级
    m_dream = [{"fact_summary": "服务器发生内存泄漏崩溃", "memory_type": "subconscious_dream", "credibility": 0.1, "involved_entities": ["server"]}]
    m_real = [{"fact_summary": "服务器发生内存泄漏崩溃", "memory_type": "episodic_experiential", "credibility": 1.0, "involved_entities": ["server"]}]

    avatar.update_memory(m_dream, "2026-11-20 10:10:00")
    assert len(avatar.core_memories) == 1
    assert avatar.core_memories[0].credibility == 0.1

    avatar.update_memory(m_real, "2026-11-20 10:20:00")
    assert len(avatar.core_memories) == 1
    assert avatar.core_memories[0].credibility == 1.0
    assert avatar.core_memories[0].memory_type == "episodic_experiential"
    assert avatar.core_memories[0].mention_count == 2

# ==================== 7. 全状态持久化与冷启动往返测试 (Round-Trip) ====================

def test_tc07_full_serialization_round_trip(tmp_path, mock_llm_client):
    """TC_07: 验证存档(含 datetime、关系图谱、浮点数) -> 冷启动读档 -> 继续 Tick 无报错"""
    orchestrator = AvatarOrchestrator(llm_client=mock_llm_client)
    orchestrator.storage_dir = str(tmp_path)  # 重定向存储目录到 pytest 临时文件夹

    avatar = PsiAvatar("cat_meet", "INTP-T", "engineer", DummyLoreFactory(), None)
    avatar.register_relationship(RelationalProfile(
        target_user_id="dad_01",
        relation_type="parent",
        intimacy_baseline=0.8,
        emotional_vulnerability=1.4,
        power_dynamic="superior",
        social_contract_lore="父亲契约"
    ))
    avatar.message_history.add_user_message("测试带时区的时间戳", speaker="dad_01")
    avatar.engine.m_layer.faith_shield = 0.45

    orchestrator.register_avatar("cat_meet", avatar)
    orchestrator.save_all_avatars()

    # 验证文件已生成且为合法 JSON
    saved_file = tmp_path / "cat_meet_psyche.json"
    assert saved_file.exists()

    # 创建全新的 Orchestrator 模拟进程重启后的冷启动恢复
    new_orchestrator = AvatarOrchestrator(llm_client=mock_llm_client)
    new_orchestrator.storage_dir = str(tmp_path)

    success = new_orchestrator.load_avatar_from_storage("cat_meet", DummyLoreFactory())
    assert success is True

    restored_avatar = new_orchestrator.avatars["cat_meet"]

    # 1. 验证浮点数精度与护盾状态无损恢复
    assert restored_avatar.engine.m_layer.faith_shield == pytest.approx(0.45)
    assert restored_avatar.engine.p_layer.ocean == avatar.engine.p_layer.ocean

    # 2. 验证社交关系图谱完整保留
    rel = restored_avatar.engine.p_layer.config.social_graph.get_relation("dad_01")
    assert rel.relation_type == "parent"
    assert rel.power_dynamic == "superior"
    # 3. 验证 m_layer 与 p_layer 共享同一份 config 实例
    assert restored_avatar.engine.m_layer.config is restored_avatar.engine.p_layer.config
    # 4. 验证恢复后的实例继续执行刺激与时钟推进不报 AttributeError
    restored_avatar.apply_appraisal_and_tick({"desirability": 0.5, "prospect_status": "none"}, speaker_id="dad_01")