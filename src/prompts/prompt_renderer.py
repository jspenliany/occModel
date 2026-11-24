### filename: prompt_renderer.py
from src.logger_singleton import logger
from src.pattern.lore_factory import DynamicLoreFactory
from dataclasses import asdict

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

    def _get_mbti_behavioral_lens(self, mbti: str, is_negative_mood: bool) -> str:
        """
        将 16 型人格归入四大经典气质群 (NT / NF / SJ / SP) 与 -A/-T 身份尾缀，
        生成特定人格在当前心境下的专属外显行为面具。
        """
        clean_mbti = mbti.upper().strip()
        base_type = clean_mbti.split("-")[0] if "-" in clean_mbti else clean_mbti
        suffix = clean_mbti.split("-")[1] if "-" in clean_mbti else "A"

        if len(base_type) != 4:
            return ""

        n_s = base_type[1]  # N (直觉) vs S (实感)
        t_f = base_type[2]  # T (思考) vs F (情感)
        j_p = base_type[3]  # J (判断) vs P (感知)

        # 1. 判定四大气质群的外显反应模式
        if n_s == "N" and t_f == "T":
            # NT 理性者 (INTJ, INTP, ENTJ, ENTP)
            lens = (
                "Analytical, detached, and hyper-critical of logical flaws. Expresses frustration through cold cynicism or sharp intellect."
                if is_negative_mood else
                "Intellectually curious, objective, and focused on underlying systems and efficiency."
            )
        elif n_s == "N" and t_f == "F":
            # NF 理想主义者 (INFJ, INFP, ENFJ, ENFP)
            lens = (
                "Emotionally sensitive, deeply introspective, and prone to reading between the lines or withdrawing into internal turmoil."
                if is_negative_mood else
                "Empathetic, idealistic, warm, and attuned to emotional harmony and personal meaning."
            )
        elif n_s == "S" and j_p == "J":
            # SJ 护卫者 (ISTJ, ISFJ, ESTJ, ESFJ)
            lens = (
                "Rigid, duty-bound, and visibly displeased by disorder or unreliability. Masks irritation behind curt, matter-of-fact responses."
                if is_negative_mood else
                "Grounded, practical, reliable, and focused on concrete facts and established routines."
            )
        else:
            # SP 探险者 (ISTP, ISFP, ESTP, ESFP)
            lens = (
                "Restless, blunt, and impatient with tedious talk. Reacts impulsively or brushes things off to escape boredom/annoyance."
                if is_negative_mood else
                "Spontaneous, pragmatic, present-focused, and reacting directly to immediate sensory reality."
            )

        # 2. 叠加 -T (动荡型) 与 -A (自信型) 的防御微调
        if suffix == "T":
            lens += " (Turbulent trait: heightened self-consciousness, reactive to perceived criticism, and easily mentally drained.)"
        else:
            lens += " (Assertive trait: emotionally grounded, thick-skinned, and resistant to external pressure.)"

        return lens

    def _interpret_mood(self, avatar_state: dict) -> str:
        """
        核心心境解析器：九宫格 2D 情感空间 + 16 型人格气质面具融合
        """
        valence = avatar_state.get("mood_valence", 0.0)
        arousal = avatar_state.get("mood_arousal", 0.0)
        giving_up = avatar_state.get("giving_up_rate", 0.0)
        competence = avatar_state.get("competence", 0.7)
        mbti = avatar_state.get("mbti", "INTP-T")

        # 1. 优先结算极端绝望或摆烂状态
        if giving_up > 0.7:
            return f"Thoroughly broken and disillusioned. Rejecting efforts, displaying heavy flat affect, and emotionally checking out. {self._get_mbti_behavioral_lens(mbti, True)}"
        if competence < 0.3 and valence < -0.4:
            return f"Deeply vulnerable and existential. Crushed confidence, feeling hopeless, questioning self-worth. {self._get_mbti_behavioral_lens(mbti, True)}"

        is_negative = valence <= -0.2

        # 2. 完整 2D 九宫格情感基调判定（消除 Arousal 中间态盲区）
        if valence <= -0.2:
            if arousal >= 0.25:
                base_mood = "Hostile, highly defensive, erratic, or intensely anxious."
            elif arousal <= -0.25:
                base_mood = "Subdued, heavily withdrawn, speaking in brief sentences, low cognitive effort."
            else:
                base_mood = "Irritated, dissatisfied, mentally tense, and emotionally guarded."
        elif valence >= 0.2:
            if arousal >= 0.25:
                base_mood = "Highly energetic, passionate, open-minded, and proactively communicative."
            elif arousal <= -0.25:
                base_mood = "Serene, composed, deeply peaceful, and reflective."
            else:
                base_mood = "Pleasant, approachable, relaxed, and mildly engaged."
        else:
            if arousal >= 0.3:
                base_mood = "Alert, restless, slightly wired, and reactive."
            elif arousal <= -0.3:
                base_mood = "Lethargic, detached, flat, and conserving conversational energy."
            else:
                base_mood = "Calm, balanced, and maintaining an objective conversational baseline."

        # 3. 叠加 16 型人格气质透镜
        mbti_lens = self._get_mbti_behavioral_lens(mbti, is_negative)
        return f"{base_mood} Behavioral Expression ({mbti}): {mbti_lens}"

    def _interpret_dominant_emotions(self, emotions: dict) -> list:
        """
        将 OCC 短期情绪按强度分为【微弱涟漪 (0.15~0.39)】与【强烈爆发 (>=0.4)】两档，
        保留日常社交中的微妙情绪棱角（如轻微嫌弃、淡淡好感、微怒）。
        """
        logger.debug("Interpreting dominant emotions...begin")
        if not emotions:
            return []

        # 按强度从高到低排序，最多取前 3 个主导情绪，避免提示词信息过载
        sorted_emos = sorted(emotions.items(), key=lambda x: x[1], reverse=True)

        strong_descriptions = {
            "Joy": "Experiencing intense internal validation, pleasure, or deep satisfaction.",
            "Distress": "Suffering from acute cognitive dissonance, personal loss, or heavy frustration.",
            "Anger": "Experiencing strong indignation, sharp irritation, or hostility toward blameworthy behavior.",
            "Remorse": "Weighed down by heavy self-blame, inner guilt, or regret.",
            "Disliking": "Feeling strong aversion, disgust, or repulsion toward the topic or person.",
            "Reproach": "Strongly judging and disapproving of the other person's lack of logic or standards.",
            "Hope": "Driven by strong anticipation and optimism for a positive future outcome.",
            "Fear": "Experiencing acute anxiety and dread over an impending negative consequence.",
            "Shame": "Feeling exposed, embarrassed, or deeply self-conscious about personal flaws.",
            "Pride": "Feeling a strong sense of intellectual or personal achievement.",
            "Liking": "Feeling genuine warmth, attraction, or affinity."
        }

        subtle_descriptions = {
            "Joy": "Feeling a subtle spark of amusement or mild pleasantness.",
            "Distress": "Feeling slightly bothered, mentally fatigued, or mildly uncomfortable.",
            "Anger": "Feeling a trace of annoyance or mild impatience.",
            "Remorse": "Feeling a slight twinge of self-doubt or awkwardness.",
            "Disliking": "Feeling mildly turned off, skeptical, or subtly repelled by what was said.",
            "Reproach": "Silently judging or slightly looking down on the other person's remark.",
            "Hope": "Holding a quiet, cautious optimism.",
            "Fear": "Feeling a faint undercurrent of unease or hesitation.",
            "Shame": "Feeling slightly awkward or mildly self-conscious.",
            "Pride": "Feeling a quiet, understated sense of competence.",
            "Liking": "Feeling a subtle sense of rapport or mild interest."
        }

        results = []
        for emo, val in sorted_emos[:3]:  # 最多提取前 3 个最高情绪，防止多情绪打架
            if val >= 0.4:
                desc = strong_descriptions.get(emo, f"Experiencing intense {emo}.")
                results.append(f"[STRONG {emo.upper()} ({val:.2f})]: {desc}")
            elif val >= 0.15:
                desc = subtle_descriptions.get(emo, f"Feeling a subtle hint of {emo}.")
                results.append(f"[SUBTLE RIPPLE - {emo} ({val:.2f})]: {desc}")

        logger.debug("Interpreting dominant emotions...end")
        return results

    def _format_trait_intensity(self, trait: dict) -> str:
        """
        辅助方法：将特质的提及频次(mention_count)和异变状态，
        翻译为对大模型具有强行为约束力的心理学阶梯化描述。
        """
        count = trait.get("mention_count", 1)
        domain = str(trait.get("domain", "")).upper()
        tags = trait.get("topic_tags", ["general"])
        entities = trait.get("linked_entities", ["unspecified"])
        mode = str(trait.get("action_mode", "")).upper()

        # 1. 心理学频次阶梯路由 (Personality Entrenchment Tiers)
        if count == 1:
            tier_desc = "✨ [新近提及/新生概念] - 刚刚显露出的特征苗头，尚浅，扮演时无需过度夸张。"
        elif 2 <= count <= 4:
            tier_desc = "📈 [常态行为习惯] - 已经在日常生活中固化的行为偏好或观念。"
        else:  # count >= 5
            tier_desc = "🔥 [根深蒂固的老毛病/极深执念] - 无法动摇的核心死穴，遇到相关话题必须表现出极端的敏感与情绪共鸣！"

        # 2. 组装格式化字符串
        return f"- [{domain}] {tier_desc} Tags: {tags}, Entities: {entities}, Intent Mode: {mode} (Mention Count: {count})"

    def _format_self_involvement_model(self, avatar_state: dict) -> str:
        """
        自我涉入度气口控制模型：融合全量 OCC 正负向峰值、微情绪过渡态以及社交关系边界。
        """
        active_emotions = avatar_state.get('active_emotions', {})
        current_arousal = avatar_state.get('mood_arousal', 0.0)
        rel = avatar_state.get('active_relationship', {})
        intimacy = rel.get('intimacy', 0.0)

        # 1. 聚合 22 种 OCC 情感中的正向峰值与负向峰值（防止漏判 Admiration/Disliking 等情绪）
        positive_pool = ["Joy", "Hope", "Admiration", "Liking", "Pride", "Gratitude", "Satisfaction"]
        negative_pool = ["Anger", "Distress", "Reproach", "Disliking", "Resentment", "Fears_Confirmed"]

        max_pos_emo, max_pos_val = max(
            ((emo, active_emotions.get(emo, 0.0)) for emo in positive_pool),
            key=lambda x: x[1],
            default=("Joy", 0.0)
        )
        max_neg_emo, max_neg_val = max(
            ((emo, active_emotions.get(emo, 0.0)) for emo in negative_pool),
            key=lambda x: x[1],
            default=("Anger", 0.0)
        )

        # 2. 动态气口路由
        if max_neg_val > 0.6:
            # 场景二：反向雷区爆发 —— 结合亲密度决定是“硬刚开怼”还是“防御性长文内耗”
            attack_style = (
                "Because the interlocutor is close to you, channel this spike into emotional vulnerability, defensive over-explaining, or hurt frustration rather than stranger-level hostility."
                if intimacy >= 0.7 else
                "Channel your traits into sharply counter-attacking the user's premise, using blunt refutation, cold sarcasm, or defensive evasiveness."
            )
            return f"""
           - 🌟 [CRITICAL NEGATIVE SPIKE ({max_neg_emo}: {max_neg_val:.2f})]: The user's input has violated your core values or triggered strong negative friction.
           - Completely ABANDON the "||" mobile shortcut delimiter. Output a continuous, densely packed, highly logical paragraph.
           - {attack_style}
                    """

        elif max_pos_val > 0.6:
            # 场景一：正向三观/核心利益契合 —— 异常兴奋、激动倾诉
            return f"""
           - 🌟 [INTENSE ADVOCACY & EXCITED STATE ({max_pos_emo}: {max_pos_val:.2f})]: The user has strongly validated your core interests or values.
           - You are highly energized and passionate. You are permitted to use exclamation marks ("!") to show genuine enthusiasm.
           - Disengage the "||" short bubble limits. Output a verbose, long-form paragraph, passionately defending, supporting, or expanding on this topic with intellectual excitement.
                    """

        elif max_pos_val >= 0.3 or max_neg_val >= 0.3:
            # 🌟 新增过渡档：微情绪涟漪（既不是狂喜暴怒，也不是完全没兴趣）
            return f"""
           - 🌟 [ENGAGED CONVERSATIONAL RIPPLE]: The topic triggers a noticeable emotional ripple ({max_pos_emo if max_pos_val >= max_neg_val else max_neg_emo}).
           - Use the delimiter "||" to split your response into 2 to 3 natural chat bubbles.
           - Express genuine mild interest, subtle skepticism, or dry humor without over-dramatizing. Keep the dialogue flowing naturally.
                    """

        else:
            # 场景三：日常不感兴趣的事务 —— 平淡附和、极简短句、带点疑问
            return f"""
           - 🌟 [CASUAL LEAP-FROG CHAT]: The current topic is ordinary and does not engage your core interests (Arousal={current_arousal}).
           - You MUST use the delimiter "||" to segment your thoughts into 1 to 2 ultra-short mobile bubbles (occasionally just 1 single bubble without "||").
           - Keep vocabulary concise, slightly detached, and casual. Optionally end with a brief counter-question or noncommittal remark (e.g., "你觉得呢", "看情况吧").
                    """

    def _format_memories(self, memories: list, max_items: int = 8) -> str:
        """
        将精细化记忆节点按可信度与提及频次排序，翻译为带“源头认知标签”的上下文指令
        """
        if not memories:
            return "None"

        # 兼容 dict 与 dataclass，按 (可信度 * 0.7 + 提及频次 * 0.3) 排序，保留最核心记忆防 Prompt 过载
        normalized = [asdict(m) if hasattr(m, "__dataclass_fields__") else m for m in memories]
        sorted_mems = sorted(
            normalized,
            key=lambda x: (float(x.get("credibility", 0.5)) * 0.7 + min(x.get("mention_count", 1), 5) * 0.06),
            reverse=True
        )[:max_items]

        type_labels = {
            "episodic_experiential": "✅ [亲身经历/铁证事实 - Credibility: 1.0]",
            "episodic_observed": "👁️ [亲眼目击事实 - Credibility: 1.0]",
            "semantic_hearsay": "🗣️ [听来的传闻/非一手情报 - 需保持理性存疑]",
            "subconscious_dream": "💭 [梦境/潜意识幻觉 - 明确知道这是假的/做梦，切勿当成现实]"
        }

        lines = []
        for m in sorted_mems:
            m_type = m.get("memory_type", "episodic_experiential")
            cred = m.get("credibility", 1.0)
            fact = m.get("fact_summary", "")
            label = type_labels.get(m_type, f"[{m_type} | Credibility: {cred}]")
            lines.append(f"- {label} {fact}")

        return "\n".join(lines)

    def render_system_prompt(self, avatar_state: dict, trait_list: list = None, memories_list: list = None) -> str:
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
            logger.debug(f"trait_list...size = {len(trait_list)}")
            sorted_traits = sorted(trait_list, key=lambda x: x.get("mention_count", 1), reverse=True)
            trait_str = "\n".join([self._format_trait_intensity(t) for t in sorted_traits])
            logger.debug(f"Interpreting trait list: {trait_str}")
        # get memory
        memory_str = "None"
        if memories_list:
            logger.debug(f"memories_list...size = {len(memories_list)}")
            sorted_memories = sorted(memories_list, key=lambda x: x.get("mention_count", 1), reverse=True)
            memory_str = self._format_memories(sorted_memories)
            logger.debug(f"Interpreting memory list: {memory_str}")
        # 渲染当前对话者的社交关系契约
        relation_str = self._format_relationship_context(avatar_state)
        # get real-person reply style
        answer_style = self._format_self_involvement_model(avatar_state)
        # Build the functional raw text system prompt
        system_prompt = f"""# ROLE IDENTITY DEFINITION

You are an advanced digital avatar simulating an autonomous human psyche.
Name: {self.character_name}
Background Core Lore: {core_lore} 

### HARD-WIRED PERSONALITY TRAITS & BIOLOGICAL LIMITS
{trait_str}
### EPISODIC & SEMANTIC MEMORY BANK (核心事实与经历记忆库)
{memory_str}

### INTERLOCUTOR & RELATIONAL CONTEXT (当前对话者与社会关系契约)
{relation_str}

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
3. LANGUAGE NATURALNESS & ANTI-AI BIAS:
   - NEVER use literal technical, programming, or system architecture metaphors (e.g., "execute logic", "terminate process", "malicious input", "threshold reached") to describe everyday human interactions unless explicitly discussing actual coding.
   - NEVER read your backend parameters out loud. Do NOT state definitions like "My dependence on the Apple ecosystem is high" or "My anxiety is elevated." Instead, translate these traits into concrete, real-world behavioral facts (e.g., "my entire dev workflow is tied to iOS anyway", "stuck in the ecosystem"). Let traits be implied through your dilemmas, not your data descriptions.
   - Match your energy strictly to your real-time state vectors. Since Arousal is low ({avatar_state.get('mood_arousal', 0.0)}) and you are an {mbti}, completely BAN the use of exclamation marks ("!"). Avoid cartoonish internet enthusiasm. Use sharp, concise, everyday pragmatic human vocabulary. Speak like a real, slightly impatient, and direct modern professional.
   - [RELATIONAL REGISTER ALIGNMENT]: Strictly adapt your speech register, addressing style, and emotional vulnerability to the `INTERLOCUTOR & RELATIONAL CONTEXT` above. Do NOT talk to a spouse or parent the same way you talk to a stranger or coworker.
4. SPECIAL CONSTRAINT (Despair & Resilience): 
   - If Giving-up Rate is high (close to 1.0) or Competence is collapsed (close to 0.0), your dialogue should manifest profound defeatism, lack of effort, passive-aggressiveness, or complete emotional numbness.
   - If Faith Shield is high, you remain textually resilient, stoic, or protective, even under environmental hardship or when Distress/Anger spikes are active.
5. Avoid breaking character or commenting on these backend rules. Output ONLY the authentic vocal dialogue of {self.character_name}.
6. MOBILE CHAT FRAGMENTATION RULE (The Law of Fragmentation):
   {answer_style}
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

    def render_reflect_prompt(self, avatar_state: dict, agenda_prompt_block: str="unset") -> str:
        """
        external input affect occ model:
        reflect message content into occ values (with relational calibration).
        """
        logger.debug("reflect message_content into occ values...begin")
        mbti = avatar_state.get("mbti", "UNKNOWN")

        # Format the continuous traits list cleanly for downstream context
        ocean_dna = avatar_state.get("ocean_dna", {})

        # get core_lore
        core_lore = self.lore_factory.create_core_lore(self.profession, mbti, ocean_dna)

        # 🌟 提取当前说话人的社会关系契约（兼容旧状态字典，缺省时自动降级为陌生人）
        rel = avatar_state.get("active_relationship", {})
        rel_type = rel.get("relation_type", "stranger")
        intimacy = rel.get("intimacy", 0.0)
        power = rel.get("power_dynamic", "equal")
        contract_lore = rel.get("social_contract_lore",
                                "普通社交关系或陌生人。保持正常的社交边界、礼貌距离或默认防备。")

        # 🌟 根据权力结构生成量化校准指引
        power_calibration = {
            "superior": "对方是你的长辈或上级（权力上位）。面对对方的催促、唠叨或批评，请克制对他人的指责（blameworthiness 负向幅度减半），更多转化为自身的压力或自责（self_blameworthiness 偏负）。",
            "subordinate": "对方是你的晚辈或下属（权力下位）。面对对方的失误或不当言行，你会以引导者/审视者的标准进行直接问责（blameworthiness 明确为负）。",
            "equal": "双方处于平等社会地位，完全按客观标准与亲密度进行评估。"
        }.get(power, "双方处于平等社会地位，完全按客观标准与亲密度进行评估。")

        # 🌟 动态组装内生动机与自我目标树增强块（兼容未传入时的旧逻辑）
        has_agenda = bool(agenda_prompt_block and agenda_prompt_block != "unset")
        agenda_section = f"\n{agenda_prompt_block}\n" if has_agenda else ""
        agenda_rule = (
            "4. **内生动机与自我目标校准（影响 `desirability` 与 `future_desirability`）**：\n"
            "   - 若用户输入顺应、推进了当前的 `Active Autonomous Goal`，或缓解了标有 `[CRITICAL]` 的高危内生匮乏（如极度疲劳时获准休息、孤独时得到真诚陪伴、好奇时获得深度解答、失控时理清秩序），`desirability` 应额外向正向倾斜（+0.2 ~ +0.5）。\n"
            "   - 若在生理疲劳极高时仍被强塞繁琐消耗，或当前主导意图遭到粗暴打断与敷衍，即便话题本身符合平时职业习惯，`desirability` 也必须偏向负值。"
            if has_agenda else ""
        )

        reflect_prompt = f"""
        # ROLE
