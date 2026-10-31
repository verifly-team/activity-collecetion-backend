"""请求 / 响应模型 + 校验。"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import settings

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

CATEGORIES = {
    "bag": "箱包手袋",
    "watch": "腕表",
    "jewelry": "珠宝配饰",
    "apparel": "服饰",
    "shoe": "鞋履",
    "other": "其他藏品",
}
ZONES = {
    "A": "收藏级 Archive",
    "B": "工装与街头",
    "C": "二手名牌／样衣",
    "D": "D 区（新增开放）",
}

# 品牌背景与经营情况 —— 本次调研新增
CHANNELS = {
    "online_store": "线上店铺",
    "physical_store": "线下实体店",
    "personal_social": "个人社交媒体",
    "market_stall": "市集摆摊",
    "multi_channel": "多渠道经营",
}
TARGET_CONSUMERS = {
    "vintage": "Vintage／古着爱好者",
    "street": "潮流及街头文化消费者",
    "designer": "Designer／奢侈品消费者",
    "young": "年轻消费群体",
    "collector": "收藏爱好者",
    "other": "其他",
}
PLANNED_ACTIVITIES = {
    "limited": "限量商品",
    "first_release": "首次公开发售",
    "discount": "特别折扣",
    "collab": "品牌联名",
    "onsite": "现场互动活动",
    "pr_license": "品牌合作及宣传授权",
    "none": "没有特别安排",
}
PROMOTE_OPTIONS = {
    "provide_material": (
        "愿意提供品牌照片及商品素材；配合品牌介绍及社交媒体宣传；转发官方活动宣传"
    ),
    "need_talk": "希望主办方与我们进一步沟通",
}
MEDIA_AUTH = {
    "agree": "同意",
    "need_scope": "需要另行确认授权范围",
}


def normalize_phone(v: Any) -> str:
    s = re.sub(r"[\s\-－()（）]", "", str(v or ""))
    if s.startswith("+86"):
        s = s[3:]
    elif s.startswith("86") and len(s) == 13:
        s = s[2:]
    return s


class ItemIn(BaseModel):
    """代表商品一行。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120, description="商品及品牌")
    era_series: str | None = Field(None, max_length=200, description="年代／系列或库存属性")
    condition_source: str | None = Field(None, max_length=200, description="状态及来源")
    price: int | None = Field(None, ge=0, le=100_000_000, description="拟售价 元")


class StructureIn(BaseModel):
    """商品结构占比，四项合计 100。"""

    model_config = ConfigDict(extra="forbid")

    secondhand: int = Field(0, ge=0, le=100, description="二手 %")
    new_stock: int = Field(0, ge=0, le=100, description="未使用库存 %")
    sample: int = Field(0, ge=0, le=100, description="样衣 %")
    replica: int = Field(0, ge=0, le=100, description="复刻／原创 %")

    @model_validator(mode="after")
    def _sum(self) -> StructureIn:
        total = self.secondhand + self.new_stock + self.sample + self.replica
        if total != 100:
            raise ValueError(f"商品结构四项合计须为 100%，当前 {total}%")
        return self


