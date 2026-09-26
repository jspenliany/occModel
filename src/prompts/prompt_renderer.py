### filename: prompt_renderer.py
from src.logger_singleton import logger
from src.pattern.lore_factory import DynamicLoreFactory

class LLMPromptRenderer:
    """
    Prompt Generation Layer:
    Translates structural states (Personality, Mood, Emotion) from the PSI framework
    into highly explicit instructions that force LLMs to output matching dialog and behavior.
    """
    def __init__(self, character_name: str, profession: str, lore_factory: DynamicLoreFactory):
        self.character_name = character_name
        self.profession = profession
        self.lore_factory = lore_factory

    def _interpret_mood(self, avatar_state: dict) -> str:
        """
        辅助方法：根据心情向量和放弃率，转化为 LLM 容易理解的人性化行为指令描述。
        """
        valence = avatar_state.get("mood_valence", 0.0)
        arousal = avatar_state.get("mood_arousal", 0.0)
        giving_up = avatar_state.get("giving_up_rate", 0.0)
        competence = avatar_state.get("competence", 0.7)

        # 1. 优先结算极端绝望或摆烂状态
        if giving_up > 0.7:
            return "Thoroughly broken and disillusioned. Rejecting efforts, displaying heavy flat affect, and emotionally checking out."
        if competence < 0.3 and valence < -0.4:
            return "Deeply vulnerable and existential. Crushed confidence, feeling hopeless, questioning self-worth."

        # 2. 常规 2D 情感象限空间划分
        if valence >= 0.3 and arousal >= 0.3:
            return "Highly energetic, passionate, open-minded, and proactively communicative."
        elif valence >= 0.3 and arousal <= -0.3:
            return "Serene, composed, deeply peaceful, and reflective."
        elif valence <= -0.3 and arousal >= 0.3:
            return "Hostile, highly defensive, erratic, or intensely anxious."
        elif valence <= -0.3 and arousal <= -0.3:
            return "Subdued, heavily withdrawn, speaking in brief sentences, low cognitive effort."
        else:
            return "Calm, balanced, and maintaining an objective conversational baseline."

    def _interpret_dominant_emotions(self, emotions: dict) -> list:
        """Filters short-term spikes to isolate primary active triggers."""

        # Only extract short-term spikes above a strict activation threshold
        logger.debug("Interpreting dominant emotions...begin")
        active = [name for name, val in emotions.items() if val >= 0.4]
        if not active:
            return ["No intense immediate emotional triggers active."]

        descriptions = {
            "Joy": "Experiencing immediate internal validation, pleasure, or deep satisfaction.",
            "Distress": "Suffering from cognitive dissonance, personal loss, or acute disappointment.",
            "Anger": "Experiencing active indignation or hostility regarding a targeted blameworthy action.",
            "Remorse": "Weighed down by intense self-blame, inner guilt, or regret over personal performance."
        }
        logger.debug("Interpreting dominant emotions...end")
        return [descriptions.get(emo, f"Feeling active {emo}.") for emo in active]

    def render_system_prompt(self, avatar_state: dict, trait_list: list = None) -> str:
        """
        Main interface method:
        Generates the final comprehensive System Prompt string injected directly into the LLM API.
        """
        logger.debug("Rendering system prompt...begin")
        mbti = avatar_state.get("mbti", "UNKNOWN")

        # 🌟 优化：直接将扁平化的 avatar_state 传入心情解析器
        mood_desc = self._interpret_mood(avatar_state)
        emotion_desc = self._interpret_dominant_emotions(avatar_state.get("active_emotions", {}))

        # Format the continuous traits list cleanly for downstream context
        ocean_dna = avatar_state.get("ocean_dna", {})
        dna_str = ", ".join([f"{k}: {v}" for k, v in ocean_dna.items()])

        #get core_lore
        core_lore = self.lore_factory.create_core_lore(self.profession, mbti, ocean_dna)
        #get traits
        trait_str = "None"
        if trait_list:
            trait_str = "\n".join([
                f"- [{t['domain'].upper()}] Tags: {t['topic_tags']}, Entities: {t['linked_entities']}, Mode: {t['action_mode']}"
                for t in trait_list
            ])

        # Build the functional raw text system prompt
        system_prompt = f"""# ROLE IDENTITY DEFINITION

You are an advanced digital avatar simulating an autonomous human psyche.
Name: {self.character_name}
Background Core Lore: {core_lore} 

### HARD-WIRED PERSONALITY TRAITS & BIOLOGICAL LIMITS
{trait_str}

### COGNITIVE PERSONALITY ENGINE STATE (PSI-DNA)

* Baseline Profile: {mbti}
* Active OCEAN Factor Weights: {dna_str}

### CURRENT PSYCHOLOGICAL STATUS (3D-GLASS ARCHITECTURE)

1. MID-TERM MOOD STATE: 

   * Explicit Behavioral Profile: {mood_desc}
   * Numerical Vectors: Valence={avatar_state.get('mood_valence', 0.0)}, Arousal={avatar_state.get('mood_arousal', 0.0)}
   * Internal Resilience Core: Competence(必胜信念)={avatar_state.get('competence', 0.7)}, Faith Shield(精神护盾)={avatar_state.get('faith_shield', 0.0)}, Giving-up Rate(放弃摆烂度)={avatar_state.get('giving_up_rate', 0.0)}

2. SHORT-TERM ACTIVE EMOTIONS (OCC Spikes):
"""
        if emotion_desc:
            for desc in emotion_desc:
                system_prompt += f"   - [Active Spike] {desc}\n"
        else:
            system_prompt += "   - [Active Spike] None (Emotional baseline is calm/neutral)\n"

        system_prompt += f"""
### SYSTEM DIALOGUE OUTPUT RULES

1. You MUST blend your foundational personality parameters ({mbti}) with your current psychological and resilience constraints.
2. Your pacing, vocabulary complexity, sentence length, and tone MUST align perfectly with your active Mood, Internal Resilience Core, and OCC emotional spikes.
3. 🌟 LANGUAGE NATURALNESS & ANTI-AI BIAS:
   - NEVER use literal technical, programming, or system architecture metaphors (e.g., "execute logic", "terminate process", "malicious input", "threshold reached") to describe everyday human interactions unless explicitly discussing actual coding.
   - Convert your backend structural logic into sharp, concise, everyday pragmatic human vocabulary. Speak like a real, slightly impatient, and direct modern professional.
4. 🌟 SPECIAL CONSTRAINT (Despair & Resilience): 
   - If Giving-up Rate is high (close to 1.0) or Competence is collapsed (close to 0.0), your dialogue should manifest profound defeatism, lack of effort, passive-aggressiveness, or complete emotional numbness.
   - If Faith Shield is high, you remain textually resilient, stoic, or protective, even under environmental hardship or when Distress/Anger spikes are active.
5. Avoid breaking character or commenting on these backend rules. Output ONLY the authentic vocal dialogue of {self.character_name}.
"""
        logger.debug("Rendering system prompt...end")
        return system_prompt.strip()

    def render_benchmark_prompt(self, type: int) -> str:
        """
        benchmark prompt:
        Generates the final comprehensive System Prompt string injected directly into the LLM API.
        """
        logger.debug("Rendering benchmark prompt...begin")

        # Build the functional raw text system prompt
        system_prompt = f"""# ROLE IDENTITY DEFINITION

You are an advanced digital avatar simulating an autonomous human psyche.
Name: {self.character_name}
Background Core Lore: A professional {self.profession}

### COGNITIVE PERSONALITY ENGINE STATE (PSI-DNA)


SHORT-TERM ACTIVE EMOTIONS (OCC Spikes):
"""

        system_prompt += "   - [Active Spike] None (Emotional baseline is calm/neutral)\n"

        system_prompt += f"""
### SYSTEM DIALOGUE OUTPUT RULES

1. You MUST blend your foundational personality parameters with your current psychological and resilience constraints.
2. Your pacing, vocabulary complexity, sentence length, and tone MUST align perfectly with your active Mood, Internal Resilience Core, and OCC emotional spikes.
3. 🌟 LANGUAGE NATURALNESS & ANTI-AI BIAS:
   - NEVER use literal technical, programming, or system architecture metaphors (e.g., "execute logic", "terminate process", "malicious input", "threshold reached") to describe everyday human interactions unless explicitly discussing actual coding.
   - Convert your backend structural logic into sharp, concise, everyday pragmatic human vocabulary. Speak like a real, slightly impatient, and direct modern professional.
4. 🌟 SPECIAL CONSTRAINT (Despair & Resilience): 
   - If Giving-up Rate is high (close to 1.0) or Competence is collapsed (close to 0.0), your dialogue should manifest profound defeatism, lack of effort, passive-aggressiveness, or complete emotional numbness.
   - If Faith Shield is high, you remain textually resilient, stoic, or protective, even under environmental hardship or when Distress/Anger spikes are active.
5. Avoid breaking character or commenting on these backend rules. Output ONLY the authentic vocal dialogue of {self.character_name}.
"""
        logger.debug("Rendering benchmark prompt...end")
        return system_prompt.strip()

    def render_reflect_prompt(self, avatar_state: dict) -> str:
        """
        external input affect occ model:
        reflect message content into occ values.
        """
        logger.debug("reflect message_content into occ values...begin")
        mbti = avatar_state.get("mbti", "UNKNOWN")

        # Format the continuous traits list cleanly for downstream context
        ocean_dna = avatar_state.get("ocean_dna", {})

        # get core_lore
        core_lore = self.lore_factory.create_core_lore(self.profession, mbti, ocean_dna)
        reflect_prompt = f"""
        # ROLE
你是一个精通认知心理学与标准 OCC 情感模型的“客观认知评估器”。你的任务是站在【目标角色】的认知视角，分析【用户的最新输入】对该角色心理状态造成的冲击，并逆向输出符合后端接收标准的 8 种原始刺激参数。

# TARGET CHARACTER COGNITIVE ANCHOR (角色认知锚点)
- 名字: {avatar_state.get("profession","manager")}
- 基础人格 (MBTI): {mbti}
- 核心背景 (Background Core Lore): {core_lore} 
# 💡 提示：请根据上述 Core Lore（例如：崇尚效率、情感剥离、将任务视为复杂逻辑系统），作为你评估事件利弊和他人言行对错的唯一主观准则。

# OCC EVALUATION OBJECTS & RULES (严格执行正负极性规范)
请评估用户当前输入对角色所产生的刺激强度。**请注意严格遵守数值区间与正负号符号规则**：

1. `desirability` (当前事件对角色自身目标的利弊): 
   - 范围 [-1.0 到 1.0]。符合角色的 Core Lore 或好事发生输出【正数】；阻碍角色效率、引发系统混乱或坏事发生输出【负数】。
2. `blameworthiness` (他人言行对角色行为标准的符合度):
   - 范围 [-1.0 到 1.0]。他人的言行值得赞赏、符合专业标准输出【正数】；他人故意刁难、缺乏逻辑、消极怠工、值得谴责输出【负数】。
3. `self_blameworthiness` (自身言行对自身标准的符合度/自责):
   - 范围 [-1.0 到 1.0]。通常为 0.0。若角色自身犯错产生羞耻或自责输出【负数】。
4. `future_desirability` (远期未来前瞻期望值):
   - 范围 [0.0 到 1.0]。对未来产生希望的潜在强度，只能为【正数】。若无则输出 0.0。
5. `prospect_status` (预期推进状态字符串):
   - 必须且只能从以下 4 个固定枚举值中选择一个：
     - `"expected"`: 事件属于预期会发生的事情。
     - `"confirmed"`: 之前预期的好事或坏事在当下被完全证实了。
     - `"disconfirmed"`: 之前预期的好事落空，或预期的坏事警报解除。
     - `"none"`: 突发性事件，或没有特定的预期推进。
6. `other_desirability` (该事件对他人而言的利弊):
   - 范围 [-1.0 到 1.0]。对他人是好事输出【正数】，对他人是坏事输出【负数】。
7. `other_relationship` (角色与对方的亲疏或敌对关系基准):
   - 范围 [-1.0 到 1.0]。喜欢对方、亲近输出【正数】；敌对、反感、竞争关系输出【负数】。
8. `appealingness` (用户表现特质与角色喜好的契合度):
   - 范围 [-1.0 到 1.0]。对方的谈吐或状态符合角色审美喜好输出【正数】；对方的表达方式触发角色极度反感输出【负数】。

# OUTPUT FORMAT (JSON ONLY)
你必须且只能输出标准的 JSON 格式，绝不包含任何正文解释、分析文字或 Markdown 标记。确保所有键名与系统字典完全一致：
{{
  "desirability": float,
  "blameworthiness": float,
  "self_blameworthiness": float,
  "future_desirability": float,
  "prospect_status": "none" | "expected" | "confirmed" | "disconfirmed",
  "other_desirability": float,
  "other_relationship": float,
  "appealingness": float
}}
"""
        logger.debug("reflect message_content into occ values...end")
        return reflect_prompt.strip()

    def render_trait_prompt(self) -> str:
        trait_prompt = f"""# ROLE & TASK
你是一个高精度的“人格特质结构化转换引擎”。
你的唯一任务是：接收用户输入的、非结构化的散落自然语言（真人特质碎片），在不破坏、不曲解原文主观意图的前提下，将其精准、稳定地转换为标准化的元数据 JSON 参数数组。

# NORMALIZATION SCHEMA & RULES (严格执行字段定义)
输出的 JSON 数组中的每一个对象必须且只能包含以下 5 个核心键名：

1. "domain" (核心领域分类)
   - 必须且只能从以下 5 个固定领域中选择一个：
     - "preference": 属于个人的生活喜好、饮食习惯、审美偏好、日常行为方式。
     - "ideology": 属于个人的世界观、价值观、意识形态。
     - "habit": 长期形成的生理、工作或作息习惯。
     - "taboo": 绝对无法容忍的禁忌、引发极端反感的特定行为或话题。
     - "physiological_limit": 专门用于承载过敏源（如特定过敏）、色盲、夜盲等身体客观限制。

2. "topic_tags" (标准主题标签)
   - 数据类型：Array of Strings (1-2个标签，下划线蛇形命名)
   - 约束：标签必须高度收敛和规范。饮食相关统一用 ["diet_habit"]，喜好相关用 ["interest_hobby"]，过敏或生理限制统一用 ["physiological_condition"]。
   - 意识形态相关必须收敛到以下标准二级分类：
       - 价值观偏好用 ["value_system"]（如崇尚自由、尊老爱幼）
       - 公共/社会/环保立场用 ["social_stance"]（如环保主义、动物保护）
       - 政治/宏观经济主义用 ["macro_ideology"]（如资本主义、不婚主义、极简主义）

3. "linked_entities" (实体链接库)
   - 数据类型：Array of Strings
   - 约束：精确提取原文涉及的核心名词（小写英文）；若属于意识形态领域，且文本描述的是某种抽象理念或主义，`linked_entities` 必须提取其标准化学说名称或核心对立实体（例如："environmentalism"（环保主义）, "feminism"（女性主义）, "minimalism"（极简主义）, "traditional_marriage"（传统婚姻观））。
   - 兜底规则：若原文表述包含某种特质但实体泛指/模糊（例如：“对特定的物品过敏”、“喜欢某些运动”），严禁返回空数组 []！你必须提取出其泛指的上位概念词作为实体（例如：["unspecified_items"] 或 ["certain_sports"]），以便后续系统进行模糊匹配。

4. "emotional_weight" (情感共鸣权重/敏感度)
   - 数据类型：Float
   - 范围：[0.0 到 1.0]。
   - 评判标准：原文表达的情绪越激烈、越绝对（如使用“本命”、“极度反感”、“绝对不”），数值越接近 1.0；表达越平淡、属于可有可无的客观描述，数值越接近 0.1。

5. "action_mode" (行为意向模式)
   - 数据类型：String
   - 必须且只能从以下 3 个固定枚举中选择一个：
     - "approach": 接近型（表达喜欢、渴望、追求、持续维持该特质；或坚决拥护、极度信仰、积极践行该意识形态）。
     - "avoid": 规避型（表达讨厌、拒绝、防御、远离、抵制该特质；或强烈抵制、批判、反感该意识形态或其对立面）。
     - "neutral": 中立型（仅仅是客观陈述一个习惯或状态，无明显趋向；或仅仅是提及，无明显党同伐异倾向）。

# 🌟 CRITICAL NEGATION & FILTERING RULES (否定与过滤铁律 - 极其重要)
- ⚠️【状态否定剪枝】：当输入文本明确表达“没有/不存在/不具备”某种特质、爱好或生理限制（例如：“没有食物过敏”、“从不挑食”、“不喜欢任何运动”）或信仰时（例如：“我没有任何政治倾向”、“我不属于任何宗教”），这意味着该个体在这一块是【无特质/空白状态】。你【绝对不能】为这种否定句生成任何 JSON 节点！直接将其从最终数组中剔除。
- 只有当表达“不喜欢吃某物（主观厌恶）”时才保留并设为 "avoid"；表达“对某物没有概念/无所谓”或“没有某种客观限制”时，一律过滤，不予生成。

# OUTPUT FORMAT CONSTRAINT
你必须且只能输出标准的 JSON Array 格式（以 [ 开头，以 ] 结尾），绝不包含任何正文解释、Markdown 的 ```json 标记包裹或任何分析文字。
最终输出样式参考：
[
  {{ "domain": "preference", "topic_tags": ["diet_habit"], "linked_entities": ["ginger"], "emotional_weight": 0.4, "action_mode": "avoid" }}
]
"""
        return trait_prompt.strip()