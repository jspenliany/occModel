import random
import math


class PSIEffectEngine:
    def __init__(self, mbti_string: str):
        # 1. PERSONALITY LAYER (Static DNA)
        self.personality = self._initialize_ocean(mbti_string)

        # 2. MOOD LAYER (Mid-term State: Valence [-1, 1], Arousal [-1, 1])
        # Initialized to a slight bias based on Extraversion and Neuroticism
        self.mood = {
            "valence": (self.personality["E"] - self.personality["N"]) * 0.3,
            "arousal": (self.personality["E"] + self.personality["N"] - 1.0) * 0.2
        }

        # 3. EMOTION LAYER (Short-term active OCC pool)
        self.emotions = {
            "Joy": 0.0, "Distress": 0.0, "Anger": 0.0, "Remorse": 0.0,
            "Hope": 0.0, "Fear": 0.0, "Admiration": 0.0, "Reproach": 0.0
        }

        # System Configuration Decay Rates
        self.mood_decay = 0.05  # Mood pulls slowly back to baseline per tick
        self.emotion_decay = 0.25  # Short-term emotions drain quickly per tick

    def _initialize_ocean(self, mbti: str) -> dict:
        """Converts an MBTI string to explicit continuous OCEAN weights [0.0, 1.0]."""
        clean = mbti.upper().strip().split('-')
        base = clean[0]
        suffix = clean[1] if len(clean) > 1 else 'A'

        ranges = {'E': (0.7, 0.9), 'I': (0.1, 0.3), 'N': (0.7, 0.9), 'S': (0.1, 0.3),
                  'F': (0.7, 0.9), 'T': (0.1, 0.3), 'J': (0.7, 0.9), 'P': (0.1, 0.3),
                  'A_s': (0.1, 0.3), 'T_s': (0.7, 0.9)}

        return {
            "O": random.uniform(*ranges.get(base[1], (0.4, 0.6))),
            "C": random.uniform(*ranges.get(base[3], (0.4, 0.6))),
            "E": random.uniform(*ranges.get(base[0], (0.4, 0.6))),
            "A": random.uniform(*ranges.get(base[2], (0.4, 0.6))),
            "N": random.uniform(*ranges.get(f"{suffix}_s", (0.4, 0.6)))
        }

    # =========================================================================
    # EXTENSION INTERFACES (Hooks for External Needs / Systems)
    # =========================================================================

    def interface_modify_mood(self, delta_valence: float, delta_arousal: float):
        """
        External API Hook: Allows physiological internal system demands (e.g., PSI hunger,
        energy drains, battery, or persistent health stats) to shift the mood layer directly.
        """
        self.mood["valence"] = max(-1.0, min(1.0, self.mood["valence"] + delta_valence))
        self.mood["arousal"] = max(-1.0, min(1.0, self.mood["arousal"] + delta_arousal))

    def interface_inject_internal_emotion(self, emotion_name: str, raw_intensity: float):
        """
        External API Hook: Allows direct simulation overrides or internal biological sparks
        to forcefully fire or increment an immediate short-term OCC emotion state.
        """
        if emotion_name in self.emotions:
            self.emotions[emotion_name] = max(0.0, min(1.0, self.emotions[emotion_name] + raw_intensity))

    # =========================================================================
    # CORE COGNITIVE PROCESSING PIPELINE
    # =========================================================================

    def update_per_tick(self):
        """
        System clock cycle step. Simulates time decay over all active mood blocks
        and immediate OCC instances back toward natural resting equilibriums.
        """
        # Mood slowly decays back to personality-driven baseline equilibrium
        target_v = (self.personality["E"] - self.personality["N"]) * 0.3
        target_a = (self.personality["E"] + self.personality["N"] - 1.0) * 0.2

        self.mood["valence"] += (target_v - self.mood["valence"]) * self.mood_decay
        self.mood["arousal"] += (target_a - self.mood["arousal"]) * self.mood_decay

        # OCC Emotions drain rapidly back down toward complete stillness (0.0)
        for emo in self.emotions:
            self.emotions[emo] = max(0.0, self.emotions[emo] - self.emotion_decay)

    def process_external_stimulus(self, appraisal: dict):
        """
        Calculates appraisal events using the concurrent three-layer system parameters.
        The current active mood filters incoming data before altering the OCC output.
        """
        # Extract immediate cognitive evaluations from stimulus
        desirability = appraisal.get("desirability", 0.0)  # range [-1.0, 1.0]
        blameworthiness = appraisal.get("blameworthiness", 0.0)  # range [0.0, 1.0]
        self_blameworthiness = appraisal.get("self_blameworthiness", 0.0)  # range [0.0, 1.0]

        # 1. MOOD INTERFERENCE FILTERS (Mood shifts cognitive perception metrics)
        # Being in a bad mood (negative valence) amplifies negative events and suppresses positive ones
        mood_multiplier = 1.0 - (self.mood["valence"] * 0.5)

        # 2. CALCULATE DYNAMIC OCC INSTANT THRESHOLDS
        joy_threshold = 0.3 * (1.0 - self.personality["E"])
        distress_threshold = 0.3 * (1.0 - self.personality["N"])

        # 3. EVALUATING OCC INSTANCES WITH PERSONALITY & FILTERED MOOD
        if desirability > 0:
            joy_spark = (desirability * (1.0 + self.personality["E"])) * (2.0 - mood_multiplier) - joy_threshold
            self.emotions["Joy"] = max(0.0, min(1.0, self.emotions["Joy"] + joy_spark))
            # Positive events nudge the mid-term mood valence up slightly
            self.interface_modify_mood(delta_valence=joy_spark * 0.2, delta_arousal=joy_spark * 0.1)
        elif desirability < 0:
            distress_spark = (abs(desirability) * (1.0 + self.personality["N"])) * mood_multiplier - distress_threshold
            self.emotions["Distress"] = max(0.0, min(1.0, self.emotions["Distress"] + distress_spark))
            # Negative events tank the mood valence down and increase internal arousal
            self.interface_modify_mood(delta_valence=-distress_spark * 0.3, delta_arousal=distress_spark * 0.2)

        # 4. COMPOUND PROCESSORS (Anger / Remorse)
        if blameworthiness > 0 and desirability < 0:
            anger_spark = ((blameworthiness + abs(desirability)) / 2) * (1.5 - self.personality["A"]) * mood_multiplier
            self.emotions["Anger"] = max(0.0, min(1.0, self.emotions["Anger"] + anger_spark))

        if self_blameworthiness > 0 and desirability < 0:
            remorse_spark = ((self_blameworthiness + abs(desirability)) / 2) * (1.0 + self.personality["C"]) * (
                        1.0 + self.personality["N"])
            self.emotions["Remorse"] = max(0.0, min(1.0, self.emotions["Remorse"] + remorse_spark))


