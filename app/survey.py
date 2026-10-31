"""问卷结构（v2 调研新增内容）—— 给前端渲染用，前后端只有这一份定义。

调整依据：Survey调整内容.docx
  · 开放 D 区报名
  · 招募截止时间与统一回复时间的文案
  · 代表商品表格下的补充说明
  · 新增「品牌背景与经营情况」三大组共 12 道题
"""

from __future__ import annotations

from .config import settings
from .models import (
    CHANNELS,
    MEDIA_AUTH,
    PLANNED_ACTIVITIES,
    PROMOTE_OPTIONS,
    TARGET_CONSUMERS,
    ZONES,
)

FEEDBACK_COPY = (
    "提交后，主办方将在 48 小时内反馈审核结果或补充资料需求。"
    "2026.11.8 为第一轮公开招募截止时间，统一回复时间为 2026.11.10；"
    "2026.11.28 为最终轮公开招募截止时间，统一回复时间为 2026.12.1。"
)

ITEMS_HINT = "添加代表商品可增加店家品牌力，显示商家独特性，会增加入选概率"


def _options(mapping: dict[str, str]) -> list[dict[str, str]]:
    return [{"value": k, "label": v} for k, v in mapping.items()]


GROUPS: list[dict] = [
    {
        "title": "1. 品牌联络与定位特色",
        "questions": [
            {
                "key": "founded_year",
                "label": "品牌成立年份",
                "type": "year",
                "required": True,
                "min": 1900,
                "max": 2100,
                "help": "填四位年份，例如 2018",
            },
            {
                "key": "social_links",
                "label": "Instagram / 小红书 / 抖音",
                "type": "url_list",
                "required": True,
                "min_items": 1,
                "max_items": 5,
                "placeholder": "https://...",
                "help": "可多填，需以 http:// 或 https:// 开头",
            },
            {
                "key": "brand_intro",
                "label": "品牌简介",
                "type": "textarea",
                "required": True,
                "min_length": 100,
                "max_length": 300,
                "help": "100–300 字",
            },
            {
                "key": "channels",
                "label": "主要经营渠道",
                "type": "multi",
                "required": True,
                "min_items": 1,
                "options": _options(CHANNELS),
            },
            {
                "key": "has_physical_store",
                "label": "是否有实体店？",
                "type": "bool",
                "required": True,
                "options": [
                    {"value": True, "label": "有"},
                    {"value": False, "label": "没有"},
                ],
            },
            {
                "key": "attended_other_events",
                "label": "是否参加过其他市集或展会？",
                "type": "bool",
                "required": True,
                "options": [
                    {"value": True, "label": "有"},
                    {"value": False, "label": "没有"},
                ],
            },
            {
                "key": "past_experience",
                "label": "过往参展经历",
                "type": "textarea",
                "required": False,
                "max_length": 1000,
                "help": "选填，简单描述参加过哪些市集或展会",
            },
        ],
    },
    {
        "title": "2. 品牌定位与特色",
        "questions": [
            {
                "key": "brand_specialty",
                "label": "你认为自己的品牌最有特色的地方是什么？",
                "type": "textarea",
                "required": True,
                "min_length": 100,
                "max_length": 300,
                "help": "100–300 字",
            },
            {
                "key": "target_consumers",
                "label": "你的品牌主要面向哪一类消费者？",
                "type": "single",
                "required": True,
                "options": _options(TARGET_CONSUMERS),
            },
            {
                "key": "planned_activities",
                "label": "本次是否有计划推出特别商品或活动？",
                "type": "multi",
                "required": True,
                "min_items": 1,
                "options": _options(PLANNED_ACTIVITIES),
                "help": "选「没有特别安排」时不能再选其他",
            },
        ],
    },
    {
        "title": "3. 品牌意愿与授权",
        "questions": [
            {
                "key": "willing_to_promote",
                "label": "是否愿意配合主办方进行活动前的品牌宣传？",
                "type": "single",
                "required": True,
                "options": _options(PROMOTE_OPTIONS),
            },
            {
                "key": "authorize_media",
                "label": (
                    "是否同意主办方在活动宣传及回顾中使用品牌提供的照片、商品图片及品牌名称？"
                ),
                "type": "single",
                "required": True,
                "options": _options(MEDIA_AUTH),
            },
        ],
    },
]


def schema() -> dict:
    """返回完整问卷结构。前端 GET /api/v1/form-schema 直接渲染即可。"""
    return {
        "version": "v2",
        "enforced": settings.survey_required,
        "required_hint": "带 * 为必填项",
        "copy": {
            "feedback": FEEDBACK_COPY,
            "items_hint": ITEMS_HINT,
        },
        "zones": _options(ZONES),
        "groups": GROUPS,
    }


__all__ = ["FEEDBACK_COPY", "GROUPS", "ITEMS_HINT", "schema"]
