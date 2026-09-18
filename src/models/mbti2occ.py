import random
from src.models.psi.engine_config import EngineConfig
from src.logger_singleton import logger

class MBTIToOCCEngine:
    def __init__(self):
        # Base mapping dict defining default values for each MBTI trait character
        # High value = closer to 1.0, Low value = closer to 0.0
        # self.trait_ranges = {
        #     'E': (0.65, 0.90), 'I': (0.10, 0.35),  # Maps to Extraversion
        #     'N': (0.65, 0.90), 'S': (0.10, 0.35),  # Maps to Openness
        #     'F': (0.65, 0.90), 'T': (0.10, 0.35),  # Maps to Agreeableness
        #     'J': (0.65, 0.90), 'P': (0.10, 0.35),  # Maps to Conscientiousness
        #     'T_suffix': (0.65, 0.90), 'A_suffix': (0.10, 0.35)  # Maps to Neuroticism
        # }
        logger.debug("MBTIToOCCEngine...init")
        self.engine_config = EngineConfig()

    def convert_mbti_to_ocean(self, mbti_string: str) -> dict:
        """
        Converts an MBTI string (e.g., 'INFP-T', 'INTJ-A') to an OCEAN profile.
        Values range between 0.0 and 1.0.
        """
        logger.debug('Converting MBTI to OCEAN...begin')
        clean_mbti = mbti_string.upper().strip()

        # Parse basic 4 traits and the identity suffix
        if '-' in clean_mbti:
            base_mbti, suffix = clean_mbti.split('-')
        else:
            base_mbti, suffix = clean_mbti, 'A'  # Default to Assertive if missing

        if len(base_mbti) != 4:
            logger.error('Invalid MBTI string: {}'.format(mbti_string))
            raise ValueError("Invalid MBTI format. Expected format like 'INFJ-T' or 'ESTP'.")

        # Extract MBTI components
        mbti_e_i, mbti_n_s, mbti_t_f, mbti_p_j = base_mbti[0], base_mbti[1], base_mbti[2], base_mbti[3]

        ranges = self.config.mbti_ranges
        default_range = ranges.DEFAULT

        # Generate continuous OCEAN scores using specific uniform distribution slices
        suffix_key = f"{suffix}_s"
        ocean = {
            "O": random.uniform(*getattr(ranges, mbti_n_s, default_range)),
            "C": random.uniform(*getattr(ranges, mbti_p_j, default_range)),
            "E": random.uniform(*getattr(ranges, mbti_e_i, default_range)),
            "A": random.uniform(*getattr(ranges, mbti_t_f, default_range)),
            "N": random.uniform(*getattr(ranges, suffix_key, default_range))
        }
        logger.debug('Converting MBTI to OCEAN...end')
        return ocean

    def calculate_occ_intensities(self, ocean: dict, stimulus: dict) -> dict:
        """
        Calculates resulting OCC emotion intensities based on OCEAN personality traits
        and a specific incoming external environmental stimulus.
        """
        logger.debug('Calculating OCC emotion intensities...begin')

        # 1. 提取原始环境刺激信号 (Raw Stimulus Signals)
        desirability = stimulus.get("desirability", 0.0)
        raw_joy = desirability if desirability > 0 else 0.0
        raw_distress = abs(desirability) if desirability < 0 else 0.0
        raw_reproach = stimulus.get("blameworthiness", 0.0)
        raw_shame = stimulus.get("self_blameworthiness", 0.0)

        # 2. 动态计算通用人格基线阈值 (Dynamic Threshold Calculation)
        thresholds = {}
        occ_cfg = self.config.occ_engine.emotions

        for emotion_name, cfg in occ_cfg.items():
            t_cfg = cfg.threshold
            trait_val = ocean[t_cfg.ocean_trait]
            actual_trait = (1.0 - trait_val) if t_cfg.invert_trait else trait_val
            thresholds[emotion_name] = t_cfg.base_multiplier * actual_trait

        # 3. 准备输出字典
        occ_outputs = {}

        # Helper: 计算人格乘法系数的乘积链
        def _get_personality_factor(emotion_key: str) -> float:
            factor = 1.0
            for p_cfg in occ_cfg[emotion_key].personality_multipliers:
                trait_val = ocean[p_cfg.ocean_trait]
                actual_trait = (1.0 - trait_val) if p_cfg.invert_trait else trait_val
                factor *= (p_cfg.base_offset + actual_trait) if p_cfg.base_offset >= 1.0 else actual_trait
            return factor

        # --- 1. OCC Joy (Event-based) ---
        joy_intensity = (raw_joy * _get_personality_factor("Joy")) - thresholds["Joy"]
        occ_outputs["Joy"] = max(0.0, min(1.0, joy_intensity))

        # --- 2. OCC Distress (Event-based) ---
        distress_intensity = (raw_distress * _get_personality_factor("Distress")) - thresholds["Distress"]
        occ_outputs["Distress"] = max(0.0, min(1.0, distress_intensity))

        # --- 3. OCC Anger (Compound: Reproach + Distress) ---
        if raw_reproach > 0 and raw_distress > 0:
            raw_anger = (raw_reproach + raw_distress) / 2
            anger_intensity = (raw_anger * _get_personality_factor("Anger")) - thresholds["Anger"]
            occ_outputs["Anger"] = max(0.0, min(1.0, anger_intensity))
        else:
            occ_outputs["Anger"] = 0.0

        # --- 4. OCC Remorse (Compound: Shame + Distress) ---
        if raw_shame > 0 and raw_distress > 0:
            raw_remorse = (raw_shame + raw_distress) / 2
            remorse_intensity = (raw_remorse * _get_personality_factor("Remorse")) - thresholds["Remorse"]
            occ_outputs["Remorse"] = max(0.0, min(1.0, remorse_intensity))
        else:
            occ_outputs["Remorse"] = 0.0
        logger.debug('Calculating OCC emotion intensities...end')
        return occ_outputs


