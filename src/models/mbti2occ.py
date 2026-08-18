import random


class MBTIToOCCEngine:
    def __init__(self):
        # Base mapping dict defining default values for each MBTI trait character
        # High value = closer to 1.0, Low value = closer to 0.0
        self.trait_ranges = {
            'E': (0.65, 0.90), 'I': (0.10, 0.35),  # Maps to Extraversion
            'N': (0.65, 0.90), 'S': (0.10, 0.35),  # Maps to Openness
            'F': (0.65, 0.90), 'T': (0.10, 0.35),  # Maps to Agreeableness
            'J': (0.65, 0.90), 'P': (0.10, 0.35),  # Maps to Conscientiousness
            'T_suffix': (0.65, 0.90), 'A_suffix': (0.10, 0.35)  # Maps to Neuroticism
        }

    def convert_mbti_to_ocean(self, mbti_string: str) -> dict:
        """
        Converts an MBTI string (e.g., 'INFP-T', 'INTJ-A') to an OCEAN profile.
        Values range between 0.0 and 1.0.
        """
        clean_mbti = mbti_string.upper().strip()

        # Parse basic 4 traits and the identity suffix
        if '-' in clean_mbti:
            base_mbti, suffix = clean_mbti.split('-')
        else:
            base_mbti, suffix = clean_mbti, 'A'  # Default to Assertive if missing

        if len(base_mbti) != 4:
            raise ValueError("Invalid MBTI format. Expected format like 'INFJ-T' or 'ESTP'.")

        # Extract MBTI components
        mbti_e_i, mbti_n_s, mbti_t_f, mbti_p_j = base_mbti[0], base_mbti[1], base_mbti[2], base_mbti[3]

        # Generate continuous OCEAN scores using specific uniform distribution slices
        ocean = {
            "O": random.uniform(*self.trait_ranges.get(mbti_n_s, (0.4, 0.6))),
            "C": random.uniform(*self.trait_ranges.get(mbti_p_j, (0.4, 0.6))),
            "E": random.uniform(*self.trait_ranges.get(mbti_e_i, (0.4, 0.6))),
            "A": random.uniform(*self.trait_ranges.get(mbti_t_f, (0.4, 0.6))),
            "N": random.uniform(*self.trait_ranges.get(f"{suffix}_suffix", (0.4, 0.6)))
        }
        return ocean

    def calculate_occ_intensities(self, ocean: dict, stimulus: dict) -> dict:
        """
        Calculates resulting OCC emotion intensities based on OCEAN personality traits
        and a specific incoming external environmental stimulus.
        """
        # Baseline threshold calculations influenced by personality traits
        thresholds = {
            "Joy": 0.4 * (1.0 - ocean["E"]),  # Extraverts trigger joy much easier (lower threshold)
            "Distress": 0.5 * (1.0 - ocean["N"]),  # Neurotic individuals trigger distress easier
            "Anger": 0.6 * ocean["A"],  # Highly agreeable individuals resist anger (higher threshold)
            "Remorse": 0.5 * (1.0 - ocean["C"])  # Conscientious individuals trigger guilt/remorse easier
        }

        # Raw values computed directly from user impact values
        raw_joy = stimulus.get("desirability", 0.0) if stimulus.get("desirability", 0.0) > 0 else 0.0
        raw_distress = abs(stimulus.get("desirability", 0.0)) if stimulus.get("desirability", 0.0) < 0 else 0.0
        raw_reproach = stimulus.get("blameworthiness", 0.0)
        raw_shame = stimulus.get("self_blameworthiness", 0.0)

        # Apply specific personality multipliers over basic OCC logic formulas
        occ_outputs = {}

        # 1. OCC Joy (Event-based)
        joy_intensity = (raw_joy * (1.0 + ocean["E"])) - thresholds["Joy"]
        occ_outputs["Joy"] = max(0.0, min(1.0, joy_intensity))

        # 2. OCC Distress (Event-based)
        distress_intensity = (raw_distress * (1.0 + ocean["N"])) - thresholds["Distress"]
        occ_outputs["Distress"] = max(0.0, min(1.0, distress_intensity))

        # 3. OCC Anger (Compound: Reproach + Distress)
        if raw_reproach > 0 and raw_distress > 0:
            # Lower agreeableness (1-A) and higher neuroticism amplify anger intensity
            anger_intensity = ((raw_reproach + raw_distress) / 2) * (1.5 - ocean["A"]) * (1.0 + ocean["N"]) - \
                              thresholds["Anger"]
            occ_outputs["Anger"] = max(0.0, min(1.0, anger_intensity))
        else:
            occ_outputs["Anger"] = 0.0

        # 4. OCC Remorse (Compound: Shame + Distress)
        if raw_shame > 0 and raw_distress > 0:
            # High conscientiousness and high neuroticism scale remorse way up
            remorse_intensity = ((raw_shame + raw_distress) / 2) * (1.0 + ocean["C"]) * (1.0 + ocean["N"]) - thresholds[
                "Remorse"]
            occ_outputs["Remorse"] = max(0.0, min(1.0, remorse_intensity))
        else:
            occ_outputs["Remorse"] = 0.0

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
