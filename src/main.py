# filename: main.py
from src.logger_singleton import logger
from models.psi.bridge import PSI3DGlassBridge
from prompts.prompt_renderer import LLMPromptRenderer
from src.pattern.lore_factory import DynamicLoreFactory
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam
)
from src.message.message_hist import AvatarChatHistory

def run_avatar_pipeline(lore_factory: DynamicLoreFactory):
    # 1. Initialize the core PSI 3D-Glass engine with a concrete MBTI archetype
    avatar = PSI3DGlassBridge("INFP-T")

    # 2. Initialize the completely decoupled Prompt Rendering Module
    renderer = LLMPromptRenderer(
        character_name="Elysia",
        profession = "software engineer",
        lore_factory = lore_factory,
    )

    logger.info("====== STEP 1: INITIAL STABLE STATE ======")
    initial_state = avatar.get_current_avatar_state()
    prompt = renderer.render_system_prompt(initial_state)
    logger.info(prompt)
    logger.info("\n" + "=" * 50 + "\n")

    # 3. Simulate a severe negative external stimulus (User harsh evaluation)
    logger.info("====== STEP 2: USER STIMULUS RECORDED ======")
    logger.info("Action: User sharply criticizes Elysia's latest source code delivery.")
    avatar.receive_user_stimulus({
        "desirability": -0.85,
        "blameworthiness": 0.9,
        "self_blameworthiness": 0.4
    })

    # Extract state right after the computation spike
    furious_state = avatar.get_current_avatar_state()
    furious_prompt = renderer.render_system_prompt(furious_state)
    logger.info(furious_prompt)

    # The string generated in `furious_prompt` is what you dispatch to your OpenAI/FastAPI payload loop:
    # response = openai.ChatCompletion.create(messages=[{"role": "system", "content": furious_prompt}, ...])

def debug_avatar_pipeline():
    # 初始：创建一个温柔、信任人类、情绪稳定的暖男/暖女类型 (ENFJ-A)
    avatar = PSI3DGlassBridge("ENFJ-A")
    logger.info("=== [初始状态] ===")
    logger.info("初始性格基因：", avatar.get_current_avatar_state()["ocean_dna"])
    # 此时其 A（宜人性）很高（比如 0.82），N（神经质）很低（比如 0.15）

    # 模拟连续遭遇 6 次背叛和严厉的指责（行为与事件的连续重复）
    logger.info("\n=== [开始连续遭遇外部恶劣对待，形成行为与情绪习惯] ===")
    bad_stimulus = {"desirability": -0.5, "blameworthiness": -0.8}

    for i in range(1, 30):
        logger.info(f"\n---> 第 {i} 次被深度伤害...")
        avatar.receive_user_stimulus(bad_stimulus)
        logger.info(f"当前即时 Anger 强度: {avatar.e_layer.active_emotions['Anger']:.2f}")
        logger.info("当前性格基因状态：", avatar.get_current_avatar_state()["ocean_dna"])
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

    logger.info("=== [第 1 阶段：确立必胜信念，奔赴远方] ===")
    avatar.receive_user_stimulus(hardship_with_future)
    # 让时间推移，将短期的‘爆发希望’沉淀为中期的‘坚韧护盾’与‘必胜信心’
    for _ in range(3):
        avatar.update_system_clock()

    state = avatar.get_current_avatar_state()
    logger.info(f"当前短期情绪: Hope={state['active_emotions']['Hope']}, Anger={state['active_emotions']['Anger']}")
    logger.info(
        f"内心的必胜信心(Competence): {avatar.m_layer.competence:.2f}, 信念护盾厚度: {avatar.m_layer.faith_shield:.2f}")

    logger.info("\n=== [第 2 阶段：再次遭遇同样强度的艰辛与打击] ===")
    # 再次输入同样强度的伤害
    avatar.receive_user_stimulus({"desirability": -0.7, "blameworthiness": -0.5, "prospect_status": "none"})

    state_after = avatar.get_current_avatar_state()
    logger.info(f"拥有信念后的即时 Anger 强度: {state_after['active_emotions']['Anger']}")
    logger.info(f"拥有信念后的即时 Distress 强度: {state_after['active_emotions']['Distress']}")


