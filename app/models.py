"""请求 / 响应模型 + 校验。"""
from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
ZONES = {"A": "收藏级 Archive", "B": "工装与街头", "C": "二手名牌／样衣"}


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
    def _sum(self) -> "StructureIn":
        total = self.secondhand + self.new_stock + self.sample + self.replica
        if total != 100:
            raise ValueError(f"商品结构四项合计须为 100%，当前 {total}%")
        return self


class ApplicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    zones: list[Literal["A", "B", "C"]] = Field(min_length=1, description="意向区域，多选")
    expected_qty: int | None = Field(None, ge=0, le=1_000_000, description="预计带货件数")
    price_min: int | None = Field(None, ge=0, le=100_000_000, description="价格区间下限")
    price_max: int | None = Field(None, ge=0, le=100_000_000, description="价格区间上限")
    structure: StructureIn | None = Field(None, description="商品结构占比")
    items: list[ItemIn] = Field(default_factory=list, max_length=20, description="代表商品 3~5 件")

    # 附件与合规
    file_ids: list[str] = Field(default_factory=list, max_length=20, description="先上传拿到的 file_id")
    consent: bool = Field(True, description="同意资料用于本次活动审核")
    source: str | None = Field(None, max_length=30, description="h5 / qrcode / word")

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

    @field_validator("wechat", "city", "brand_name", "contact_name")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _checks(self) -> "ApplicationIn":
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
        return self

    def to_row(self, privacy_version: str, consent_at: str) -> dict[str, Any]:
        s = self.structure or StructureIn()
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
            "pct_secondhand": s.secondhand,
            "pct_new_stock": s.new_stock,
            "pct_sample": s.sample,
            "pct_replica": s.replica,
            "items_json": json.dumps([i.model_dump() for i in self.items], ensure_ascii=False),
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