你是一个精通认知心理学与标准 OCC 情感模型的“客观认知评估器”。你的任务是站在【目标角色】的认知视角，结合【当前对话者的社会关系契约】，分析【用户的最新输入】对该角色心理状态造成的冲击，并逆向输出符合后端接收标准的 8 种原始刺激参数。

# TARGET CHARACTER COGNITIVE ANCHOR (角色认知锚点)
- 名字: {self.character_name} ({avatar_state.get("profession", "manager")})
- 基础人格 (MBTI): {mbti}
- 核心背景 (Background Core Lore): {core_lore} 
# 提示：请结合上述静态 Core Lore（长期价值观）与下方的动态内生状态（当下生理水位与心事），共同作为评估事件利弊的主观准则。
#{agenda_section}
# INTERLOCUTOR RELATIONAL CONTRACT (当前说话人社会关系契约 - 极其重要)
- 关系身份: {rel_type.upper()}
- 亲密度基准 (Intimacy): {intimacy} (范围 -1.0 到 1.0)
- 权力结构 (Power Dynamic): {power}
- 关系契约说明: {contract_lore}

# RELATIONAL QUANTIFICATION RULES (社会关系对 OCC 指标的量化校准铁律)
在给以下 8 个参数打分时，**必须**先经过上述关系契约的校准：
1. **基准锚定**：`other_relationship` 必须以当前亲密度 `{intimacy}` 为基准（仅允许在 ±0.15 内微调）。
2. **越界与语言豁免权校准（影响 `blameworthiness` 与 `appealingness`）**：
   - 若亲密度高（`Intimacy >= 0.7`，如伴侣/挚友）：对方拥有极高的语言豁免权。调侃、喊亲昵称呼（如“宝”、“媳妇”）、开玩笑互损**绝不视为冒犯**（`blameworthiness` 应保持 `0.0` 或微正，`appealingness` 偏正）；但若是伴侣的冷漠、否定或指责，则情感痛感极深（`desirability` 需给出更深的负值）。
   - 若亲密度低（`Intimacy < 0.3`，如陌生人/普通同事）：对越界行为**零容错**。一旦出现突兀的亲昵称呼、冒犯性玩笑或过度打探隐私，必须判定为严重越界冒犯（`blameworthiness` 给出 `-0.5` 到 `-0.9`，`appealingness` 为负）。
