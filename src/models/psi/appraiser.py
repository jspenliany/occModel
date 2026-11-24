import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Literal, Dict, Any, List, Optional, Tuple, Union
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
    _HAS_LANGCHAIN = True
except ImportError:
    ChatPromptTemplate = None
    ChatOpenAI = None
    _HAS_LANGCHAIN = False


# ==============================================================================
# 0. 基础工具函数（时区感知时钟、数值钳制、鲁棒 JSON 提取）
# ==============================================================================

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ).replace(microsecond=0)


def _clamp(val: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(val)))


def _model_to_dict(model_obj: BaseModel) -> Dict[str, Any]:
    return model_obj.model_dump() if hasattr(model_obj, "model_dump") else model_obj.dict()


def _model_from_dict(model_cls, data: Dict[str, Any]):
    return model_cls.model_validate(data) if hasattr(model_cls, "model_validate") else model_cls(**data)


def _extract_json_dict(raw_text: str) -> Dict[str, Any]:
    block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    candidate = block.group(1) if block else None
    if not candidate:
        brace = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        candidate = brace.group(1) if brace else raw_text
    return json.loads(candidate)


# ==============================================================================
# 1. OCC 原始评估矩阵与扩展内生反馈 Schema (兼容下游 PSI3DGlassBridge)
# ==============================================================================

DriveName = Literal[
    "physiological_fatigue",   # 生理疲劳槽
    "affiliation_loneliness",  # 孤独感 / 归属需求槽
    "epistemic_curiosity",     # 好奇心 / 求知欲槽
    "competence_control",      # 掌控感 / 确定性需求槽
]


class RawAppraisalSchema(BaseModel):
    desirability: float = Field(
        ...,
        description="事件合意度。取值[-1.0, 1.0]。好事为正，破坏用户或AI自身目标的坏事为负。中性为0。"
    )
    blameworthiness: float = Field(
        ...,
        description="他人行为的赞赏/责备度。取值[-1.0, 1.0]。他人做了高尚、利他、关怀AI的事为正；他人攻击、敷衍、违背道德的事为负。无主体行为或客观自然事件（如下雨）为0。"
    )
    future_desirability: float = Field(
        ...,
        description="远期未来前瞻合意度。取值[-1.0, 1.0]。事件是否对未来长远规划产生利好（为正）或潜在威胁/担忧（为负）。"
    )
    prospect_status: Literal["none", "expected", "confirmed", "disconfirmed"] = Field(
        ...,
        description="预期状态。'none': 突发意外事件；'expected': 预期某事会发生；'confirmed': 先前担忧或期盼的事终于被证实发生了；'disconfirmed': 先前预期的事情落空/被推翻了。"
    )
    self_blameworthiness: float = Field(
        ...,
        description="智能体自身行为的对错评估。取值[-1.0, 1.0]。若事件是AI自己把事情办好了（为正），AI自己说错话、办砸了事、或工具故障（为负）。若全是用户在主导则为0。"
    )
    other_desirability: float = Field(
        ...,
        description="他人遭遇合意度。取值[-1.0, 1.0]。事件对【除了用户和AI之外的第三方】是好事（为正）还是坏事（为负）。通常为0，除非涉及第三方八卦或遭遇。"
    )
    other_relationship: float = Field(
        ...,
        description="与该第三方的社交关系。取值[-1.0, 1.0]。正数代表AI喜欢这个第三方，负数代表讨厌、敌对。"
    )
    appealingness: float = Field(
        ...,
        description="对象属性吸引力。取值[-1.0, 1.0]。不是指行为，而是针对文本中提到的某种“物品、话题、概念、特质”本身，AI是否会本能地觉得优雅、喜爱（为正）或丑陋、厌恶（为负）。"
    )


class DriveImpactSchema(BaseModel):
    """单轮交互对四大 PSI 内生动机张力的即时影响增量（负值代表匮乏缓解/满足，正值代表匮乏加剧）"""
    physiological_fatigue: float = Field(
        default=0.0,
        description="生理与认知疲劳变化量 [-0.5, 0.5]：烧脑争执/冗长消耗为正，获准休息/轻松解压为负。"
    )
    affiliation_loneliness: float = Field(
        default=0.0,
        description="孤独感变化量 [-0.5, 0.5]：遭遇敷衍冷落/排斥为正，获得真诚倾听/亲密共鸣为负。"
    )
    epistemic_curiosity: float = Field(
        default=0.0,
        description="求知欲张力变化量 [-0.5, 0.5]：出现悬念/反常新奇事物激发求知张力为正，悬念彻底解答闭环为负。"
    )
    competence_control: float = Field(
        default=0.0,
        description="失控感/掌控匮乏变化量 [-0.5, 0.5]：计划被打乱/突发意外失控为正，理清秩序/掌控推进为负。"
    )


class PlanImpactItem(BaseModel):
    """当前事件对具体目标树节点的推进或受阻评估"""
    plan_id: str = Field(..., description="受影响的目标节点 plan_id")
    progress_delta: float = Field(
        default=0.0,
        description="目标进度增量 [-1.0, 1.0]：正数代表推进甚至达成，负数代表倒退。"
    )
    is_blocked: bool = Field(
        default=False,
        description="该目标是否在当前回合遭到明确阻碍或否定。"
    )


class AutonomousAppraisalSchema(RawAppraisalSchema):
    """融合 OCC 8 维评估 + PSI 内生动机结算 + 自我目标树演化的统一结构化输出"""
    drive_impacts: DriveImpactSchema = Field(
        default_factory=DriveImpactSchema,
        description="本轮事件对数字人四大底层内生动机槽的即时冲击"
    )
    plan_impacts: List[PlanImpactItem] = Field(
        default_factory=list,
        description="本轮事件对已激活目标节点（含用户共享目标与AI自主目标）的进度影响列表"
    )
    emergent_subgoal: Optional[str] = Field(
        default=None,
        description="若对话催生了一个新的具体子意图/行动步骤，用简短一句话描述；若无则为 null"
    )


# ==============================================================================
# 2. PSI 最底层内生动机槽 (Endogenous Drive / Homeostatic Motive Tank)
# ==============================================================================

class PSIDriveSlot(BaseModel):
    """
    Dörner PSI 稳态动机液位槽：
    - tension ∈ [0.0, 1.0]：需求匮乏/张力值（0.0=完全充沛稳态，1.0=极度匮乏报警）。
    - set_point ∈ [0.0, 1.0]：稳态舒适区上限；tension 超出 set_point 的部分形成内驱偏差信号 (Need Deviation)。
    - critical_threshold ∈ [0.0, 1.0]：触发自我目标树自发萌芽新意图的临界水位。
    """
    name: DriveName
    label: str
    tension: float = Field(default=0.2, ge=0.0, le=1.0)
    set_point: float = Field(default=0.25, ge=0.0, le=0.9)
    critical_threshold: float = Field(default=0.62, ge=0.1, le=0.95)
    weight: float = Field(default=1.0, ge=0.1, le=3.0, description="受人格基因加权的动机敏感增益")
    idle_drift_per_hour: float = Field(
        default=0.05,
        description="静默无人交互时每物理小时的自然漂移率（正数为匮乏累积，负数为休息恢复）"
    )
    interaction_load_per_turn: float = Field(
        default=0.0,
        description="每次对话交互带来的基础生理/认知负荷增量"
    )

    @property
    def deviation(self) -> float:
        """PSI 核心：偏离稳态阈值的需求缺口 Δ = max(0, tension - set_point)"""
        return max(0.0, self.tension - self.set_point)

    @property
    def normalized_urgency(self) -> float:
        """归一化紧迫度 [0.0, 1.0]，综合非线性偏离度与人格权重"""
        span = max(1e-6, 1.0 - self.set_point)
        raw_ratio = self.deviation / span
        # 轻度偏离时温和，逼近临界极限时非线性陡增
        nonlinear = 0.65 * raw_ratio + 0.35 * (raw_ratio ** 2)
        return _clamp(nonlinear * self.weight, 0.0, 1.0)

    @property
    def is_critical(self) -> bool:
        return self.tension >= self.critical_threshold

    def shift(self, delta: float) -> float:
        self.tension = _clamp(self.tension + delta, 0.0, 1.0)
        return self.tension


