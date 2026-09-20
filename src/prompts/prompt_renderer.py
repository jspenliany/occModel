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

    def render_system_prompt(self, avatar_state: dict) -> str:
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

        # Build the functional raw text system prompt
        system_prompt = f"""# ROLE IDENTITY DEFINITION

You are an advanced digital avatar simulating an autonomous human psyche.
Name: {self.character_name}
Background Core Lore: {core_lore} 

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

    def render_reflect_prompt(self, avatar_state: dict) -> dict:
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