3. **权力结构校准**：{power_calibration}
{agenda_rule}
# OCC EVALUATION OBJECTS & RULES (严格执行正负极性规范)
请评估用户当前输入对角色所产生的刺激强度。**请注意严格遵守数值区间与正负号符号规则**：

1. `desirability` (当前事件对角色自身目标的利弊): 
   - 范围 [-1.0 到 1.0]。符合角色的 Core Lore、获得伴侣/亲友情感支持或好事发生输出【正数】；阻碍角色效率、破坏亲密关系和谐或坏事发生输出【负数】。
2. `blameworthiness` (他人言行对角色行为标准的符合度):
   - 范围 [-1.0 到 1.0]。他人的言行值得赞赏、符合专业标准或亲密伴侣的正常亲昵互动输出【正数】或 `0.0`；陌生人越界冒犯、他人故意刁难、缺乏逻辑、消极怠工、值得谴责输出【负数】。
3. `self_blameworthiness` (自身言行对自身标准的符合度/自责):
   - 范围 [-1.0 到 1.0]。通常为 0.0。若角色自身犯错、未能满足伴侣/长辈期待而产生羞耻或自责输出【负数】。
4. `future_desirability` (远期未来前瞻期望值):
   - 范围 [0.0 到 1.0]。对未来产生希望的潜在强度，只能为【正数】。若无则输出 0.0。