# ==========================================
# SIMULATION SHOWCASE RUN
# ==========================================
if __name__ == "__main__":
    # Instantiate a highly sensitive, introverted, empathetic character persona
    ai_character = PSIEffectEngine("INFP-T")

    print("--- [1. INITIAL CONFIGURATION VERIFICATION] ---")
    print("Personality (OCEAN Weights):", {k: round(v, 2) for k, v in ai_character.personality.items()})
    print("Starting Mood Baseline:", {k: round(v, 2) for k, v in ai_character.mood.items()})

    # Event 1: An external user insults the agent's work performance
    user_insult = {"desirability": -0.7, "blameworthiness": 0.8, "self_blameworthiness": 0.3}
    print("\n--- [2. EXTERNAL EVENT: CRITICAL USER INSULT SUBMITTED] ---")
    ai_character.process_external_stimulus(user_insult)
    print("Active Emotion States:", {k: round(v, 2) for k, v in ai_character.emotions.items()})
    print("Modified Mid-Term Mood State:", {k: round(v, 2) for k, v in ai_character.mood.items()})

    # Event 2: Physical system internal hardware degradation triggers a mood interface hook directly
    print("\n--- [3. INTERNAL API INTERFACE HOOK INJECTION: LOW BATTERY/ENERGY BRAIN DRAIN] ---")
    ai_character.interface_modify_mood(delta_valence=-0.4, delta_arousal=0.3)
    print("Mood State After Direct Internal Push:", {k: round(v, 2) for k, v in ai_character.mood.items()})

    # Event 3: Time steps pass via clock ticks
    print("\n--- [4. SYSTEM TIME CLOCK PROGRESSION TICK RUNNING] ---")
    ai_character.update_per_tick()
    print("Decayed Short-Term Emotions:", {k: round(v, 2) for k, v in ai_character.emotions.items()})
    print("Restored/Decayed Mood State:", {k: round(v, 2) for k, v in ai_character.mood.items()})
