import pytest
from src.models.psi.personality import PersonalityLayer
from src.models.psi.engine_config import EngineConfig, RelationalProfile


class TestPersonalityLayer:

    def test_tc_per_01_init_valid_mbti_and_normalization(self):
        """TC_PER_01: 验证标准 MBTI（含小写与首尾空格）规范化及 OCEAN 区间映射"""
        p = PersonalityLayer("  intp-t  ")

        assert p.mbti == "INTP-T"
        assert isinstance(p.config, EngineConfig)
        assert set(p.ocean.keys()) == {"O", "C", "E", "A", "N"}

        # 验证映射结果严格落在 TraitRangeConfig 声明的区间内
        assert 0.7 <= p.get_trait("O") <= 0.9   # N (Intuition) -> Openness
        assert 0.1 <= p.get_trait("C") <= 0.3   # P (Perceiving) -> Conscientiousness
        assert 0.1 <= p.get_trait("E") <= 0.3   # I (Introversion) -> Extraversion
        assert 0.1 <= p.get_trait("A") <= 0.3   # T (Thinking) -> Agreeableness
        assert 0.7 <= p.get_trait("N") <= 0.95  # -T (Turbulent) -> Neuroticism

    def test_tc_per_02_init_invalid_mbti_fallback(self):
        """TC_PER_02: 验证非法 MBTI 输入安全回退至 DEFAULT 兜底区间 (0.4, 0.6)"""
        p_invalid = PersonalityLayer("XXXX-Z")
        for trait in ["O", "C", "E", "A", "N"]:
            val = p_invalid.get_trait(trait)
            assert 0.4 <= val <= 0.6

    def test_tc_per_03_get_trait_valid_and_missing_key(self):
        """TC_PER_03: 验证特质读取接口及缺失键名返回 0.5 兜底"""
        p = PersonalityLayer("ENFJ-A")
        p.ocean["O"] = 0.888

        assert p.get_trait("O") == 0.888
        assert p.get_trait("NON_EXISTENT_TRAIT") == 0.5

    def test_tc_per_04_dynamic_reshape_trait_clamping(self):
        """TC_PER_04: 验证自循环习惯微调的步长累加与 [0.0, 1.0] 边界钳制"""
        p = PersonalityLayer("INTP-T")
        p.ocean["A"] = 0.08
        p.ocean["N"] = 0.96

        # 正常递减
        p.dynamic_reshape_trait("A", -0.05)
        assert p.get_trait("A") == pytest.approx(0.03)

        # 触底钳制：0.03 - 0.05 必须锁死在 0.0
        p.dynamic_reshape_trait("A", -0.05)
        assert p.get_trait("A") == 0.0

        # 触顶钳制：0.96 + 0.08 必须锁死在 1.0
        p.dynamic_reshape_trait("N", 0.08)
        assert p.get_trait("N") == 1.0

        # 异常键名容错：传入非法特质名不抛出异常，且不污染字典
        p.dynamic_reshape_trait("INVALID_KEY", 0.5)
        assert "INVALID_KEY" not in p.ocean

    def test_tc_per_05_paradigm_shift_by_external_source(self, capsys):
        """TC_PER_05: 验证外部权威/书籍顿悟的强制观念反转与越界钳制"""
        p = PersonalityLayer("INTP-T")
        p.ocean["A"] = 0.15

        # 1. 正常范围内的降维打击反转
        p.paradigm_shift_by_external_source("A", "阅读《非暴力沟通》", 0.92)
        assert p.get_trait("A") == 0.92

        # 验证控制台输出了重塑日志
        captured = capsys.readouterr()
        assert "[观念崩塌与重塑]" in captured.out
        assert "非暴力沟通" in captured.out

        # 2. 边界钳制测试：传入大于 1.0 或小于 0.0 的强制值
        p.paradigm_shift_by_external_source("A", "极端刺激", 1.5)
        assert p.get_trait("A") == 1.0

        p.paradigm_shift_by_external_source("A", "极端刺激", -0.5)
        assert p.get_trait("A") == 0.0

    def test_tc_per_06_serialization_round_trip_with_config(self):
        """TC_PER_06: 验证 to_dict -> from_dict 完整保留浮点数精度与动态修改的 config"""
        p = PersonalityLayer("INTJ-T")
        # 注入高精度浮点数与动态配置修改
        p.ocean["O"] = 0.8123456789
        p.config.cognitive_filter.bad_event_distortion.pessimist = 3.2
        p.config.social_graph.register_relation(RelationalProfile(
            target_user_id="spouse_01",
            relation_type="spouse",
            intimacy_baseline=0.95,
            emotional_vulnerability=1.8,
            power_dynamic="equal",
            social_contract_lore="伴侣"
        ))

        snapshot = p.to_dict()
        assert "mbti" in snapshot
        assert "ocean" in snapshot
        assert "config" in snapshot

        # 从快照重建实例
        restored_p = PersonalityLayer.from_dict(snapshot)

        assert restored_p.mbti == "INTJ-T"
        assert restored_p.get_trait("O") == pytest.approx(0.8123456789)
        assert restored_p.config.cognitive_filter.bad_event_distortion.pessimist == 3.2
        rel = restored_p.config.social_graph.get_relation("spouse_01")
        assert rel.relation_type == "spouse"
        assert rel.intimacy_baseline == 0.95

    def test_tc_per_07_from_dict_legacy_compatibility(self):
        """TC_PER_07: 验证反序列化不包含 config 字段的旧版存档时自动兜底默认配置"""
        legacy_data = {
            "mbti": "ESFP-A",
            "ocean": {"O": 0.6, "C": 0.2, "E": 0.85, "A": 0.8, "N": 0.15}
        }

        restored_p = PersonalityLayer.from_dict(legacy_data)
        assert restored_p.mbti == "ESFP-A"
        assert restored_p.get_trait("E") == 0.85
        assert isinstance(restored_p.config, EngineConfig)
        assert restored_p.config.cognitive_filter.bad_event_distortion.pessimist == 2.0