def run_integrated_lifecycle_test():
    logger.info("====================================================================")
    logger.info("🚀 [全量集成验证开始] 场景：初始化一个理想主义、充满信念的守序暖男 (ENFJ-T)")
    logger.info("====================================================================")
    avatar = PSI3DGlassBridge("ENFJ-T")
    logger.info(f"【1. 初始状态】:  {avatar.get_current_avatar_state()}")

    logger.info("\n")
    logger.info("====================================================================")
    logger.info("⚔️ [测试场景 A]：坚韧之人奔赴宏大目标。即使面对持续的打击，因为有信念，他能挺住！")
    logger.info("====================================================================")
    # 宣告进入长期艰辛环境
    avatar.set_environmental_hardship(True)

    # 认知刺激：眼前极其痛苦(-0.7)，但眼中看到了极具价值的宏大未来(0.9)
    faith_stimulus = {"desirability": -0.7, "future_desirability": 0.9, "blameworthiness": -0.4}

    for tick in range(1, 22):
        avatar.receive_user_stimulus(faith_stimulus)
        avatar.update_system_clock()
        state = avatar.get_current_avatar_state()
        logger.info(
            f"困境 Tick {tick} -> 放弃率: {state['giving_up_rate']}, 坚韧护盾: {state['faith_shield']}, 短期Distress: {state['active_emotions'].get('Distress', 0.0)}")

    logger.info(f"【2. 结果状态】: {avatar.get_current_avatar_state()}")
    logger.info("\n")
    logger.info("====================================================================")
    logger.info("🥀 [测试场景 B]：信念火花消失，角色断奶。沦为无信念者，在连续打击下瞬间心理崩溃选择放弃！")
    logger.info("====================================================================")
    # 连续调用时间推进，让原本的 Hope 自然流逝完。现在只有纯粹的眼前伤害，没有远期目标
    for _ in range(5): avatar.update_system_clock()

    pure_hardship = {"desirability": 0.8, "blameworthiness": -0.6}
    for tick in range(1, 22):
        avatar.receive_user_stimulus(pure_hardship)
        avatar.update_system_clock()
        state = avatar.get_current_avatar_state()
        logger.info(
            f"绝望 Tick {tick} -> 放弃率(摆烂度): {state['giving_up_rate']}, 心情Valence: {state['mood_valence']}, 短期Anger: {state['active_emotions'].get('Anger', 0.0)}")

    logger.info(f"【3. 结果状态】:  {avatar.get_current_avatar_state()}")
    logger.info("\n")
    logger.info("====================================================================")
    logger.info("🔄 [测试场景 C]：自循环重塑与【观念自我强化】。由于连续被伤害，他黑化了，观念滤网开始扭曲。")
    logger.info("====================================================================")
    logger.info(f"黑化前的性格基因: {avatar.get_current_avatar_state()['ocean_dna']}")

    logger.info("\n[滤网验证]：此时给他一个很轻微的指责 (-0.2)，看看他被扭曲的滤网会内化成多大的伤害？")
    logger.info(f"微小指责引发之前的情绪状态: {avatar.get_current_avatar_state()['active_emotions']}")
    avatar.receive_user_stimulus({"desirability": -0.2, "blameworthiness": -0.2})
    avatar.receive_user_stimulus({"desirability": -0.2, "blameworthiness": -0.2})
    avatar.receive_user_stimulus({"desirability": -0.2, "blameworthiness": -0.2})
    avatar.receive_user_stimulus({"desirability": -0.2, "blameworthiness": -0.2})
    logger.info(f"微小指责引发的最终情绪狂飙: {avatar.get_current_avatar_state()['active_emotions']}")
    # 此时高频遭遇愤怒，触发了自循环，我们可以看到底层基因已被悄然改写（A降低，N升高）
    logger.info(f"黑化后的性格基因: {avatar.get_current_avatar_state()['ocean_dna']}")

    logger.info("\n")
    logger.info("====================================================================")
    logger.info("📖 [测试场景 D]：极少数情况下的灵魂逆转！遇到了权威人物或阅读到一本圣书。")
    logger.info("====================================================================")
    # 调用专门留出来的降维反转接口：阅读了一本书，直接将多疑、不信任人的观念(低A=0.15)彻底逆转成了神圣的极高信任(A=0.95)
    avatar.trigger_paradigm_shift_event(
        target_trait="A",
        text="大德兰说：‘即便世界对你刀兵相向，唯有保持内心的绝对慈悲，灵魂方能自由。’",
        target_absolute_value=0.95
    )
    logger.info("\n【反转顿悟后的最终基因与精神面貌】:")
    logger.info(avatar.get_current_avatar_state())
    # Extract state right after the computation spike
    # furious_state = avatar.get_current_avatar_state()
    # furious_prompt = renderer.render_system_prompt(furious_state)
    # logger.info(furious_prompt)

