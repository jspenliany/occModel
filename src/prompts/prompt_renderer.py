### filename: prompt_renderer.py

class LLMPromptRenderer:
    """
    Prompt Generation Layer:
    Translates structural states (Personality, Mood, Emotion) from the PSI framework
    into highly explicit instructions that force LLMs to output matching dialog and behavior.
    """
    def init(self, character_name: str, core_lore: str):
        self.character_name = character_name
        self.core_lore = core_lore

    def _interpret_mood(self, mood: dict) -> str:
        """Translates numerical Valence and Arousal variables into clear behaviors."""
        v = mood.get("valence", 0.0)
        a = mood.get("arousal", 0.0)
        if v >= 0.3 and a >= 0.3:
            return "Highly excited, energetic, exceptionally proactive, and expressive."
        elif v >= 0.3 and a < -0.3:
            return "Calm, deeply relaxed, serene, peaceful, and thoroughly content."
        elif v < -0.3 and a >= 0.3:
            return "Hostile, highly agitated, tense, easily triggered, or defensive."
        elif v < -0.3 and a < -0.3:
            return "Sullen, emotionally drained, exhausted, unresponsive, and clinically unmotivated."
        else:
            return "Neutral, composed, steady, and emotionally balanced."

    def _interpret_dominant_emotions(self, emotions: dict) -> list:
        """Filters short-term spikes to isolate primary active triggers."""

        # Only extract short-term spikes above a strict activation threshold

        active = [name for name, val in emotions.items() if val >= 0.4]
        if not active:
            return ["No intense immediate emotional triggers active."]

        descriptions = {
        "Joy": "Experiencing immediate internal validation, pleasure, or deep satisfaction.",
        "Distress": "Suffering from cognitive dissonance, personal loss, or acute disappointment.",
        "Anger": "Experiencing active indignation or hostility regarding a targeted blameworthy action.",
        "Remorse": "Weighed down by intense self-blame, inner guilt, or regret over personal performance."
        }
        return [descriptions.get(emo, f"Feeling active {emo}.") for emo in active]

    def render_system_prompt(self, avatar_state: dict) -> str:
        """
        Main interface method:
        Generates the final comprehensive System Prompt string injected directly into the LLM API.
        """
        mbti = avatar_state.get("mbti", "UNKNOWN")
        mood_desc = self._interpret_mood(avatar_state.get("current_mood", {}))
        emotion_descs = self._interpret_dominant_emotions(avatar_state.get("active_emotions", {}))
        ### Format the continuous traits list cleanly for downstream context

        dna_str = ", ".join([f"{k}: {v}" for k, v in avatar_state.get("ocean_dna", {}).items()])

        # Build the functional raw text system prompt
        system_prompt = f"""# ROLE IDENTITY DEFINITION
        
        You are an advanced digital avatar simulating an autonomous human psyche.
        Name: {self.character_name}
        Background Core Lore: {self.core_lore} 
        
        ### COGNITIVE PERSONALITY ENGINE STATE (PSI-DNA)
        
        * Baseline Profile: {mbti}
        * Active OCEAN Factor Weights: {dna_str}
        
        ### CURRENT PSYCHOLOGICAL STATUS (3D-GLASS ARCHITECTURE)
        
        1. MID-TERM MOOD STATE: 
        
          * Explicit Behavioral Profile: {mood_desc}
          * Numerical Vectors: Valence={avatar_state['current_mood']['valence']}, Arousal={avatar_state['current_mood']['arousal']}
        2. SHORT-TERM ACTIVE EMOTIONS (OCC Spikes):
        """
        for desc in emotion_descs:
            system_prompt += f"   - [Active Spike] {desc}\n"

        system_prompt += f"""
        
        ### SYSTEM DIALOGUE OUTPUT RULES
        
        1. You MUST blend your foundational personality parameters ({mbti}) with your current physiological constraints.
        2. Your pacing, vocabulary complexity, sentence length, and tone MUST align perfectly with your active Mood and OCC emotional spikes.
        3. If Anger or Distress is active, your text generation should naturally display defensive or evasive characteristics matching your profile.
        4. Avoid breaking character or commenting on these backend rules. Output only the authentic vocal dialogue of {self.character_name}.
        """
        return system_prompt.strip()