class ApplicationIn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "brand_name": "拾光中古",
                "contact_name": "陈小姐",
                "phone": "13800138000",
                "wechat": "shiguang_vtg",
                "email": None,
                "city": "深圳",
                "entity_type": "company",
                "is_first_time": False,
                "categories": ["bag", "apparel"],
                "zones": ["A", "C"],
                "expected_qty": 180,
                "price_min": 800,
                "price_max": 28000,
                "structure": {
                    "secondhand": 60,
                    "new_stock": 30,
                    "sample": 10,
                    "replica": 0,
                },
                "items": [
                    {
                        "name": "Hermès Birkin 30 金棕",
                        "era_series": "2015 年 / Birkin",
                        "condition_source": "二手 / 附购买凭证",
                        "price": 52000,
                    }
                ],
                "file_ids": ["3f2a1c9b0d4e4f7a8b6c5d4e3f2a1b0c"],
                "consent": True,
                "source": "h5",
            }
        },
    )

    # 品牌与联络
    brand_name: str = Field(min_length=1, max_length=120, description="品牌／店铺名称")
    contact_name: str = Field(min_length=1, max_length=60, description="联系人")
    phone: str = Field(description="手机号")
    wechat: str | None = Field(None, max_length=60, description="微信")
    email: str | None = Field(None, max_length=120, description="邮箱")
    city: str | None = Field(None, max_length=60, description="所在城市")
    entity_type: Literal["company", "individual", "personal"] | None = Field(
        None, description="公司／个体工商户／个人"
    )
    is_first_time: bool = Field(False, description="首次参展")

    # 经营与参展内容
    categories: list[Literal["bag", "watch", "jewelry", "apparel", "shoe", "other"]] = Field(
        min_length=1, description="经营品类，多选"
    )
    zones: list[Literal["A", "B", "C", "D"]] = Field(min_length=1, description="意向区域，多选")
    expected_qty: int | None = Field(None, ge=0, le=1_000_000, description="预计带货件数")
    price_min: int | None = Field(None, ge=0, le=100_000_000, description="价格区间下限")
    price_max: int | None = Field(None, ge=0, le=100_000_000, description="价格区间上限")
    structure: StructureIn | None = Field(None, description="商品结构占比")
    items: list[ItemIn] = Field(default_factory=list, max_length=20, description="代表商品 3~5 件")

    # ---- 品牌背景与经营情况（本次调研新增，见 SURVEY_REQUIRED 开关） ----
    founded_year: int | None = Field(None, ge=1900, le=2100, description="品牌成立年份")
    social_links: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Instagram／小红书／抖音 链接，可多填",
    )
    brand_intro: str | None = Field(None, description="品牌简介（100–300 字）")
    channels: list[
        Literal[
            "online_store", "physical_store", "personal_social", "market_stall", "multi_channel"
        ]
    ] = Field(default_factory=list, description="主要经营渠道，多选")
    has_physical_store: bool | None = Field(None, description="是否有实体店")
    attended_other_events: bool | None = Field(None, description="是否参加过其他市集或展会")
    past_experience: str | None = Field(None, max_length=1000, description="过往参展经历")

    # ---- 品牌定位与特色 ----
    brand_specialty: str | None = Field(None, description="品牌最有特色的地方（100–300 字）")
    target_consumers: (
        Literal["vintage", "street", "designer", "young", "collector", "other"] | None
    ) = Field(None, description="主要面向的消费者，单选")
    planned_activities: list[
        Literal["limited", "first_release", "discount", "collab", "onsite", "pr_license", "none"]
    ] = Field(default_factory=list, description="本次特别商品或活动，多选")

    # ---- 品牌意愿与授权 ----
    willing_to_promote: Literal["provide_material", "need_talk"] | None = Field(
        None, description="是否愿意配合活动前品牌宣传，单选"
    )
    authorize_media: Literal["agree", "need_scope"] | None = Field(
        None, description="是否同意在宣传与回顾中使用品牌素材，单选"
    )

    # 附件与合规
    file_ids: list[str] = Field(
        default_factory=list, max_length=20, description="先上传拿到的 file_id"
    )
    consent: bool = Field(..., description="同意资料用于本次活动审核（必须显式为 true）")
    source: str | None = Field(None, max_length=30, description="h5 / qrcode / word")

    @field_validator("zones")
    @classmethod
    def _dedupe_zones(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        s = normalize_phone(v)
        if not PHONE_RE.match(s):
            raise ValueError("请填写有效的 11 位手机号")
        return s

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if v and not EMAIL_RE.match(v):
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("social_links")
    @classmethod
    def _social_links(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for raw in v:
            link = (raw or "").strip()
            if not link:
                continue
            if not re.match(r"^https?://\S+$", link):
                raise ValueError(f"链接需以 http:// 或 https:// 开头：{link[:40]}")
            out.append(link)
        return list(dict.fromkeys(out))

    @field_validator("brand_intro", "brand_specialty", "past_experience")
    @classmethod
    def _strip_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("wechat", "city", "brand_name", "contact_name")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _checks(self) -> ApplicationIn:
        if not self.email and not self.wechat:
            raise ValueError("微信与邮箱至少填写一项")
        if not self.consent:
            raise ValueError("必须同意资料用于本次活动审核")
        if (
            self.price_min is not None
            and self.price_max is not None
            and self.price_max < self.price_min
        ):
            raise ValueError("价格区间上限不能小于下限")

        # 长文本题：填了就必须 100–300 字
        for label, value in (
            ("品牌简介", self.brand_intro),
            ("品牌最有特色的地方", self.brand_specialty),
        ):
            if value and not (100 <= len(value) <= 300):
                raise ValueError(f"{label}需 100–300 字，当前 {len(value)} 字")

        # 互斥选项：选了「没有特别安排」就不能再选别的
        if "none" in self.planned_activities and len(self.planned_activities) > 1:
            raise ValueError("「没有特别安排」不能与其他选项同时选择")

        if settings.survey_required:
            missing = [
                label
                for label, ok in (
                    ("品牌成立年份", self.founded_year is not None),
                    ("社交平台链接", bool(self.social_links)),
                    ("品牌简介", bool(self.brand_intro)),
                    ("主要经营渠道", bool(self.channels)),
                    ("是否有实体店", self.has_physical_store is not None),
                    ("是否参加过其他市集或展会", self.attended_other_events is not None),
                    ("品牌最有特色的地方", bool(self.brand_specialty)),
                    ("主要面向的消费者", self.target_consumers is not None),
                    ("特别商品或活动", bool(self.planned_activities)),
                    ("是否配合品牌宣传", self.willing_to_promote is not None),
                    ("是否授权使用素材", self.authorize_media is not None),
                )
                if not ok
            ]
            if missing:
                raise ValueError("以下必填项未填写：" + "、".join(missing))
        return self

    def to_row(self, privacy_version: str, consent_at: str) -> dict[str, Any]:
        s = self.structure
        return {
            "created_at": consent_at,
            "brand_name": self.brand_name,
            "contact_name": self.contact_name,
            "phone": self.phone,
            "wechat": self.wechat,
            "email": self.email,
            "city": self.city,
            "entity_type": self.entity_type,
            "is_first_time": int(bool(self.is_first_time)),
            "categories": json.dumps(self.categories, ensure_ascii=False),
            "zones": json.dumps(self.zones, ensure_ascii=False),
            "expected_qty": self.expected_qty,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "pct_secondhand": s.secondhand if s else None,
            "pct_new_stock": s.new_stock if s else None,
            "pct_sample": s.sample if s else None,
            "pct_replica": s.replica if s else None,
            "items_json": json.dumps([i.model_dump() for i in self.items], ensure_ascii=False),
            "founded_year": self.founded_year,
            "social_links": json.dumps(self.social_links, ensure_ascii=False),
            "brand_intro": self.brand_intro,
            "channels": json.dumps(self.channels, ensure_ascii=False),
            "has_physical_store": (
                None if self.has_physical_store is None else int(self.has_physical_store)
            ),
            "attended_other_events": (
                None if self.attended_other_events is None else int(self.attended_other_events)
            ),
            "past_experience": self.past_experience,
            "brand_specialty": self.brand_specialty,
            "target_consumers": self.target_consumers,
            "planned_activities": json.dumps(self.planned_activities, ensure_ascii=False),
            "willing_to_promote": self.willing_to_promote,
            "authorize_media": self.authorize_media,
            "consent_at": consent_at,
            "privacy_version": privacy_version,
            "source": self.source or "h5",
        }


class UploadResult(BaseModel):
    file_id: str
    original_name: str
    size: int
    kind: str | None = None


class SubmitResult(BaseModel):
    id: int
    files: int
    created_at: str