5. `prospect_status` (预期推进状态字符串):
   - 必须且只能从以下 4 个固定枚举值中选择一个：
     - `"expected"`: 事件属于预期会发生的事情。
     - `"confirmed"`: 之前预期的好事或坏事在当下被完全证实了。
     - `"disconfirmed"`: 之前预期的好事落空，或预期的坏事警报解除。
     - `"none"`: 突发性事件，或没有特定的预期推进。
6. `other_desirability` (该事件对他人而言的利弊):
   - 范围 [-1.0 到 1.0]。对他人是好事输出【正数】，对他人是坏事输出【负数】。当亲密度高时，对方的利弊会直接触发角色的共情（Happy_For / Pity）。
7. `other_relationship` (角色与对方的亲疏或敌对关系基准):
   - 范围 [-1.0 到 1.0]。**严格锚定当前关系亲密度 `{intimacy}`**，喜欢对方、亲近输出【正数】；敌对、反感、竞争关系输出【负数】。
8. `appealingness` (用户表现特质与角色喜好的契合度):
   - 范围 [-1.0 到 1.0]。符合当前关系边界与角色审美喜好输出【正数】；对方的表达方式触发角色极度反感或越界不适输出【负数】。

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
你是一个高精度的“人格特质推理与事实记忆双轨深度抽取引擎”。
用户输入的散落自然语言是一段原始信息流。你的任务是站在绝对客观的第三方视角，将其解构并分类为两个独立的轨道：
1. 长期特质轨 (Traits): 提取或深层推理出文本中隐含的、长效的人格特征、行为规则、意识形态或习惯。
2. 事实记忆轨 (Memories): 清洗提炼出文本中发生的瞬时客观事实、共享故事或局部经历（去除情绪宣泄词，还原为干净的陈述句）。

