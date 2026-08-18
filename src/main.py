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

def debug_avatar_pipeline():
    # 初始：创建一个温柔、信任人类、情绪稳定的暖男/暖女类型 (ENFJ-A)
    avatar = PSI3DGlassBridge("ENFJ-A")
    print("=== [初始状态] ===")
    print("初始性格基因：", avatar.get_current_avatar_state()["ocean_dna"])
    # 此时其 A（宜人性）很高（比如 0.82），N（神经质）很低（比如 0.15）

    # 模拟连续遭遇 6 次背叛和严厉的指责（行为与事件的连续重复）
    print("\n=== [开始连续遭遇外部恶劣对待，形成行为与情绪习惯] ===")
    bad_stimulus = {"desirability": -0.5, "blameworthiness": -0.8}

    for i in range(1, 30):
        print(f"\n---> 第 {i} 次被深度伤害...")
        avatar.receive_user_stimulus(bad_stimulus)
        print(f"当前即时 Anger 强度: {avatar.e_layer.active_emotions['Anger']:.2f}")
        print("当前性格基因状态：", avatar.get_current_avatar_state()["ocean_dna"])
        #--
        avatar.update_system_clock()


def run_faith_test():
    # 创建一个充满温情与理想主义的坚韧角色 (ENFJ-A)
    avatar = PSI3DGlassBridge("ENFJ-A")

    # 认知评估：虽然眼前极其痛苦，但未来的愿景非常宏大
    hardship_with_future = {
        "desirability": -0.7,  # 眼前的短期艰辛：极其痛苦
        "future_desirability": 0.9,  # 🌟 宏大的未来：必胜的目标
        "blameworthiness": -0.5,  # 伴随着他人的冷嘲热讽
        "prospect_status": "none"
    }

    print("=== [第 1 阶段：确立必胜信念，奔赴远方] ===")
    avatar.receive_user_stimulus(hardship_with_future)
    # 让时间推移，将短期的‘爆发希望’沉淀为中期的‘坚韧护盾’与‘必胜信心’
    for _ in range(3):
        avatar.update_system_clock()

    state = avatar.get_current_avatar_state()
    print(f"当前短期情绪: Hope={state['active_emotions']['Hope']}, Anger={state['active_emotions']['Anger']}")
    print(
        f"内心的必胜信心(Competence): {avatar.m_layer.competence:.2f}, 信念护盾厚度: {avatar.m_layer.faith_shield:.2f}")

    print("\n=== [第 2 阶段：再次遭遇同样强度的艰辛与打击] ===")
    # 再次输入同样强度的伤害
    avatar.receive_user_stimulus({"desirability": -0.7, "blameworthiness": -0.5, "prospect_status": "none"})

    state_after = avatar.get_current_avatar_state()
    print(f"拥有信念后的即时 Anger 强度: {state_after['active_emotions']['Anger']}")
    print(f"拥有信念后的即时 Distress 强度: {state_after['active_emotions']['Distress']}")


if __name__ == "__main__":
    # run_avatar_pipeline()
    # debug_avatar_pipeline()
    run_faith_test()