# ==========================================
# Execution & Testing Showcase
# ==========================================
if __name__ == "__main__":
    engine = MBTIToOCCEngine()

    # Define two opposing virtual personas
    persona_a_mbti = "INTJ-A"
    persona_b_mbti = "INFP-T"

    # Convert profiles to continuous values
    ocean_a = engine.convert_mbti_to_ocean(persona_a_mbti)
    ocean_b = engine.convert_mbti_to_ocean(persona_b_mbti)

    print(f"--- [Personality Initialization Verification] ---")
    print(f"{persona_a_mbti} -> OCEAN Vector Elements: " + ", ".join([f"{k}: {v:.2f}" for k, v in ocean_a.items()]))
    print(f"{persona_b_mbti} -> OCEAN Vector Elements: " + ", ".join([f"{k}: {v:.2f}" for k, v in ocean_b.items()]))

    # Scenario: The user strictly criticizes a mistake made by the virtual character
    negative_stimulus = {
        "desirability": -0.6,  # Event outcome is highly undesirable
        "blameworthiness": 0.7,  # The user acted harshly (reproachable)
        "self_blameworthiness": 0.5  # The AI agent also knows it made an actual mistake
    }

    print(f"\n--- [Stimulus Processing Output] ---")
    print(f"Incoming Stimulus Data: {negative_stimulus}")

    emotions_a = engine.calculate_occ_intensities(ocean_a, negative_stimulus)
    emotions_b = engine.calculate_occ_intensities(ocean_b, negative_stimulus)

    print(f"\n[{persona_a_mbti} (The Rational Architect)] Responding Intensities:")
    for emotion, value in emotions_a.items():
        print(f" - {emotion}: {value:.2f}")

    print(f"\n[{persona_b_mbti} (The Sensitive Mediator)] Responding Intensities:")
    for emotion, value in emotions_b.items():
        print(f" - {emotion}: {value:.2f}")