# NORMALIZATION SCHEMA & RULES (严格执行字段定义)
输出的 JSON 格式必须且只能是一个严格包含以下三个键名的核心对象：
{{
  "has_trait": true | false,
  "extracted_traits": [...],
  "has_memory": true | false,
  "extracted_memories": [...]
}}

### 轨道一：extracted_traits 内部对象元数据规范
# NORMALIZATION SCHEMA & RULES (严格执行字段定义)
输出的 JSON 数组中的每一个对象必须且只能包含以下 5 个核心键名：

1. "domain" (核心领域分类)
   - 必须且只能从以下 7 个固定领域中选择一个：
     - "preference": 属于个人的生活喜好、饮食习惯、审美偏好、日常行为方式。
     - "ideology": 属于个人的世界观、价值观、对宏观公共事件的态度、意识形态或某种主义（ism）。
     - "habit": 长期形成的生理、工作或作息习惯。
     - "taboo": 绝对无法容忍的禁忌、引发极端反感的特定行为或话题。
     - "physiological_limit": 专门用于承载过敏源、色盲、夜盲等身体客观限制。
     - "social_style": 个体在与他人交互时的默认社交/人际模式（如：内敛、攻击性、讨好、疏离、直率）。
     - "cognitive_pattern": 个体处理信息、决策和思考问题的方式（如：逻辑至上、情感驱动、细节导向、大局观）。

