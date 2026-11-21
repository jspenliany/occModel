import os
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from openai import OpenAI
import uvicorn
from src.pattern.avatar_orchestrator import AvatarOrchestrator
from src.pattern.psi_avatar import PsiAvatar
from src.pattern.lore_factory import DynamicLoreFactory
from src.models.psi.trait import TraitNormalizer
from src.models.psi.engine_config import RelationalProfile
from src.logger_singleton import logger

# ==================== 1. 全局引擎管理器 (单例生命周期) ====================

class EngineContext:
    orchestrator: Optional[AvatarOrchestrator] = None
    lore_factory: Optional[DynamicLoreFactory] = None
    trait_factory: Optional[TraitNormalizer] = None

ctx = EngineContext()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 启动时初始化 PSI-3DGlass 核心引擎，关闭时自动持久化存档"""
    logger.info("Initializing PSI-3DGlass Engine for FastAPI...")
    llm_base_url = os.getenv("LLM_BASE_URL", "http://0.0.0.0:8000/v1")
    llm_api_key = os.getenv("LLM_API_KEY", "no-key-required")
    model_name = os.getenv("LLM_MODEL_NAME", "google/gemma-4-31b-it")

    llm_client = OpenAI(base_url=llm_base_url, api_key=llm_api_key)
    ctx.lore_factory = DynamicLoreFactory()
    ctx.trait_factory = TraitNormalizer(llm_client, model_name)
    ctx.orchestrator = AvatarOrchestrator(llm_client, model_name=model_name)

    # 默认预注册基准测试角色（如本地已有存档则优先冷启动恢复）
    default_avatars = [
        ("cat_intja", "INTJ-A", "pharmacist"),
        ("cat_esfpt", "ESFP-T", "brilliant singer"),
        ("cat_intpt", "INTP-T", "software engineer"),
    ]
    for key, mbti, prof in default_avatars:
        if not ctx.orchestrator.load_avatar_from_storage(key, ctx.lore_factory):
            avatar = PsiAvatar(key, mbti, prof, ctx.lore_factory, ctx.trait_factory)
            ctx.orchestrator.register_avatar(key, avatar)

    logger.info("PSI-3DGlass Engine ready to serve Spring requests.")
    yield
    logger.info("Shutting down PSI-3DGlass Engine, saving all avatars...")
    if ctx.orchestrator:
        ctx.orchestrator.save_all_avatars()

app = FastAPI(
    title="PSI-3DGlass Digital Soul API",
    description="为 Spring 生态提供的计算心理学数字人对话与状态管理微服务",
    version="1.0.0",
    lifespan=lifespan
)


# ==================== 2. 强类型 DTO 契约 (对齐 Spring Jackson 序列化) ====================

class ApiResponse(BaseModel):
    """统一响应包装体，方便 Spring 端使用 Result<T> 泛型反序列化"""
    code: int = Field(default=200, description="状态码: 200 成功, 404 未找到, 500 内部异常")
    message: str = Field(default="success", description="提示信息")
    data: Optional[Any] = Field(default=None, description="业务载荷")

class RegisterAvatarRequest(BaseModel):
    avatar_key: str = Field(..., description="智能体唯一标识，如 cat_intpt")
    character_name: str = Field(..., description="角色显示名称")
    mbti: str = Field(..., description="16型人格编码，如 INTP-T")
    profession: str = Field(..., description="职业设定，如 software engineer")
    load_from_storage: bool = Field(default=True, description="若磁盘存在历史存档是否优先恢复")

class RegisterRelationRequest(BaseModel):
    avatar_key: str = Field(..., description="智能体标识")
    target_user_id: str = Field(..., description="对话者ID（对应 Spring 用户体系 ID）")
    relation_type: str = Field(default="stranger", description="关系类型: spouse / parent / child / colleague / stranger")
    intimacy_baseline: float = Field(default=0.0, ge=-1.0, le=1.0, description="亲密度基准 [-1.0, 1.0]")
    emotional_vulnerability: float = Field(default=1.0, ge=0.1, le=3.0, description="情感易伤乘数")
    power_dynamic: str = Field(default="equal", description="权力结构: equal / superior / subordinate")
    social_contract_lore: str = Field(..., description="关系契约描述")

class ChatTurnRequest(BaseModel):
    avatar_keys: List[str] = Field(..., description="需要参与回复的智能体 key 列表（支持单聊传1个，群聊传多个）")
    user_message: str = Field(..., description="用户最新发送的消息文本")
    context: str = Field(default="", description="上下文历史摘要（可选）")
    speaker_id: str = Field(default="unknown_stranger", description="说话人ID，用于匹配社交关系契约")
    reflect_temperature: float = Field(default=0.3, description="OCC 情感评估采样温度")
    chat_temperature: float = Field(default=0.75, description="最终对话生成采样温度")
    extract_traits_async: bool = Field(default=True, description="是否后台异步提取特质与记忆并自动存档")

class AvatarReplyItem(BaseModel):
    avatar_key: str
    raw_reply: str = Field(..., description="大模型原始输出（含 || 分隔符）")
    bubbles: List[str] = Field(..., description="已按 || 切分好的短气泡列表，方便前端逐条弹窗")
    psychological_state: Dict[str, Any] = Field(..., description="回复后的实时心境与情绪快照")

class ParadigmShiftRequest(BaseModel):
    avatar_key: str
    target_trait: str = Field(..., description="目标 OCEAN 维度: O / C / E / A / N")
    trigger_text: str = Field(..., description="触发顿悟的文本/事件描述")
    target_absolute_value: float = Field(..., ge=0.0, le=1.0, description="反转后的目标绝对值")


# ==================== 3. 后台异步辅助任务 ====================

def _background_extract_and_save(avatar_keys: List[str], user_message: str):
    """不阻塞 Spring HTTP 响应的后台任务：双轨提取特质/记忆 + 持久化落盘"""
    for key in avatar_keys:
        avatar = ctx.orchestrator.avatars.get(key)
        if avatar:
            try:
                avatar.append_new_trait(user_message)
            except Exception as e:
                logger.error(f"[Background] Trait/Memory extraction failed for {key}: {e}")
    ctx.orchestrator.save_all_avatars()


# ==================== 4. RESTful API 路由定义 ====================

@app.post("/api/v1/avatars/register", response_model=ApiResponse, summary="注册或冷启动加载数字人")
async def register_avatar(req: RegisterAvatarRequest):
    if req.load_from_storage and ctx.orchestrator.load_avatar_from_storage(req.avatar_key, ctx.lore_factory):
        state = ctx.orchestrator.avatars[req.avatar_key].engine.get_current_avatar_state()
        return ApiResponse(message="loaded from storage", data={"avatar_key": req.avatar_key, "state": state})

    avatar = PsiAvatar(
        character_name=req.character_name,
        mbti=req.mbti,
        profession=req.profession,
        lore_factory=ctx.lore_factory,
        trait_factory=ctx.trait_factory
    )
    ctx.orchestrator.register_avatar(req.avatar_key, avatar)
    return ApiResponse(
        message="registered new avatar",
        data={"avatar_key": req.avatar_key, "state": avatar.engine.get_current_avatar_state()}
    )


@app.post("/api/v1/avatars/relations", response_model=ApiResponse, summary="绑定或更新社交关系契约")
async def register_relation(req: RegisterRelationRequest):
    avatar = ctx.orchestrator.avatars.get(req.avatar_key)
    if not avatar:
        raise HTTPException(status_code=404, detail=f"Avatar '{req.avatar_key}' not found")

    profile = RelationalProfile(
        target_user_id=req.target_user_id,
        relation_type=req.relation_type,
        intimacy_baseline=req.intimacy_baseline,
        emotional_vulnerability=req.emotional_vulnerability,
        power_dynamic=req.power_dynamic,
        social_contract_lore=req.social_contract_lore
    )
    avatar.register_relationship(profile)
    return ApiResponse(message="relationship registered", data=profile.model_dump())


@app.post("/api/v1/chat/turn", response_model=ApiResponse, summary="核心对话接口（支持单聊与多智能体并发群聊）")
async def chat_turn(req: ChatTurnRequest, background_tasks: BackgroundTasks):
    """
    对应原 benchmark_pair_mbti_optimized 的核心对话流：
    使用 asyncio.to_thread 并发驱动多个智能体完成 [OCC评估 -> 时钟推进 -> 生成气泡回复]
    """
    missing = [k for k in req.avatar_keys if k not in ctx.orchestrator.avatars]
    if missing:
        raise HTTPException(status_code=404, detail=f"Avatars not registered: {missing}")

    def _run_single_avatar_turn(key: str) -> AvatarReplyItem:
        avatar = ctx.orchestrator.avatars[key]
        # 1. 情感反射评估
        reflect_payload = avatar.get_reflect_payload(req.context, req.user_message, speaker_id=req.speaker_id)
        resp = ctx.orchestrator.llm_client.chat.completions.create(
            model=ctx.orchestrator.model_name,
            messages=reflect_payload,
            temperature=req.reflect_temperature
        )
        from src.utils.util_json import extract_and_parse_json
        appraisal_data = extract_and_parse_json(resp.choices.message.content.strip())

        # 2. 状态内化与时钟推进
        avatar.apply_appraisal_and_tick(appraisal_data, speaker_id=req.speaker_id)

        # 3. 生成最终对话回复
        chat_payload = avatar.get_common_chat_payload(req.context, req.user_message, speaker_id=req.speaker_id)
        chat_resp = ctx.orchestrator.llm_client.chat.completions.create(
            model=ctx.orchestrator.model_name,
            messages=chat_payload,
            temperature=req.chat_temperature
        )
        raw_reply = chat_resp.choices.message.content.strip()
        bubbles = [b.strip() for b in raw_reply.split("||") if b.strip()]

        return AvatarReplyItem(
            avatar_key=key,
            raw_reply=raw_reply,
            bubbles=bubbles,
            psychological_state=avatar.engine.get_current_avatar_state(speaker_id=req.speaker_id)
        )

    # 多个智能体并发推理，显著降低群聊场景下的 Spring 等待耗时
    tasks = [asyncio.to_thread(_run_single_avatar_turn, key) for key in req.avatar_keys]
    results: List[AvatarReplyItem] = await asyncio.gather(*tasks)

    # 将双轨特质/记忆提取与落盘挂载到后台异步任务
    if req.extract_traits_async:
        background_tasks.add_task(_background_extract_and_save, req.avatar_keys, req.user_message)

    return ApiResponse(data={"replies": [item.model_dump() for item in results]})


@app.get("/api/v1/avatars/{avatar_key}/state", response_model=ApiResponse, summary="查询智能体实时心理状态快照")
async def get_avatar_state(avatar_key: str, speaker_id: str = "unknown_stranger"):
    avatar = ctx.orchestrator.avatars.get(avatar_key)
    if not avatar:
        raise HTTPException(status_code=404, detail=f"Avatar '{avatar_key}' not found")
    return ApiResponse(data=avatar.engine.get_current_avatar_state(speaker_id=speaker_id))


@app.post("/api/v1/avatars/paradigm-shift", response_model=ApiResponse, summary="触发外部顿悟/观念重塑事件")
async def trigger_paradigm_shift(req: ParadigmShiftRequest, background_tasks: BackgroundTasks):
    avatar = ctx.orchestrator.avatars.get(req.avatar_key)
    if not avatar:
        raise HTTPException(status_code=404, detail=f"Avatar '{req.avatar_key}' not found")
    avatar.engine.trigger_paradigm_shift_event(
    target_trait=req.target_trait,
    text=req.trigger_text,
    target_absolute_value=req.target_absolute_value
    )
    background_tasks.add_task(ctx.orchestrator.save_all_avatars)
    return ApiResponse(
    message="paradigm shift executed",
    data=avatar.engine.get_current_avatar_state()
    )
@app.post("/api/v1/avatars/save", response_model=ApiResponse, summary="手动触发全量状态持久化存档")
async def save_all():
    ctx.orchestrator.save_all_avatars()
    return ApiResponse(message="all avatars persisted to storage")

if __name__ == "main":
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8088, reload=False)