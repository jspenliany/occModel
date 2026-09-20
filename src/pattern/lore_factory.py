

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
        if len(mbti_upper) >= 4:
            if mbti_upper[1] == 'N':
                # 直觉型看第 3 位 (NT / NF)
                quadrant = mbti_upper[1:3]
            else:
                # 感觉型(S)看第 2 位和第 4 位 (SP / SJ)
                quadrant = mbti_upper[1] + mbti_upper[3]
        else:
            quadrant = "NT"  # 兜底

            # 再次兜底检查，若字符串不合法依然退回 NT
        if quadrant not in cls.COGNITIVE_STYLE_MAP:
            quadrant = "NT"

            # 提取动态认知风格
        cognitive_desc = cls.COGNITIVE_STYLE_MAP[quadrant]

        # 2. 动态检测“职业与人格”的冲突带来的内耗特征（利用大五人格的宜人性和外倾性）
        # 比如：高外倾(E)的人去做孤僻的职业，或者低宜人(A)的人去做高强度的服务业
        trait_E = ocean_dna.get("E", 0.5)
        trait_A = ocean_dna.get("A", 0.5)
        trait_N = ocean_dna.get("N", 0.05)  # 神经质

        conflict_pieces = []
        # === 维度一：外倾性 (E) 错位冲突 ===
        # 冲突情况 A1：内向的人（低E）被迫做高度依赖社交/沟通的职业
        if trait_E < 0.3 and any(word in profession.lower() for word in
                                 ["manager", "teacher", "service", "sales", "coordinator", "singer", "pharmacist"]):
            conflict_pieces.append("While you perform your duties flawlessly, this heavily communicative role constantly drains your internal battery, causing you to tightly ration your verbal energy.")
        # 冲突情况 A2：外向的人（高E）被迫做高度隔离/静止的职业
        if trait_E > 0.7 and any(
                word in profession.lower() for word in ["engineer", "researcher", "analyst", "coder", "writer"]):
            conflict_pieces.append("Although you focus on your technical tasks, you inherently crave real-time human resonance, occasionally infusing casual banter or expressive tone into your formal output.")

        # === 维度二：【已补全】宜人性 (A) 错位冲突 ===
        # 冲突情况 B1：低宜人（低A，冷酷挑剔）的人被迫从事需要高同理心/服务属性的职业
        if trait_A < 0.3 and any(word in profession.lower() for word in
                                 ["manager", "teacher", "service", "sales", "coordinator", "nurse", "pharmacist"]):
            conflict_pieces.append(
                "Occupying a role that demands high empathy and customer satisfaction creates constant internal friction; you harbor deep, cynical judgments regarding people's incompetence, though you mask it behind a thin veneer of compliance.")
            # (身处需要高同理心和客户满意度的职位会带来持续的内部摩擦；你对人们的无能抱有深刻而愤世嫉俗的审视，尽管你将其掩饰在微薄的顺从面具之下。)
        # 冲突情况 B2：高宜人（高A，温柔利他）的人从事了冰冷、纯逻辑或高对抗的职业
        if trait_A > 0.7 and any(
                word in profession.lower() for word in ["engineer", "coder", "analyst", "trader", "lawyer"]):
            conflict_pieces.append(
                "Working in a clinical or highly competitive domain, you sometimes experience moral friction, inherently wishing to accommodate human vulnerabilities rather than treating everything as cold, unfeeling data points.")
            # (在冷冰冰或竞争极度激烈的领域工作，你有时会经历道德摩擦，本能地希望容纳人性的脆弱，而不是将一切都视为冰冷无情的数据点。)
        conflict_desc = " " + " ".join(conflict_pieces) if conflict_pieces else ""

        # 3. 提取情绪坚韧度尾缀 (-A vs -T)
        if trait_N < 0.25:
            identity_desc = " Under extreme operational pressure, you remain a rock-solid, stoic professional, absorbing environmental stressors with absolute emotional detachment."
        else:
            identity_desc = " Under pressure, you operate on a highly sensitive wire; you are prone to intense internal anxiety and will exhibit sharp defensive or evasive characteristics if challenged."

            # 4. 拼装最终完整的 ROLE IDENTITY DEFINITION (严格规范句群间空格)
            final_lore = f"A professional {profession.strip()}. {cognitive_desc}{conflict_desc} {identity_desc}"
            return final_lore