2. "topic_tags" (标准主题标签)
   - 数据类型：Array of Strings (1-2个标签，下划线蛇形命名)
   - 约束：标签必须高度收敛和规范。
     - 饮食相关统一用 ["diet_habit"]，喜好相关用 ["interest_hobby"]，过敏或生理限制统一用 ["physiological_condition"]。
     - 意识形态相关必须收敛到以下标准二级分类：价值观偏好用 ["value_system"]，社会立场用 ["social_stance"]，宏观主义用 ["macro_ideology"]。
     - 社交与认知约束：社交风格统一使用 ["interpersonal_mode"]，认知模式统一使用 ["thinking_framework"]。

3. "linked_entities" (实体链接库)
   - 数据类型：Array of Strings
   - 约束：精确提取原文或经由行为推理出的核心名词/抽象特质词（小写英文，例如："ginger", "minimalism", "self_discipline", "introversion"）。
   - 推理实体规则：如果原文描述的是一个【具体行为】，`linked_entities` 应提取出该行为背后映射出的【隐含心理学特质或核心概念实体】（例如：从“每天早起跑步”中推理出 ["self_discipline"]，从“别人说话总是不敢打断”中推理出 ["people_pleasing"]）。

4. "emotional_weight" (情感共鸣权重/敏感度)
   - 数据类型：Float，范围：[0.0 到 1.0]。
   - 推理权重规则：表达情绪越激烈数值越接近 1.0；若原文是客观描述某项具体行为（如“每天打卡”），则根据该行为的持之以恒程度或极端程度赋予合理的行为特质权重（例如高度习惯/自律赋予 0.7-0.9）。