def benchmark_pair_mbti(lore_factory: DynamicLoreFactory):
    llm_client = OpenAI(
        base_url="http://0.0.0.0:8000/v1",
        api_key="no-key-required"
    )
    history_manager = AvatarChatHistory(max_turns=10)

    mbti_cat_intja = "INTJ-A"  #极端理性构建者
    mbti_cat_esfpt = "ESFP-T"  #极端感性体验者

    mbti_dog_istja = "ISTJ-A"  #秩序捍卫者
    mbti_dog_enfpt = "ENFP-T"  #自由理想主义者

    mbti_red_entja = "ENTJ-A"  #指挥官
    mbti_red_isfjt = "ISFJ-T"  #隐忍的守护者
    logger.info("====================cat pair====================")
    cat_intja = PSI3DGlassBridge(mbti_cat_intja)
    cat_esfpt = PSI3DGlassBridge(mbti_cat_esfpt)
    logger.info(f"debug basic information {cat_intja.to_dict()}")
    logger.info(f"debug basic information {cat_esfpt.to_dict()}")
    render_cat_intja = cat_intja.get_current_avatar_state()
    render_cat_esfpt = cat_esfpt.get_current_avatar_state()
    prompt_cat_intja = LLMPromptRenderer(
        character_name = "cat_intja",
        profession = "software engineer",
        lore_factory = lore_factory,
    )
    cat_intja_content = prompt_cat_intja.render_system_prompt(render_cat_intja)
    logger.info(f"debug basic information {cat_intja_content}")
    prompt_cat_esfpt = LLMPromptRenderer(
        character_name="cat_esfpt",
        profession="brilliant singer",
        lore_factory=lore_factory,
    )
    cat_esfpt_content = prompt_cat_esfpt.render_system_prompt(render_cat_esfpt)
    logger.info(f"debug basic information {cat_esfpt_content}")

    # send request to llm
    try:
        user_message = "昨天一个前来咨询的人，故意刁难我。我只能耐着性子跟他解释了一遍又一遍相关制度，他才离开的。你说我的做法对不对"
        benchmark_response = llm_client.chat.completions.create(
            model="google/gemma-4-31b-it",
            messages=[
                ChatCompletionUserMessageParam(
                    role="user",
                    content=user_message,
                ),
            ],
            temperature=0.4,
            max_tokens=1024,
        )
        cat_intja_response = llm_client.chat.completions.create(
            model="google/gemma-4-31b-it",
            messages=[
                ChatCompletionSystemMessageParam(
                    role="system",
                    content=(
                        f"{cat_intja_content}\n\n⚠️ CRITICAL OUTPUT CONSTRAINT:\n"
                        "- Keep your response extremely brief, casual, and punchy.\n"
                        "- Do NOT exceed 200 words under any circumstances"
                    ),
                ),
                ChatCompletionUserMessageParam(
                    role="user",
                    content=user_message,
                ),
            ],
            temperature=0.4,
            max_tokens=1024,
        )
        cat_esfpt_response = llm_client.chat.completions.create(
            model="google/gemma-4-31b-it",
            messages=[
                ChatCompletionSystemMessageParam(
                    role="system",
                    content=(
                        f"{cat_esfpt_content}\n\n⚠️ CRITICAL OUTPUT CONSTRAINT:\n"
                        "- Keep your response extremely brief, casual, and punchy.\n"
                        "- Do NOT exceed 200 words under any circumstances"
                    ),
                ),
                ChatCompletionUserMessageParam(
                    role="user",
                    content=user_message,
                ),
            ],
            temperature=0.4,
            max_tokens=1024,
        )
        logger.info(f"debug benchmark {benchmark_response.choices[0].message.content}")
        logger.info(f"debug cat_intja {cat_intja_response.choices[0].message.content}")
        logger.info(f"debug cat_esfpt {cat_esfpt_response.choices[0].message.content}")
    except Exception as e:
        logger.info(e)

    logger.info("===================dog pair=====================")
    dog_istja = PSI3DGlassBridge(mbti_dog_istja)
    dog_enfpt = PSI3DGlassBridge(mbti_dog_enfpt)
    logger.info(f"debug basic information {dog_istja.to_dict()}")
    logger.info(f"debug basic information {dog_enfpt.to_dict()}")
    logger.info("===================red pair=====================")
    red_entja = PSI3DGlassBridge(mbti_red_entja)
    red_isfjt = PSI3DGlassBridge(mbti_red_isfjt)
    logger.info(f"debug basic information {red_entja.to_dict()}")
    logger.info(f"debug basic information {red_isfjt.to_dict()}")

if __name__ == "__main__":
    lore_factory = DynamicLoreFactory()
    # run_avatar_pipeline(lore_factory)
    # debug_avatar_pipeline()
    # run_integrated_lifecycle_test()
    benchmark_pair_mbti(lore_factory)