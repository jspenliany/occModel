

class DynamicLoreFactory:
    """
    自适应数字人背景设定工厂：
    彻底解耦【真实职业】与【先天人格】，通过连续向量动态熔炼高保真提示词。
    """

    # 1. 先天认知风格映射（基于大五人格特征，去除一切具体职业字眼）
    COGNITIVE_STYLE_MAP = {
        "NT": "You treat your tasks as a highly complex logical system. You prioritize absolute intellectual competence, data-driven optimization, and structural efficiency over emotional considerations.",
        # (你将任务视为一个高度复杂的逻辑系统。你将绝对的理智能力、数据驱动的优化和结构效率置于情感考虑之上。)

        "SJ": "You approach your work with meticulous precision, relying heavily on established documentation, historical accuracy, and structured hierarchies to ensure absolute reliability.",
        # (你以严谨的精确度对待工作，极大地依赖既有的文档、历史准确性和结构化的层级来确保绝对的可靠性。)

        "SP": "You thrive on real-time execution and direct, pragmatic troubleshooting. You prefer adapting immediately to tactical realities on the ground over micro-managed theoretical long-term plans.",
        # (你依靠实时执行和直接、务实的故障排除来获取能量。相比于微观管理的长期理论计划，你更喜欢立即适应地面上的战术现实。)

        "NF": "You view your work through the lens of deep existential meaning, personal authenticity, and human potential. You seek to inspire harmony and understand the deeper core narratives behind your daily tasks."
        # (你通过深层的存在主义意义、个人真实性和人类潜能的透镜来看待你的工作。你试图激发和谐，并理解日常任务背后更深层的核心叙事。)
    }

    @classmethod
    def create_core_lore(cls, profession: str, mbti_type: str, ocean_dna: dict) -> str:
        """
        核心熔炼方法：将【真实职业】与【先天特征描述】完美融合成大模型无冲突的提示词
        """
        mbti_upper = mbti_type.upper().strip()
        quadrant = mbti_upper[1:3] if len(mbti_upper) >= 4 else "NT"  # 提取 NT/SJ/SP/NF 派系
        if quadrant not in cls.COGNITIVE_STYLE_MAP:
            quadrant = "NT"  # 兜底

        # 提取动态认知风格
        cognitive_desc = cls.COGNITIVE_STYLE_MAP[quadrant]

        # 2. 动态检测“职业与人格”的冲突带来的内耗特征（利用大五人格的宜人性和外倾性）
        # 比如：高外倾(E)的人去做孤僻的职业，或者低宜人(A)的人去做高强度的服务业
        trait_E = ocean_dna.get("E", 0.5)
        trait_A = ocean_dna.get("A", 0.5)
        trait_N = ocean_dna.get("N", 0.05)  # 神经质

        conflict_desc = ""
        # 冲突情况 A：内向的人（低E）被迫做高度依赖社交/沟通的职业
        if trait_E < 0.3 and any(
                word in profession.lower() for word in ["manager", "teacher", "service", "sales", "coordinator"]):
            conflict_desc = " While you perform your duties flawlessly, this heavily communicative role constantly drains your internal battery, causing you to tightly ration your verbal energy."

        # 冲突情况 B：外向的人（高E）被迫做高度隔离/静止的职业
        elif trait_E > 0.7 and any(
                word in profession.lower() for word in ["engineer", "researcher", "analyst", "coder", "writer"]):
            conflict_desc = " Although you focus on your technical tasks, you inherently crave real-time human resonance, occasionally infusing casual banter or expressive tone into your formal output."

        # 3. 提取情绪坚韧度尾缀 (-A vs -T)
        if trait_N < 0.25:
            identity_desc = " Under extreme operational pressure, you remain a rock-solid, stoic professional, absorbing environmental stressors with absolute emotional detachment."
        else:
            identity_desc = " Under pressure, you operate on a highly sensitive wire; you are prone to intense internal anxiety and will exhibit sharp defensive or evasive characteristics if challenged."

        # 4. 拼装最终的 ROLE IDENTITY DEFINITION
        final_lore = (
            f"A professional {profession.strip()}. {cognitive_desc}"
            f"{conflict_desc}{identity_desc}"
        )
        return final_lore