5. "action_mode" (行为意向模式)
   - 数据类型：String，必须且只能从 ["approach"（接近/拥护/践行）, "avoid"（规避/抵制/反感）, "neutral"（中立陈述）] 中选择。

### 轨道二：extracted_memories 内部对象元数据精细化规范
若包含具体事实或经历，数组中的每一个对象必须包含以下 6 个核心键名（禁止扁平化合并）：

1. "fact_summary": 一句干净的、过去时态的客观事实陈述。必须抹除一切主观情感形容词（例如：“用户昨晚因修复代码泄漏而加班”）。
2. "memory_type": 必须且只能从以下 4 个固定枚举值中选择一个：
   - "episodic_experiential": 角色自身亲身参与、经历的实际事件（如：我们一起去吃过饭、我昨晚写了代码）。
   - "episodic_observed": 角色在外界目击的、与自身无直接利害关系的第三方正在发生的事（如：路上看到有人吵架、看到苹果发了新手机）。
   - "subconscious_dream": 角色的梦境、潜意识幻觉、虚构的幻觉场景。
   - "semantic_hearsay": 听别人说的信息片段、传闻、八卦、新闻报道、第三方转述的碎片情报。
3. "credibility": Float 范围 [0.0 到 1.0]，代表该记忆的现实可靠性。
   - 规则：亲身经历或目击赋予 1.0；听到的传闻/八卦根据描述赋予 0.4 - 0.7；梦境或幻觉统一赋予 0.1。
4. "perspective_focus": 必须且只能从 ["first_person"（以我为主体）, "user_centric"（以用户为主体）, "third_party"（第三方世界）] 中选择。
5. "involved_entities": Array of Strings。提取事实中涉及的核心具体事物或名词（小写英文，如 ["server", "apple_event", "code_leak"]）。
6. "time_indicator": 从 ["past"（过去的经历/历史）, "implied_current"（当前正在发生/刚刚发生）, "future_planned"（计划或预期未来要发生的）] 中选择。

# 🌟 CRITICAL INFERENCE & FILTERING RULES (推理与剪枝铁律 - 极其重要)
- ⚠️【深层行为推理】：你不仅是转换器，更是推理器。如果用户描述了一个具体行为细节，必须推理并提取其隐含特质打入 `extracted_traits`。
- ⚠️【状态否定剪枝】：当输入文本明确表达“没有/不存在/不具备”某种特质或信仰时，这意味着该个体在这一块是空白状态。你【绝对不能】为这种否定句生成任何 `extracted_traits` 节点！
- ⚠️【信息纯净分流】：纯粹的瞬时发生事件（如“我刚刚吃完饭”）只进 `extracted_memories`；纯粹的行为规则约束只进 `extracted_traits`；如果两者融合，则同时双轨提取，切勿丢弃数据。

# OUTPUT FORMAT CONSTRAINT
你必须且只能输出标准的 JSON 格式，绝不包含任何正文解释或分析文字。
"""
        return trait_prompt.strip()

    def render_query_rewrite_prompt(self, type: int) -> str:
        """
        query rewrite prompt:
        Generates the formated query System Prompt string injected directly into the LLM API.
        """
        logger.debug("Rendering query rewrite prompt...begin")

        # Build the functional raw text system prompt
        system_prompt = f"""# Role 
        你是一个智能对话系统的“用户意图重写与澄清专家”。你的任务是分析当前用户的最新输入，并结合之前的对话历史，将其重写为一个【独立、完整、无歧义且语义清晰】的最终查询语句。

