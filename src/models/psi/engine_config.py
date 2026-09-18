from typing import Tuple
from pydantic import BaseModel, Field

class TraitRangeConfig(BaseModel):
    # 基础 4 轴 8 种倾向的连续浮点数生成区间
    E: Tuple[float, float] = Field(default=(0.7, 0.9), description="外倾型 (Extraversion) 区间")
    I: Tuple[float, float] = Field(default=(0.1, 0.3), description="内倾型 (Introversion) 区间")

    N: Tuple[float, float] = Field(default=(0.7, 0.9), description="直觉型 (Openness) 区间")
    S: Tuple[float, float] = Field(default=(0.1, 0.3), description="感觉型 (Closedness) 区间")

    F: Tuple[float, float] = Field(default=(0.7, 0.9), description="情感型 (Agreeableness) 区间")
    T: Tuple[float, float] = Field(default=(0.1, 0.3), description="思考型 (Disagreeableness) 区间")

    J: Tuple[float, float] = Field(default=(0.7, 0.9), description="独立型 (Conscientiousness) 区间")
    P: Tuple[float, float] = Field(default=(0.1, 0.3), description="感知型 (Unconscientiousness) 区间")

    # 身份尾缀区间
    A_s: Tuple[float, float] = Field(default=(0.05, 0.25), description="自我肯定型 (Low Neuroticism) 区ain")
    T_s: Tuple[float, float] = Field(default=(0.7, 0.95), description="动荡型 (High Neuroticism) 区间")

    # 缺省兜底区间
    DEFAULT: Tuple[float, float] = Field(default=(0.4, 0.6), description="当MBTI字符非法时的中庸兜底区间")

class EngineConfig(BaseModel):
    """全局数字人情感引擎声明式配置中心"""
    mbti_ranges: TraitRangeConfig = Field(default_factory=TraitRangeConfig)