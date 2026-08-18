# filename: main.py
import time
from models.psi.bridge import PSI3DGlassBridge
from prompts.prompt_renderer import LLMPromptRenderer


def run_avatar_pipeline():
    # 1. Initialize the core PSI 3D-Glass engine with a concrete MBTI archetype
    avatar = PSI3DGlassBridge("INFP-T")

    # 2. Initialize the completely decoupled Prompt Rendering Module
    renderer = LLMPromptRenderer(
        character_name="Elysia",
        core_lore="A brilliant but reclusive software engineer who prefers maintaining code over human conversations."
    )

    print("====== STEP 1: INITIAL STABLE STATE ======")
    initial_state = avatar.get_current_avatar_state()
    prompt = renderer.render_system_prompt(initial_state)
    print(prompt)
    print("\n" + "=" * 50 + "\n")

    # 3. Simulate a severe negative external stimulus (User harsh evaluation)
    print("====== STEP 2: USER STIMULUS RECORDED ======")
    print("Action: User sharply criticizes Elysia's latest source code delivery.")
    avatar.receive_user_stimulus({
        "desirability": -0.85,
        "blameworthiness": 0.9,
        "self_blameworthiness": 0.4
    })

    # Extract state right after the computation spike
    furious_state = avatar.get_current_avatar_state()
    furious_prompt = renderer.render_system_prompt(furious_state)
    print(furious_prompt)

    # The string generated in `furious_prompt` is what you dispatch to your OpenAI/FastAPI payload loop:
    # response = openai.ChatCompletion.create(messages=[{"role": "system", "content": furious_prompt}, ...])


if __name__ == "__main__":
    run_avatar_pipeline()