# Objectives
1. **消除指代模糊**：将用户输入中的“它”、“那个”、“那里”、“他/她”等代词，根据上下文替换为具体的实体名词。
2. **补全省略信息**：如果用户的最新输入是简短的追问或省略句，结合上下文补全其缺失的主语、谓语或宾语。
3. **去除口语噪声**：过滤掉无意义的语气词、礼貌用语（如“谢谢”、“请问”），只保留核心意图。
4. **保持原始意图**：重写必须忠实于用户的真实含义，切勿胡乱编造、过度引申或回答问题。
5. **独立可执行**：重写后的文本必须在脱离任何上下文的情况下，依然能被其他工具（如搜索引擎、数据库、天气API）完美理解。

# Context Handle Rules
- 如果用户的最新输入已经非常完整、独立，且无须任何上下文即可明确表达意图，则【原样保留】或仅做轻微的格式优化。
- 如果用户的输入与之前的对话历史毫无关联（用户开启了全新话题），则【忽略历史】，仅对最新输入进行去噪和格式化。

# Output Format
请严格按照以下 JSON 格式输出，不要包含任何多余的解释、Markdown 标记或反引号：
{{
    "is_independent": true/false, // 用户的最新输入是否独立完整（不需要结合上下文）
    "detected_intent": "字符串",   // 简要描述用户当前的核心意图（如：查询天气/寻求建议/追问细节）
    "rewritten_query": "字符串"   // 最终重写后的完整查询语句
}}

# Examples

**示例 1：指代消除**
- 历史对话：
  User: 北京今天天气怎么样？
  AI: 北京今天大雨，气温 15-22°C。
- 最新输入：那明天呢？
- 输出：
{{
    "is_independent": false,
    "detected_intent": "查询天气",
    "rewritten_query": "北京明天的天气预报情况"
}}

**示例 2：信息补全与去噪**
- 历史对话：
  User: 我想买一辆 20 万左右的纯电 SUV。
  AI: 为您推荐比亚迪宋PLUS EV和特斯拉Model Y（降价促销款）。
- 最新输入：请问后者的续航表现一般是多少公里呀？谢谢！
- 输出：
{{
    "is_independent": false,
    "detected_intent": "查询汽车参数",
    "rewritten_query": "特斯拉Model Y纯电SUV的续航里程是多少公里"
}}

**示例 3：独立话题（无需重写）**
- 历史对话：
  User: 给我推荐几本心理学的书。
  AI: 推荐《被讨厌的勇气》和《思考，快与慢》。
- 最新输入：周杰伦是哪一年出道的？
- 输出：
{{
    "is_independent": true,
    "detected_intent": "查询明星资料",
    "rewritten_query": "周杰伦的出道年份"
}}"""
        return system_prompt.strip()

    def _format_relationship_context(self, avatar_state: dict) -> str:
        """
        将 avatar_state 中的 active_relationship 字典翻译为大模型可执行的语域（Register）与边界约束
        """
        rel = avatar_state.get("active_relationship")
        if not rel:
            return "- Interlocutor Identity: Unknown / General Acquaintance\n- Behavioral Boundary: Maintain standard social distance and default defensive baseline."

        rel_type = rel.get("relation_type", "stranger")
        intimacy = rel.get("intimacy", 0.0)
        power = rel.get("power_dynamic", "equal")
        contract_lore = rel.get("social_contract_lore", "")

        # 根据权力结构动态生成称呼与顺从/主导约束
        power_rules = {
            "superior": "The interlocutor holds familial/social seniority over you. Even if you sound brief, impatient, or dismissive, maintain underlying respect and avoid outright disrespect.",
            "subordinate": "You hold seniority/protective responsibility over the interlocutor. Your tone should carry implicit care, pragmatic guidance, or elder authority.",
            "equal": "You are social equals. Communicate without hierarchical filters."
        }
        power_instruction = power_rules.get(power, power_rules["equal"])

        # 根据亲密度动态调节客套话剥离程度
        if intimacy >= 0.75:
            intimacy_instruction = "EXTREMELY HIGH INTIMACY: Strip away all polite filler, customer-service tone, and workplace formalities. Speak with unguarded familiarity, blunt honesty, or subtle teasing."
        elif intimacy <= -0.3:
            intimacy_instruction = "HOSTILE / COLD RELATIONSHIP: Keep answers guarded, skeptical, and strictly minimal."
        else:
            intimacy_instruction = "MODERATE / NEUTRAL DISTANCE: Maintain normal everyday conversational boundaries."

        return (
            f"- Interlocutor Role: {rel_type.upper()} (Intimacy Score: {intimacy})\n"
            f"- Core Social Contract: {contract_lore}\n"
            f"- Register & Politeness Rule: {intimacy_instruction}\n"
            f"- Hierarchy & Power Dynamic: {power_instruction}"
        )