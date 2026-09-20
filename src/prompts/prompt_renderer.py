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
        Main interface method:
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