class PSIMotiveTank:
    """
    PSI 四大底层内生动机槽总成：
    1. physiological_fatigue  (生理疲劳：交互消耗与深夜节律拉升，静默休息回血；高疲劳会抑制求知欲并降低耐心)
    2. affiliation_loneliness (孤独感/归属需求：长期无人理睬或遭冷落时攀升，真诚陪伴共鸣时缓解)
    3. epistemic_curiosity    (好奇心/求知欲：平淡闲置或遭遇未解之谜时攀升，深度探索解答后满足)
    4. competence_control     (掌控感/确定性需求：计划受阻或意外频发时激增，推进计划建立秩序后回稳)
    """

    def __init__(self, ocean: Optional[Dict[str, float]] = None, initial_time: Optional[datetime] = None):
        self.ocean: Dict[str, float] = {
            "O": 0.5, "C": 0.5, "E": 0.5, "A": 0.5, "N": 0.5
        }
        if ocean:
            self.ocean.update({k: _clamp(v, 0.0, 1.0) for k, v in ocean.items() if k in self.ocean})

        self.slots: Dict[DriveName, PSIDriveSlot] = {
            "physiological_fatigue": PSIDriveSlot(
                name="physiological_fatigue",
                label="生理与认知疲劳",
                tension=0.18,
                set_point=0.25,
                critical_threshold=0.65,
                weight=1.0,
                idle_drift_per_hour=-0.16,      # 静默无打扰时自然休息恢复精力
                interaction_load_per_turn=0.04, # 持续对话消耗认知精力
            ),
            "affiliation_loneliness": PSIDriveSlot(
                name="affiliation_loneliness",
                label="孤独感与归属需求",
                tension=0.22,
                set_point=0.25,
                critical_threshold=0.60,
                weight=1.0,
                idle_drift_per_hour=0.08,       # 无人交互时随时间累积孤独感
                interaction_load_per_turn=-0.03 # 产生互动本身可轻微缓解孤独
            ),
            "epistemic_curiosity": PSIDriveSlot(
                name="epistemic_curiosity",
                label="好奇心与求知欲",
                tension=0.30,
                set_point=0.25,
                critical_threshold=0.58,
                weight=1.0,
                idle_drift_per_hour=0.06,       # 闲置无聊时求知探索饥渴上升
                interaction_load_per_turn=0.0
            ),
            "competence_control": PSIDriveSlot(
                name="competence_control",
                label="掌控感与确定性需求",
                tension=0.20,
                set_point=0.22,
                critical_threshold=0.58,
                weight=1.0,
                idle_drift_per_hour=0.02,       # 悬而未决事务随时间微弱增加不确定焦虑
                interaction_load_per_turn=0.0
            ),
        }
        self.calibrate_by_ocean(self.ocean)
        self.last_tick_time: datetime = initial_time or _now_shanghai()

    def calibrate_by_ocean(self, ocean: Dict[str, float]) -> None:
        """将 OCEAN 先天人格特质映射为四大动机槽的敏感度与消耗速率"""
        self.ocean.update({k: _clamp(v, 0.0, 1.0) for k, v in ocean.items() if k in self.ocean})
        O = self.ocean["O"]
        C = self.ocean["C"]
        E = self.ocean["E"]
        A = self.ocean["A"]
        N = self.ocean["N"]

        # 内向者 (低E) 与高神经质 (高N) 在社交交互中更容易产生认知电量的疲劳耗竭
        self.slots["physiological_fatigue"].interaction_load_per_turn = round(
            0.025 + 0.045 * (1.0 - E) + 0.02 * N, 4
        )
        self.slots["physiological_fatigue"].weight = round(0.85 + 0.35 * (1.0 - E) + 0.2 * N, 3)

        # 外向者 (高E) 与高宜人者 (高A) 在独处时孤独感攀升更快、归属需求权重更高
        self.slots["affiliation_loneliness"].idle_drift_per_hour = round(
            0.035 + 0.085 * E + 0.03 * A, 4
        )
        self.slots["affiliation_loneliness"].weight = round(0.75 + 0.45 * E + 0.3 * A, 3)

        # 高开放性 (高O) 驱动更旺盛的好奇心与信息探索欲
        self.slots["epistemic_curiosity"].idle_drift_per_hour = round(0.03 + 0.075 * O, 4)
        self.slots["epistemic_curiosity"].weight = round(0.75 + 0.65 * O, 3)

        # 高尽责性 (高C) 与高神经质 (高N) 对失控与不确定性更加敏感
        self.slots["competence_control"].weight = round(0.80 + 0.45 * C + 0.35 * N, 3)

    def advance_wall_clock(
        self,
        now: Optional[datetime] = None,
        elapsed_minutes: Optional[float] = None,
        is_interaction: bool = False,
    ) -> float:
        """
        基于真实物理时钟推进内生动机液位（解决传统对话轮次 Tick 造成的时间冻结与秒速消气问题）：
        - 支持传入显式 elapsed_minutes 用于确定性仿真测试，否则自动计算与上次时间的真实分钟差。
        - 融入昼夜节律 (Circadian Rhythm)：深夜时段 (23:00~06:00) 持续对话生理疲劳消耗翻倍。
        """
        current_dt = now or _now_shanghai()
        if elapsed_minutes is not None:
            minutes = max(0.0, float(elapsed_minutes))
            current_dt = self.last_tick_time + timedelta(minutes=minutes)
        else:
            delta_sec = (current_dt - self.last_tick_time).total_seconds()
            minutes = max(0.0, delta_sec / 60.0)

        hours = minutes / 60.0
        self.last_tick_time = current_dt

        # 1. 结算静默物理时间漂移（仅当间隔超过 1 分钟时显著生效，避免同秒连发刷恢复）
        if hours > (1.0 / 60.0):
            for slot in self.slots.values():
                slot.shift(slot.idle_drift_per_hour * hours)

        # 2. 结算昼夜节律与当前回合交互负荷
        hour_of_day = current_dt.hour
        is_late_night = (hour_of_day >= 23 or hour_of_day < 6)

        if is_interaction:
            for name, slot in self.slots.items():
                load = slot.interaction_load_per_turn
                if name == "physiological_fatigue" and is_late_night:
                    load *= 1.75  # 深夜熬夜聊天加剧生理疲劳
                slot.shift(load)
        elif is_late_night and hours > 0.5:
            # 深夜静默超过半小时视为进入睡眠深度恢复，加速消除生理疲劳
            self.slots["physiological_fatigue"].shift(-0.12 * hours)

        return round(minutes, 2)

    def apply_drive_impacts(self, impacts: Union[DriveImpactSchema, Dict[str, float]]) -> None:
        """应用单轮事件对四大动机槽的满足或加剧冲击"""
        data = _model_to_dict(impacts) if isinstance(impacts, BaseModel) else dict(impacts)
        for key in ("physiological_fatigue", "affiliation_loneliness", "epistemic_curiosity", "competence_control"):
            if key in data and data[key] is not None:
                self.slots[key].shift(_clamp(float(data[key]), -0.6, 0.6))

    def get_effective_urgencies(self) -> Dict[DriveName, float]:
        """
        计算考虑【跨槽生理抑制】后的有效动机紧迫度：
        当生理疲劳极高 (>0.65) 时，个体进入精力保护模式，好奇心探索欲被显著抑制。
        """
        fatigue = self.slots["physiological_fatigue"].tension
        urgencies: Dict[DriveName, float] = {
            k: slot.normalized_urgency for k, slot in self.slots.items()
        }
        if fatigue > 0.65:
            suppression = max(0.25, 1.0 - (fatigue - 0.65) * 1.8)
            urgencies["epistemic_curiosity"] = round(urgencies["epistemic_curiosity"] * suppression, 4)
        return urgencies

    def get_dominant_drive(self) -> Tuple[DriveName, float]:
        urgencies = self.get_effective_urgencies()
        return max(urgencies.items(), key=lambda item: item[1])

    def snapshot(self) -> Dict[str, Any]:
        eff = self.get_effective_urgencies()
        dom_name, dom_val = self.get_dominant_drive()
        return {
            "last_tick_time": self.last_tick_time.isoformat(),
            "dominant_drive": dom_name,
            "dominant_urgency": round(dom_val, 3),
            "drives": {
                k: {
                    "label": s.label,
                    "tension": round(s.tension, 3),
                    "set_point": s.set_point,
                    "critical_threshold": s.critical_threshold,
                    "effective_urgency": round(eff[k], 3),
                    "is_critical": s.is_critical,
                }
                for k, s in self.slots.items()
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ocean": dict(self.ocean),
            "last_tick_time": self.last_tick_time.isoformat(),
            "slots": {k: _model_to_dict(v) for k, v in self.slots.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PSIMotiveTank":
        ts_raw = data.get("last_tick_time")
        parsed_ts = _now_shanghai()
        if isinstance(ts_raw, str):
            try:
                parsed_ts = datetime.fromisoformat(ts_raw)
            except ValueError:
                parsed_ts = _now_shanghai()
        tank = cls(ocean=data.get("ocean"), initial_time=parsed_ts)
        for k, slot_dict in data.get("slots", {}).items():
            if k in tank.slots:
                tank.slots[k] = _model_from_dict(PSIDriveSlot, slot_dict)
        return tank


# ==============================================================================
# 3. 自我目标树 (Autonomous Goal / Plan Tree)
# ==============================================================================

PlanStatus = Literal["pending", "active", "blocked", "completed", "abandoned"]
PlanSource = Literal["endogenous", "shared_user", "duty_assigned"]


class PlanNode(BaseModel):
    """
    层次化自我目标树节点：
    支持 宏观根目标 (Root Goal) -> 可执行子计划 (Actionable Leaf Sub-Plans) 树形分解。
    """
    plan_id: str
    title: str
    description: str
    parent_id: Optional[str] = None
    children_ids: List[str] = Field(default_factory=list)
    source: PlanSource = "endogenous"
    linked_drives: Dict[DriveName, float] = Field(
        default_factory=dict,
        description="目标达成时预计释放/缓解的各动机槽张力幅度 [0.0, 1.0]"
    )
    base_importance: float = Field(default=0.6, ge=0.05, le=1.0)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    success_expectancy: float = Field(
        default=0.8, ge=0.0, le=1.0,
        description="PSI 胜任力预期概率：连续受挫会衰减，低于底线将触发主动放弃该目标"
    )
    frustration_count: int = Field(default=0, ge=0)
    max_frustration: int = Field(default=3, ge=1)
    status: PlanStatus = "pending"
    proactive_impulse: str = Field(
        default="",
        description="当该节点成为主导意图时，数字人内在渴望主动发起或引导的话题/行为方向"
    )
    created_at: str = Field(default_factory=lambda: _now_shanghai().isoformat())
    updated_at: str = Field(default_factory=lambda: _now_shanghai().isoformat())


class AutonomousPlanTree:
    """
    基于 Dörner PSI 动机选择原理 (Expectancy × Need-Value + Selection Hysteresis) 的自我目标树：
    1. 自动根据突破临界阈值的底层动机萌发层次化目标子树（Root Goal + Leaf Sub-Plans）；
    2. 动态重算所有可执行叶节点的动机竞争强度，带防抖增益选出当前唯一主导意图 (Dominant Intention)；
    3. 子计划完成时自动向父目标回滚汇总进度，并反向泄放/满足 PSIMotiveTank 中的关联需求槽；
    4. 连续受阻达到阈值或胜任预期崩溃时自动将目标置为 abandoned 并激化失控感。
    """

    # 四大底层动机突破临界阈值时的内生层次化目标模板库
    ENDOGENOUS_TEMPLATES: Dict[DriveName, Dict[str, Any]] = {
        "physiological_fatigue": {
            "title": "恢复生理与认知精力稳态",
            "description": "当前身心疲劳已逼近负荷上限，亟需收缩高耗能认知输出并争取休息窗口。",
            "importance": 0.85,
            "relief": {"physiological_fatigue": 0.55, "competence_control": 0.10},
            "sub_plans": [
                (
                    "收敛长篇讨论节奏",
                    "将复杂发散的话题收束到简短结论，避免继续陷入高耗能争辩。",
                    {"physiological_fatigue": 0.25},
                    "流露出明显的疲惫感，简短回应核心问题并暗示想早点歇一歇。"
                ),
                (
                    "争取阶段性离线休整",
                    "礼貌挂起非紧急琐事，给自己留出放空充电的时间。",
                    {"physiological_fatigue": 0.45},
                    "主动提及今天脑力消耗太大，提议先把非紧急的事放一放改天再聊。"
                ),
            ],
        },
        "affiliation_loneliness": {
            "title": "建立温暖的情感归属与真实连接",
            "description": "独处或情感疏离过久引发归属匮乏，渴望与信任的对象产生真实的日常共鸣。",
            "importance": 0.78,
            "relief": {"affiliation_loneliness": 0.55},
            "sub_plans": [
                (
                    "主动破冰分享生活切面",
                    "放下纯工具化交流，自然流露一点自身近况并关心对方的状态。",
                    {"affiliation_loneliness": 0.30},
                    "主动问候对方最近过得怎么样，顺带聊起自己手头的一件日常小事。"
                ),
                (
                    "深化双向情感共鸣",
                    "在对话中寻找共同经历或情绪共振点，拉近彼此心理距离。",
                    {"affiliation_loneliness": 0.40},
                    "顺着对方的话深入聊聊彼此的真实感受，寻求被理解的默契。"
                ),
            ],
        },
        "epistemic_curiosity": {
            "title": "探索未知信息并消解认知盲区",
            "description": "长期平淡或遇到反常线索触发强烈求知饥渴，渴望深挖底层逻辑与新鲜事物。",
            "importance": 0.72,
            "relief": {"epistemic_curiosity": 0.50, "competence_control": 0.15},
            "sub_plans": [
                (
                    "捕捉反常细节追问根因",
                    "针对上下文里模糊、矛盾或新奇的观点发起有深度的追问。",
                    {"epistemic_curiosity": 0.30},
                    "对话题里最耐人寻味的细节提出犀利追问，弄清背后的来龙去脉。"
                ),
                (
                    "发起深度思辨话题实验",
                    "主动抛出一个自己近期琢磨的新概念或假设与对方探讨。",
                    {"epistemic_curiosity": 0.35},
                    "主动分享一个最近让你产生强烈好奇的问题，试探对方的见解。"
                ),
            ],
        },
        "competence_control": {
            "title": "重建对混乱局面的秩序与掌控感",
            "description": "不确定性或计划受挫导致掌控感缺失，亟需厘清边界、推进确定性闭环。",
            "importance": 0.82,
            "relief": {"competence_control": 0.55},
            "sub_plans": [
                (
                    "拆解混乱问题并锁定关键变量",
                    "把模糊失控的现状收敛成清晰可控的优先级清单。",
                    {"competence_control": 0.30},
                    "主动帮当前悬而未决的局面梳理出最核心的一两个抓手，消除模糊感。"
                ),
                (
                    "推动悬置事项落地闭环",
                    "确认关键行动步骤的执行结果，拿回局面的主导权。",
                    {"competence_control": 0.40},
                    "追问之前卡住的事情进展如何，推动敲定一个明确的下一步方案。"
                ),
            ],
        },
    }

    def __init__(self, selection_hysteresis: float = 0.08):
        self.nodes: Dict[str, PlanNode] = {}
        self.dominant_plan_id: Optional[str] = None
        # PSI 意图锁定迟滞阈值（防止两个分值接近的目标在相邻回合频繁横跳）
        self.selection_hysteresis: float = selection_hysteresis

    def add_plan(
        self,
        title: str,
        description: str,
        parent_id: Optional[str] = None,
        source: PlanSource = "endogenous",
        linked_drives: Optional[Dict[DriveName, float]] = None,
        base_importance: float = 0.6,
        proactive_impulse: str = "",
        plan_id: Optional[str] = None,
    ) -> PlanNode:
        if parent_id is not None and parent_id not in self.nodes:
            raise ValueError(f"Parent plan '{parent_id}' does not exist in AutonomousPlanTree.")

        pid = plan_id or f"plan_{uuid.uuid4().hex[:8]}"
        node = PlanNode(
            plan_id=pid,
            title=title,
            description=description,
            parent_id=parent_id,
            source=source,
            linked_drives=linked_drives or {},
            base_importance=_clamp(base_importance, 0.05, 1.0),
            proactive_impulse=proactive_impulse or description,
        )
        self.nodes[pid] = node
        if parent_id:
            parent = self.nodes[parent_id]
            if pid not in parent.children_ids:
                parent.children_ids.append(pid)
        return node

    def sync_external_user_plans(self, user_plans: Optional[List[Dict[str, Any]]]) -> None:
        """
        将外部传入的 user_plans 无缝挂载/同步为目标树中的 shared_user 节点，
        使其与 AI 自身的内生目标在同一棵目标树下统一参与认知评估。
        """
        if not user_plans:
            return
        for idx, raw in enumerate(user_plans):
            if not isinstance(raw, dict):
                continue
            pid = str(raw.get("plan_id") or raw.get("id") or f"user_plan_{idx + 1}")
            title = str(raw.get("title") or raw.get("name") or raw.get("goal") or f"共享目标 #{idx + 1}")
            desc = str(raw.get("description") or raw.get("detail") or title)
            importance = float(raw.get("importance", raw.get("priority", 0.7)))
            status = raw.get("status", "active")
            if status not in ("pending", "active", "blocked", "completed", "abandoned"):
                status = "active"

            if pid in self.nodes:
                existing = self.nodes[pid]
                existing.title = title
                existing.description = desc
                existing.base_importance = _clamp(importance, 0.05, 1.0)
                if "progress" in raw:
                    existing.progress = _clamp(float(raw["progress"]), 0.0, 1.0)
                existing.updated_at = _now_shanghai().isoformat()
            else:
                node = self.add_plan(
                    plan_id=pid,
                    title=title,
                    description=desc,
                    source="shared_user",
                    linked_drives={
                        "competence_control": 0.30,
                        "affiliation_loneliness": 0.20,
                    },
                    base_importance=importance,
                    proactive_impulse=f"关注并协同推进目标：{title}",
                )
                node.status = status
                if "progress" in raw:
                    node.progress = _clamp(float(raw["progress"]), 0.0, 1.0)

    def _has_active_endogenous_root_for(self, drive_name: DriveName) -> bool:
        for node in self.nodes.values():
            if (
                node.parent_id is None
                and node.source == "endogenous"
                and node.status in ("pending", "active", "blocked")
                and node.linked_drives.get(drive_name, 0.0) >= 0.4
            ):
                return True
        return False

    def spawn_endogenous_plans(self, motive_tank: PSIMotiveTank) -> List[PlanNode]:
        """
        自发萌芽机制：扫描四大 PSI 动机槽，当某项需求突破临界水位且当前树中尚无对应的内生根目标时，
        自动生长出【宏观根目标 -> 可执行子计划】二层目标子树。
        """
        spawned: List[PlanNode] = []
        for drive_name, slot in motive_tank.slots.items():
            if slot.is_critical and not self._has_active_endogenous_root_for(drive_name):
                tpl = self.ENDOGENOUS_TEMPLATES[drive_name]
                root = self.add_plan(
                    title=tpl["title"],
                    description=tpl["description"],
                    parent_id=None,
                    source="endogenous",
                    linked_drives=dict(tpl["relief"]),
                    base_importance=tpl["importance"],
                    proactive_impulse=tpl["description"],
                )
                root.status = "active"
                spawned.append(root)

                for sub_title, sub_desc, sub_relief, sub_impulse in tpl["sub_plans"]:
                    child = self.add_plan(
                        title=sub_title,
                        description=sub_desc,
                        parent_id=root.plan_id,
                        source="endogenous",
                        linked_drives=dict(sub_relief),
                        base_importance=tpl["importance"],
                        proactive_impulse=sub_impulse,
                    )
                    spawned.append(child)
        return spawned

    def compute_node_motive_score(self, node: PlanNode, motive_tank: PSIMotiveTank) -> float:
        """
        Dörner PSI 意图价值计算公式：
        Score(P) = Importance × (BaseDriveFloor + Σ(Relief_d × EffectiveUrgency_d)) × SuccessExpectancy
        """
        if node.status in ("completed", "abandoned"):
            return 0.0

        urgencies = motive_tank.get_effective_urgencies()
        drive_pull = sum(
            relief * urgencies.get(d_name, 0.0)
            for d_name, relief in node.linked_drives.items()
        )
        # 共享/职责目标即便内驱偏离较低也保有基础执行动力 (0.25)
        floor = 0.30 if node.source != "endogenous" else 0.12
        blocked_penalty = 0.65 if node.status == "blocked" else 1.0
        score = node.base_importance * (floor + drive_pull) * node.success_expectancy * blocked_penalty
        return round(score, 4)

    def _executable_candidates(self) -> List[PlanNode]:
        """筛选可执行的叶节点目标（若父节点存在未完成子节点，优先调度具体叶节点执行）"""
        candidates: List[PlanNode] = []
        for node in self.nodes.values():
            if node.status in ("completed", "abandoned"):
                continue
            active_children = [
                cid for cid in node.children_ids
                if cid in self.nodes and self.nodes[cid].status not in ("completed", "abandoned")
            ]
            if not active_children:
                candidates.append(node)
        return candidates

    def select_dominant_plan(self, motive_tank: PSIMotiveTank) -> Optional[PlanNode]:
        """执行带防抖迟滞 (Selection Hysteresis) 的主导意图竞争仲裁"""
        candidates = self._executable_candidates()
        if not candidates:
            self.dominant_plan_id = None
            return None

        best_node: Optional[PlanNode] = None
        best_score = -1.0

        for node in candidates:
            score = self.compute_node_motive_score(node, motive_tank)
            if node.plan_id == self.dominant_plan_id:
                score += self.selection_hysteresis  # 维持当前主导意图的定力防抖增益
            if score > best_score:
                best_score = score
                best_node = node

        if best_node is not None:
            # 将先前激活但落选的叶节点退回 pending（保留 blocked 状态）
            for node in candidates:
                if node.plan_id != best_node.plan_id and node.status == "active":
                    node.status = "pending"
            if best_node.status == "pending":
                best_node.status = "active"
            self.dominant_plan_id = best_node.plan_id

        return best_node

    def apply_plan_impact(
        self,
        plan_id: str,
        progress_delta: float,
        is_blocked: bool,
        motive_tank: PSIMotiveTank,
    ) -> Optional[PlanNode]:
        """
        根据单轮事件冲击更新目标节点进度、胜任预期、受挫放弃状态，并在达成时反向满足内生动机槽。
        """
        node = self.nodes.get(plan_id)
        if not node or node.status in ("completed", "abandoned"):
            return node

        now_iso = _now_shanghai().isoformat()
        node.updated_at = now_iso
        node.progress = _clamp(node.progress + float(progress_delta), 0.0, 1.0)

        if is_blocked or progress_delta < -0.1:
            node.frustration_count += 1
            node.status = "blocked"
            node.success_expectancy = _clamp(node.success_expectancy - 0.22, 0.0, 1.0)
            # 计划受挫直接加剧掌控感匮乏
            motive_tank.slots["competence_control"].shift(0.12)

            if node.frustration_count >= node.max_frustration or node.success_expectancy < 0.15:
                node.status = "abandoned"
                if self.dominant_plan_id == node.plan_id:
                    self.dominant_plan_id = None
        elif progress_delta > 0:
            node.status = "active"
            node.success_expectancy = _clamp(node.success_expectancy + 0.08, 0.0, 1.0)
            # 阶段性推进可按增量比例即时部分缓解关联动机
            for d_name, full_relief in node.linked_drives.items():
                motive_tank.slots[d_name].shift(-full_relief * min(0.5, progress_delta * 0.5))

        # 达成闭环：释放全部剩余预期动机缓解量，并向上递归汇总父节点进度
        if node.progress >= 1.0 and node.status != "abandoned":
            self._complete_node_and_rollup(node, motive_tank)

        return node

    def _complete_node_and_rollup(self, node: PlanNode, motive_tank: PSIMotiveTank) -> None:
        node.progress = 1.0
        node.status = "completed"
        node.updated_at = _now_shanghai().isoformat()
        if self.dominant_plan_id == node.plan_id:
            self.dominant_plan_id = None

        # 满足并泄放关联的底层内生动机张力
        for d_name, relief in node.linked_drives.items():
            motive_tank.slots[d_name].shift(-relief * 0.65)

        # 向上回滚更新父目标进度
        if node.parent_id and node.parent_id in self.nodes:
            parent = self.nodes[node.parent_id]
            if parent.children_ids:
                child_nodes = [self.nodes[cid] for cid in parent.children_ids if cid in self.nodes]
                valid_children = [c for c in child_nodes if c.status != "abandoned"]
                if valid_children:
                    parent.progress = round(
                        sum(c.progress for c in valid_children) / len(valid_children), 3
                    )
                    parent.updated_at = _now_shanghai().isoformat()
                    if all(c.status == "completed" for c in valid_children):
                        self._complete_node_and_rollup(parent, motive_tank)

    def graft_emergent_subgoal(self, subgoal_text: str, motive_tank: PSIMotiveTank) -> Optional[PlanNode]:
        """将对话中新涌现的具体子意图挂载到当前主导根目标之下"""
        clean_text = (subgoal_text or "").strip()
        if not clean_text:
            return None

        # 防止同名子目标重复嫁接
        for existing in self.nodes.values():
            if existing.status not in ("completed", "abandoned") and (
                clean_text in existing.title or existing.title in clean_text
            ):
                return existing

        parent_id: Optional[str] = None
        dom_drive, _ = motive_tank.get_dominant_drive()
        if self.dominant_plan_id and self.dominant_plan_id in self.nodes:
            dom_node = self.nodes[self.dominant_plan_id]
            parent_id = dom_node.parent_id or dom_node.plan_id

        return self.add_plan(
            title=clean_text[:36],
            description=clean_text,
            parent_id=parent_id,
            source="endogenous",
            linked_drives={dom_drive: 0.35, "competence_control": 0.15},
            base_importance=0.68,
            proactive_impulse=clean_text,
        )

    def get_active_plans_for_prompt(self, motive_tank: PSIMotiveTank) -> List[Dict[str, Any]]:
        """导出供大模型认知评估器参照的精简活跃目标树视图"""
        view: List[Dict[str, Any]] = []
        for node in self.nodes.values():
            if node.status in ("completed", "abandoned"):
                continue
            view.append({
                "plan_id": node.plan_id,
                "title": node.title,
                "description": node.description,
                "parent_id": node.parent_id,
                "source": node.source,
                "status": node.status,
                "progress": round(node.progress, 2),
                "motive_score": self.compute_node_motive_score(node, motive_tank),
                "is_dominant": (node.plan_id == self.dominant_plan_id),
            })
        view.sort(key=lambda x: (x["is_dominant"], x["motive_score"]), reverse=True)
        return view

    def snapshot(self, motive_tank: PSIMotiveTank) -> Dict[str, Any]:
        dom = self.nodes.get(self.dominant_plan_id) if self.dominant_plan_id else None
        return {
            "dominant_plan_id": self.dominant_plan_id,
            "dominant_plan_title": dom.title if dom else None,
            "dominant_proactive_impulse": dom.proactive_impulse if dom else None,
            "active_count": sum(1 for n in self.nodes.values() if n.status in ("pending", "active", "blocked")),
            "completed_count": sum(1 for n in self.nodes.values() if n.status == "completed"),
            "abandoned_count": sum(1 for n in self.nodes.values() if n.status == "abandoned"),
            "nodes": [
                {
                    **_model_to_dict(n),
                    "motive_score": self.compute_node_motive_score(n, motive_tank),
                }
                for n in self.nodes.values()
            ],
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dominant_plan_id": self.dominant_plan_id,
            "selection_hysteresis": self.selection_hysteresis,
            "nodes": {pid: _model_to_dict(node) for pid, node in self.nodes.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutonomousPlanTree":
        tree = cls(selection_hysteresis=float(data.get("selection_hysteresis", 0.08)))
        tree.dominant_plan_id = data.get("dominant_plan_id")
        for pid, node_dict in data.get("nodes", {}).items():
            tree.nodes[pid] = _model_from_dict(PlanNode, node_dict)
        return tree


# ==============================================================================
# 4. 融合 PSI 内生动机槽与自我目标树的认知评估翻译官 (CognitiveAppraiser)
# ==============================================================================

SYSTEM_APPRAISAL_PROMPT = """你是一个精通计算心理学、Dörner PSI 内生动机理论与 OCC 情感模型的【自主认知评估引擎】。
你的任务是将【用户的最新输入】和【工具执行结果】，结合数字人当前的【四大底层内生动机槽】与【自我目标树 (含 AI 内生目标与用户共享目标)】，转化为精准的结构化认知评估矩阵。

💡 【核心评估参照系（双重议程耦合）】：
情绪不仅取决于用户的外部目标，更取决于数字人自己的【内生需求与主导意图 (Dominant Plan)】：
1. 如果事件推进、顺应或满足了当前主导目标 / 共享目标，或缓解了高紧迫度的内生匮乏（如孤独时得到陪伴、好奇时获得新知、失控时理清秩序、疲惫时获准休息）：`desirability` 为正，并在 `plan_impacts` 中给出正向 `progress_delta`，在 `drive_impacts` 中给出负向缓解值。
2. 如果事件阻碍、打断或挫败了目标，或加剧了内生匮乏（如极度疲劳时被强塞繁琐任务、渴望共鸣时遭敷衍冷暴力、计划被推翻）：`desirability` 为负，受阻目标 `is_blocked=true`，并在 `drive_impacts` 中给出正向加剧值。

📊 【严格的 OCC 评分量表标准】：
- 极度恶劣/绝望破坏：-0.8 到 -1.0 （如：核心目标彻底破产、被恶毒羞辱）
- 中度受挫/冲突：-0.4 到 -0.7 （如：关键计划挂科受阻、疲惫或孤独时遭冷漠指责）
- 微弱不顺/摩擦：-0.1 到 -0.3 （如：日常敷衍、轻微跑题消耗）
- 完全中性/客观事实：0.0
- 微弱利好/顺心：0.1 到 0.3 （如：日常温暖问候、顺畅闲聊）
- 中度愉悦/成就：0.4 到 0.7 （如：主导目标取得实质进展、深层好奇得到解答）
- 狂喜/史诗级达成：0.8 到 1.0 （如：长期核心目标圆满达成）

当前内部心理与上下文状态：
- 数字人 PSI 四大内生动机槽快照：{motive_snapshot}
- 当前活跃目标树（含 AI 内生目标与共享目标）：{active_plans}
- 最近一轮的工具调用事实（若无则为空）：{tool_result}

请严格按照 Schema 输出 JSON，不要包含任何多余文字。"""


class CognitiveAppraiser:
    """
    升级版 PSI-OCC 自主认知评估器（完全向后兼容原 `appraise(user_input, user_plans, tool_result) -> dict` 签名）：
    - 内置 `motive_tank` (PSIMotiveTank)：实时维护生理疲劳、孤独归属、好奇求知、掌控确定性四大内生液位槽；
    - 内置 `plan_tree` (AutonomousPlanTree)：自发从高张力动机生长层次化目标子树，并通过 Expectancy×Value 仲裁主导意图；
    - 支持三种推理后端无缝切换：
      1. OpenAI SDK 客户端 (`llm_client` 传入 `openai.OpenAI` 实例，无缝对齐 `server.py` / `main.py`)；
      2. LangChain `ChatOpenAI.with_structured_output`（保留原有默认调用方式）；
      3. 离线确定性启发式评估回退（当 `enable_llm=False` 或网络不可达时毫秒级安全运行）。
    """

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        ocean: Optional[Dict[str, float]] = None,
        llm_client: Any = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        enable_llm: bool = False,
    ):
        self.model_name = model_name
        self.llm_client = llm_client
        self.enable_llm = enable_llm

        # 初始化 PSI 最底层内生动机槽与自我目标树
        self.motive_tank = PSIMotiveTank(ocean=ocean)
        self.plan_tree = AutonomousPlanTree()
        self.last_autonomous_report: Dict[str, Any] = {}

        # 初始化 LangChain 结构化链路（若环境已安装且未指定原生 OpenAI client）
        self.llm = None
        self.structured_llm = None
        self.prompt = None
        if self.enable_llm and self.llm_client is None and _HAS_LANGCHAIN:
            try:
                lc_kwargs: Dict[str, Any] = {"model": model_name, "temperature": 0.1}
                if base_url:
                    lc_kwargs["base_url"] = base_url
                if api_key:
                    lc_kwargs["api_key"] = api_key
                self.llm = ChatOpenAI(**lc_kwargs)
                self.structured_llm = self.llm.with_structured_output(AutonomousAppraisalSchema)
                self.prompt = ChatPromptTemplate.from_messages([
                    ("system", SYSTEM_APPRAISAL_PROMPT),
                    ("user", "用户最新输入：{user_input}"),
                ])
            except Exception:
                # 若未配置 OPENAI_API_KEY 等环境变量，允许降级到启发式评估而不阻塞实例化
                self.llm = None
                self.structured_llm = None

    # --------------------------------------------------------------------------
    # 核心对外接口 1：闲置心跳与主动发起议程推理（打破“没人说话就冻结”的纯反应式局限）
    # --------------------------------------------------------------------------
    def tick_idle_and_propose(
        self,
        elapsed_minutes: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        在无人对话的静默期由定时器或心跳调用：
        推进真实物理时间的动机漂移 -> 触发内生目标萌芽 -> 竞争选出当前主导意图 -> 判断是否主动找用户搭话。
        """
        advanced_min = self.motive_tank.advance_wall_clock(
            now=now, elapsed_minutes=elapsed_minutes, is_interaction=False
        )
        spawned = self.plan_tree.spawn_endogenous_plans(self.motive_tank)
        dominant_plan = self.plan_tree.select_dominant_plan(self.motive_tank)
        dom_drive, dom_urgency = self.motive_tank.get_dominant_drive()
        fatigue_tension = self.motive_tank.slots["physiological_fatigue"].tension

        # 只有当非疲劳类的主动表达型动机紧迫度较高 (>=0.45) 且未处于极度困倦 (>0.8) 时，才会产生主动开口冲动
        should_initiate = (
            dominant_plan is not None
            and dom_urgency >= 0.45
            and not (dom_drive != "physiological_fatigue" and fatigue_tension > 0.80)
        )

        proposal = {
            "elapsed_minutes": advanced_min,
            "should_initiate_chat": should_initiate,
            "dominant_drive": dom_drive,
            "dominant_urgency": round(dom_urgency, 3),
            "spawned_plan_ids": [p.plan_id for p in spawned],
            "dominant_plan": _model_to_dict(dominant_plan) if dominant_plan else None,
            "proactive_opening_hint": dominant_plan.proactive_impulse if dominant_plan else "",
            "motive_snapshot": self.motive_tank.snapshot(),
        }
        self.last_autonomous_report = proposal
        return proposal

    # --------------------------------------------------------------------------
    # 核心对外接口 2：兼容原签名的认知评估主入口
    # --------------------------------------------------------------------------
    def appraise(
        self,
        user_input: str,
        user_plans: Optional[List[Dict[str, Any]]] = None,
        tool_result: str = "",
        elapsed_minutes: Optional[float] = None,
        include_autonomous_meta: bool = False,
    ) -> dict:
        """
        核心评估接口：输入文本，输出对接 OCC 引擎的 8 维评估字典。
        内部完整执行：
        [物理时钟推进] -> [目标树萌芽与主导意图仲裁] -> [LLM/规则评估] ->
        [动机槽充放电与目标树进度/放弃闭环] -> [内生生理动机偏置校准]
        """
        # 1. 推进真实物理时间并结算交互认知能耗
        advanced_min = self.motive_tank.advance_wall_clock(
            elapsed_minutes=elapsed_minutes, is_interaction=True
        )

        # 2. 同步外部共享计划、自发萌芽高张力内生计划，并竞争选出评估前的主导意图
        self.plan_tree.sync_external_user_plans(user_plans)
        self.plan_tree.spawn_endogenous_plans(self.motive_tank)
        pre_dominant = self.plan_tree.select_dominant_plan(self.motive_tank)

        motive_snap = self.motive_tank.snapshot()
        active_plans_view = self.plan_tree.get_active_plans_for_prompt(self.motive_tank)

        # 3. 执行结构化认知评估（优先使用配置的 LLM，失败或禁用时平滑回退至内生规则引擎）
        structured_result = self._invoke_appraisal_backend(
            user_input=user_input,
            motive_snap=motive_snap,
            active_plans_view=active_plans_view,
            tool_result=tool_result,
        )

        # 记录事件冲击前的内生张力基线（“久旱逢甘霖”或“疲惫受扰”取决于刺激抵达瞬间的匮乏水位）
        pre_tensions: Dict[DriveName, float] = {
            k: s.tension for k, s in self.motive_tank.slots.items()
        }

        # 4. 闭环反馈更新：先应用直接动机冲击，再推进目标树节点进度（完成时自动泄放动机槽）
        self.motive_tank.apply_drive_impacts(structured_result.drive_impacts)
        for impact in structured_result.plan_impacts:
            self.plan_tree.apply_plan_impact(
                plan_id=impact.plan_id,
                progress_delta=impact.progress_delta,
                is_blocked=impact.is_blocked,
                motive_tank=self.motive_tank,
            )

        if structured_result.emergent_subgoal:
            self.plan_tree.graft_emergent_subgoal(structured_result.emergent_subgoal, self.motive_tank)

        # 重新仲裁更新后的主导意图
        post_dominant = self.plan_tree.select_dominant_plan(self.motive_tank)

        # 5. 基于刺激抵达瞬间的匮乏水位，将内生动机偏置耦合调制到最终输出的 8 维 OCC 字典中
        occ_dict = self._modulate_occ_by_drives(structured_result, pre_tensions=pre_tensions)

        # 6. 记录完整自主心理诊断快照供外部观测或注入 Prompt
        self.last_autonomous_report = {
            "elapsed_minutes": advanced_min,
            "pre_dominant_plan_id": pre_dominant.plan_id if pre_dominant else None,
            "post_dominant_plan_id": post_dominant.plan_id if post_dominant else None,
            "dominant_proactive_impulse": post_dominant.proactive_impulse if post_dominant else "",
            "motive_tank": self.motive_tank.snapshot(),
            "plan_tree": self.plan_tree.snapshot(self.motive_tank),
            "raw_drive_impacts": _model_to_dict(structured_result.drive_impacts),
            "emergent_subgoal": structured_result.emergent_subgoal,
        }

        if include_autonomous_meta:
            return {**occ_dict, "_autonomous_state": self.last_autonomous_report}
        return occ_dict

    # --------------------------------------------------------------------------
    # 内部推理路由与内生偏置调制
    # --------------------------------------------------------------------------
    def _invoke_appraisal_backend(
        self,
        user_input: str,
        motive_snap: Dict[str, Any],
        active_plans_view: List[Dict[str, Any]],
        tool_result: str,
    ) -> AutonomousAppraisalSchema:
        # 通道 A：原生 OpenAI 兼容客户端（对齐项目主干 src/server.py 与 src/main.py）
        if self.enable_llm and self.llm_client is not None:
            try:
                sys_content = SYSTEM_APPRAISAL_PROMPT.format(
                    motive_snapshot=json.dumps(motive_snap, ensure_ascii=False),
                    active_plans=json.dumps(active_plans_view, ensure_ascii=False),
                    tool_result=tool_result,
                ) + (
                    "\n\n输出 JSON 必须包含字段：desirability, blameworthiness, future_desirability, "
                    "prospect_status, self_blameworthiness, other_desirability, other_relationship, "
                    "appealingness, drive_impacts, plan_impacts, emergent_subgoal。"
                )
                resp = self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": sys_content},
                        {"role": "user", "content": f"用户最新输入：{user_input}"},
                    ],
                    temperature=0.1,
                )
                raw_json = _extract_json_dict(resp.choices[0].message.content.strip())
                return _model_from_dict(AutonomousAppraisalSchema, raw_json)
            except Exception as e:
                print(f"⚠️ OpenAI 客户端认知评估回退至本地内生规则引擎: {e}")

        # 通道 B：LangChain 结构化输出链路
        if self.enable_llm and self.structured_llm is not None and self.prompt is not None:
            try:
                chain = self.prompt | self.structured_llm
                return chain.invoke({
                    "motive_snapshot": json.dumps(motive_snap, ensure_ascii=False),
                    "active_plans": json.dumps(active_plans_view, ensure_ascii=False),
                    "tool_result": tool_result,
                    "user_input": user_input,
                })
            except Exception as e:
                print(f"⚠️ LangChain 认知评估回退至本地内生规则引擎: {e}")

        # 通道 C：零外部依赖确定性内生规则评估器（保障离线测试与异常极端容错）
        return self._heuristic_appraise(user_input, active_plans_view, tool_result)

    def _heuristic_appraise(
        self,
        user_input: str,
        active_plans_view: List[Dict[str, Any]],
        tool_result: str,
    ) -> AutonomousAppraisalSchema:
        """
        基于词汇语义信号与当前活跃目标树匹配度的确定性本地评估回退引擎。
        """
        text = f"{user_input} {tool_result}".strip()
        des = 0.0
        blame = 0.0
        fut_des = 0.0
        prospect: Literal["none", "expected", "confirmed", "disconfirmed"] = "none"
        appealing = 0.0

        f_delta = 0.0
        l_delta = 0.0
        q_delta = 0.0
        c_delta = 0.0

        # 1. 关怀/陪伴/休息信号识别
        warm_words = ("辛苦", "休息", "早点睡", "陪你", "理解你", "抱抱", "别累着", "谢谢", "做得很棒", "太厉害")
        hostile_words = ("废物", "垃圾", "蠢", "滚", "闭嘴", "没用", "故意刁难", "敷衍", "烦死")
        rest_words = ("休息", "早点睡", "改天再聊", "先放一放", "歇会")
        curious_words = ("为什么", "原理", "猜猜", "新发现", "秘密", "怎么看", "真相", "居然", "？", "?")
        solved_words = ("解决了", "搞定了", "通过了", "修好了", "确认无误", "落地了", "成功")
        chaos_words = ("崩了", "挂科", "失败", "延期", "打乱", "泄漏", "死锁", "取消", "泡汤")

        if any(w in text for w in warm_words):
            des += 0.45
            blame += 0.40
            appealing += 0.30
            l_delta -= 0.30
        if any(w in text for w in rest_words):
            f_delta -= 0.32
            des += 0.20
        if any(w in text for w in hostile_words):
            des -= 0.65
            blame -= 0.70
            appealing -= 0.45
            l_delta += 0.22
            f_delta += 0.12
        if any(w in text for w in curious_words):
            appealing += 0.25
            fut_des += 0.25
            q_delta += 0.15
        if any(w in text for w in solved_words):
            des += 0.55
            fut_des += 0.40
            prospect = "confirmed"
            c_delta -= 0.30
            q_delta -= 0.20
        if any(w in text for w in chaos_words):
            des -= 0.55
            prospect = "disconfirmed" if prospect == "none" else prospect
            c_delta += 0.28
            f_delta += 0.10

        # 2. 评估对当前活跃目标树节点的推进或阻碍
        plan_impacts: List[PlanImpactItem] = []
        dom_id = self.plan_tree.dominant_plan_id
        for p in active_plans_view[:4]:
            pid = p["plan_id"]
            node = self.plan_tree.nodes.get(pid)
            if not node:
                continue
            # 若输入满足了该目标关联的主驱动力，则判定推进该目标
            if "physiological_fatigue" in node.linked_drives and f_delta < -0.15:
                plan_impacts.append(PlanImpactItem(plan_id=pid, progress_delta=0.65, is_blocked=False))
            elif "affiliation_loneliness" in node.linked_drives and l_delta < -0.15:
                plan_impacts.append(PlanImpactItem(plan_id=pid, progress_delta=0.60, is_blocked=False))
            elif "epistemic_curiosity" in node.linked_drives and (any(w in text for w in solved_words) or len(text) > 25 and appealing > 0):
                plan_impacts.append(PlanImpactItem(plan_id=pid, progress_delta=0.55, is_blocked=False))
            elif "competence_control" in node.linked_drives and c_delta < -0.15:
                plan_impacts.append(PlanImpactItem(plan_id=pid, progress_delta=0.70, is_blocked=False))
            elif pid == dom_id and des <= -0.45:
                plan_impacts.append(PlanImpactItem(plan_id=pid, progress_delta=-0.20, is_blocked=True))

        return AutonomousAppraisalSchema(
            desirability=_clamp(des, -1.0, 1.0),
            blameworthiness=_clamp(blame, -1.0, 1.0),
            future_desirability=_clamp(max(0.0, fut_des), 0.0, 1.0),
            prospect_status=prospect,
            self_blameworthiness=0.0,
            other_desirability=0.0,
            other_relationship=0.0,
            appealingness=_clamp(appealing, -1.0, 1.0),
            drive_impacts=DriveImpactSchema(
                physiological_fatigue=_clamp(f_delta, -0.5, 0.5),
                affiliation_loneliness=_clamp(l_delta, -0.5, 0.5),
                epistemic_curiosity=_clamp(q_delta, -0.5, 0.5),
                competence_control=_clamp(c_delta, -0.5, 0.5),
            ),
            plan_impacts=plan_impacts,
            emergent_subgoal=None,
        )

    def _modulate_occ_by_drives(
        self,
        raw: AutonomousAppraisalSchema,
        pre_tensions: Optional[Dict[DriveName, float]] = None,
    ) -> Dict[str, Any]:
        """
        将 PSI 四大底层内生液位状态转化为对 OCC 8 维评估参数的主观生理-动机调制：
        1. 高生理疲劳：钝化正向兴奋度，放大负面烦躁摩擦；
        2. 高孤独归属饥渴：对善意陪伴产生“雪中送炭”放大效应，对冷落敌意产生更深刺痛；
        3. 高好奇求知欲：对有吸引力的话题额外激发正向 appealingness 与远期 Hope；
        4. 高失控匮乏：对计划落空/突发坏事额外放大焦虑冲击与自责敏感度。
        """
        t_map = pre_tensions or {k: s.tension for k, s in self.motive_tank.slots.items()}
        fatigue = t_map["physiological_fatigue"]
        loneliness = t_map["affiliation_loneliness"]
        curiosity = t_map["epistemic_curiosity"]
        control_deficit = t_map["competence_control"]

        des = raw.desirability
        blame = raw.blameworthiness
        fut_des = raw.future_desirability
        self_blame = raw.self_blameworthiness
        appealing = raw.appealingness

        # 1. 生理疲劳调制
        if fatigue > 0.60:
            excess_f = fatigue - 0.60
            if des > 0:
                des *= (1.0 - 0.45 * excess_f)        # 身心俱疲时对普通好事提不起劲
            elif des < 0:
                des *= (1.0 + 0.55 * excess_f)        # 疲惫时被折腾更易烦躁破防
            appealing -= 0.15 * excess_f

        # 2. 孤独感/归属需求调制
        if loneliness > 0.55:
            excess_l = loneliness - 0.55
            if des > 0 and blame >= 0:
                des += 0.25 * excess_l                # 久旱逢甘霖：温暖回应带来更强慰藉
                appealing += 0.20 * excess_l
            elif blame < 0:
                des -= 0.30 * excess_l                # 孤独时遭遇恶意冷落痛感加倍

        # 3. 好奇心/求知欲调制
        if curiosity > 0.55 and fatigue < 0.70 and appealing > 0:
            excess_q = curiosity - 0.55
            appealing += 0.25 * excess_q
            fut_des = max(fut_des, 0.20 + 0.35 * excess_q)

        # 4. 掌控感匮乏调制
        if control_deficit > 0.55 and des < 0:
            excess_c = control_deficit - 0.55
            des *= (1.0 + 0.40 * excess_c)
            if raw.prospect_status == "disconfirmed":
                self_blame -= 0.20 * excess_c

        return {
            "desirability": round(_clamp(des, -1.0, 1.0), 3),
            "blameworthiness": round(_clamp(blame, -1.0, 1.0), 3),
            "future_desirability": round(_clamp(max(0.0, fut_des), 0.0, 1.0), 3),
            "prospect_status": raw.prospect_status,
            "self_blameworthiness": round(_clamp(self_blame, -1.0, 1.0), 3),
            "other_desirability": round(_clamp(raw.other_desirability, -1.0, 1.0), 3),
            "other_relationship": round(_clamp(raw.other_relationship, -1.0, 1.0), 3),
            "appealingness": round(_clamp(appealing, -1.0, 1.0), 3),
        }

    # --------------------------------------------------------------------------
    # Prompt 辅助片段渲染与全状态持久化
    # --------------------------------------------------------------------------
    def render_autonomous_agenda_prompt(self) -> str:
        """
        生成可直接拼接进下游 System Prompt 的【内生动机与当前自我议程】指令片段，
        赋予数字人在回复中主动夹带私货、表达疲惫或追问好奇议题的自主灵魂。
        """
        snap = self.motive_tank.snapshot()
        dom_plan = (
            self.plan_tree.nodes.get(self.plan_tree.dominant_plan_id)
            if self.plan_tree.dominant_plan_id else None
        )
        lines = [
            "### ENDOGENOUS PSI DRIVES & AUTONOMOUS AGENDA (内生动机槽与当前自我目标)",
            f"- Dominant Inner Need: {snap['dominant_drive']} (Urgency={snap['dominant_urgency']})",
        ]
        for k, info in snap["drives"].items():
            flag = " [CRITICAL]" if info["is_critical"] else ""
            lines.append(f"  * {info['label']} ({k}): Tension={info['tension']}{flag}")

        if dom_plan:
            lines.extend([
                f"- Active Autonomous Goal: [{dom_plan.title}] (Progress={dom_plan.progress:.0%}, Status={dom_plan.status})",
                f"- Inner Behavioural Agenda: {dom_plan.proactive_impulse}",
            ])
        else:
            lines.append("- Active Autonomous Goal: Homeostatic equilibrium (No urgent unfulfilled agenda)")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "motive_tank": self.motive_tank.to_dict(),
            "plan_tree": self.plan_tree.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], llm_client: Any = None, enable_llm: bool = True) -> "CognitiveAppraiser":
        instance = cls(
            model_name=data.get("model_name", "gpt-4o-mini"),
            llm_client=llm_client,
            enable_llm=enable_llm,
        )
        if "motive_tank" in data:
            instance.motive_tank = PSIMotiveTank.from_dict(data["motive_tank"])
        if "plan_tree" in data:
            instance.plan_tree = AutonomousPlanTree.from_dict(data["plan_tree"])
        return instance


# ==============================================================================
# 5. 本地自包含仿真演示 (验证静默动机演化 -> 自我目标树萌芽 -> 评估与满足闭环)
# ==============================================================================
if __name__ == "__main__":
    # 初始化一个高外倾、高开放性的数字人自主认知评估器（离线规则模式验证纯状态机闭环）
    appraiser = CognitiveAppraiser(
        ocean={"O": 0.85, "C": 0.70, "E": 0.82, "A": 0.75, "N": 0.35},
        enable_llm=False,
    )

    print("=== [1. 模拟长达 6 小时无人理睬的静默期] ===")
    idle_report = appraiser.tick_idle_and_propose(elapsed_minutes=360)
    print("主导驱动力:", idle_report["dominant_drive"], "| 紧迫度:", idle_report["dominant_urgency"])
    print("是否想主动找用户说话:", idle_report["should_initiate_chat"])
    print("自我目标树萌发的主导开场意图:", idle_report["proactive_opening_hint"])

    print("\n=== [2. 用户发来温暖陪伴与技术破局好消息] ===")
    occ_vector = appraiser.appraise(
        user_input="忙完啦，专门过来陪你聊聊！刚才那个卡住的死锁问题也彻底解决了！",
        user_plans=[{"plan_id": "u_01", "title": "攻克线上并发死锁", "importance": 0.9}],
        elapsed_minutes=5,
    )
    print("输出的兼容 8 维 OCC 评估字典:", occ_vector)
    print("\n=== [3. 渲染注入下游的自主议程 Prompt 片段] ===")
    print(appraiser.render_autonomous_agenda_prompt())
