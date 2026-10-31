import io
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/vf_test/app.db")
os.environ.setdefault("UPLOAD_DIR", "/tmp/vf_test/uploads")
os.environ.setdefault("MAX_FILE_MB", "1")

from app.main import app


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    base = tmp_path_factory.mktemp("vf")
    os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{base / 'app.db'}")
    os.environ["UPLOAD_DIR"] = str(base / "uploads")
    from app import config

    config.settings.database_url = os.environ["DATABASE_URL"]
    config.settings.upload_dir = str(base / "uploads")
    config.settings.max_file_mb = 1
    with TestClient(app) as c:
        yield c


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.txt", "hello")
    return buf.getvalue()


def _payload(**over):
    data = {
        "brand_name": "拾光中古",
        "contact_name": "陈小姐",
        "phone": "138 0013 8000",
        "wechat": "shiguang_vtg",
        "city": "深圳",
        "entity_type": "company",
        "is_first_time": False,
        "categories": ["bag", "apparel"],
        "zones": ["A", "C"],
        "expected_qty": 180,
        "price_min": 800,
        "price_max": 28000,
        "structure": {"secondhand": 60, "new_stock": 30, "sample": 10, "replica": 0},
        "items": [
            {
                "name": "Hermès Birkin 30 金棕",
                "era_series": "2015 年 / Birkin",
                "condition_source": "二手 / 附购买凭证",
                "price": 52000,
            }
        ],
        "consent": True,
    }
    data.update(over)
    return data


def test_healthz(client):
    body = client.get("/healthz").json()
    assert body["ok"] is True
    assert "upload_dir" in body, "健康检查应带附件目录信息，方便排查挂载问题"
    assert body["upload_files"] >= 0


def test_upload_and_submit(client):
    up = client.post(
        "/api/v1/uploads",
        files={"file": ("photos.zip", _zip_bytes(), "application/zip")},
        data={"kind": "photos"},
    )
    assert up.status_code == 201, up.text
    file_id = up.json()["file_id"]

    res = client.post(
        "/api/v1/applications",
        json=_payload(file_ids=[file_id]),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["id"] >= 1
    assert body["files"] == 1


def test_phone_normalized_and_rejects_bad(client):
    ok = client.post("/api/v1/applications", json=_payload(phone="+86 139-0013-9000"))
    assert ok.status_code == 201

    bad = client.post("/api/v1/applications", json=_payload(phone="12345"))
    assert bad.status_code == 422


def test_structure_must_sum_100(client):
    res = client.post(
        "/api/v1/applications",
        json=_payload(structure={"secondhand": 50, "new_stock": 30, "sample": 10, "replica": 0}),
    )
    assert res.status_code == 422
    assert "100" in res.text


def test_need_contact_channel(client):
    res = client.post("/api/v1/applications", json=_payload(wechat=None, email=None))
    assert res.status_code == 422


def test_file_id_cannot_be_reused(client):
    up = client.post(
        "/api/v1/uploads",
        files={"file": ("a.txt", b"x", "text/plain")},
    )
    assert up.status_code == 400  # txt 不在白名单

    up = client.post(
        "/api/v1/uploads",
        files={"file": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert up.status_code == 201
    fid = up.json()["file_id"]

    first = client.post("/api/v1/applications", json=_payload(file_ids=[fid]))
    assert first.status_code == 201
    second = client.post("/api/v1/applications", json=_payload(file_ids=[fid]))
    assert second.status_code == 400


def test_oversize_rejected(client):
    big = b"0" * (2 * 1024 * 1024)
    res = client.post("/api/v1/uploads", files={"file": ("big.png", big, "image/png")})
    assert res.status_code == 413


def test_fake_zip_rejected(client):
    res = client.post("/api/v1/uploads", files={"file": ("x.zip", b"not-a-zip", "application/zip")})
    assert res.status_code == 400


# ---------------------------------------------------------------- review 补充用例


def test_structure_optional(client):
    """不传 structure 时不应 500，四个占比列存 NULL。"""
    res = client.post("/api/v1/applications", json=_payload(structure=None))
    assert res.status_code == 201, res.text

    from app import db

    row = db.fetch_one(
        "SELECT pct_secondhand, pct_new_stock FROM application WHERE id = ?",
        (res.json()["id"],),
    )
    assert row["pct_secondhand"] is None and row["pct_new_stock"] is None


def test_consent_must_be_explicit(client):
    no_field = _payload()
    no_field.pop("consent")
    assert client.post("/api/v1/applications", json=no_field).status_code == 422

    assert client.post("/api/v1/applications", json=_payload(consent=False)).status_code == 422


def test_upload_kind_whitelist(client):
    res = client.post(
        "/api/v1/uploads",
        files={"file": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        data={"kind": "随便写"},
    )
    assert res.status_code == 400


def test_zones_deduped(client):
    res = client.post("/api/v1/applications", json=_payload(zones=["A", "A", "C"]))
    assert res.status_code == 201
    from app import db

    stored = db.fetch_one("SELECT zones FROM application WHERE id = ?", (res.json()["id"],))[
        "zones"
    ]
    assert stored == '["A", "C"]'


def test_healthz_checks_db(client):
    assert client.get("/healthz").json()["ok"] is True


def test_rate_limit(client, monkeypatch):
    from app import config, main

    monkeypatch.setattr(config.settings, "rate_limit_per_minute", 2)
    main._hits.clear()

    codes = [client.post("/api/v1/applications", json=_payload()).status_code for _ in range(3)]
    assert codes == [201, 201, 429], codes

    body = client.post("/api/v1/applications", json=_payload()).json()
    assert body["error"]["code"] == "RATE_LIMITED"

    main._hits.clear()


# ---------------------------------------------------------------- v2 调研新增


def test_form_schema(client):
    """问卷结构接口：12 道新题 + D 区 + 新文案。"""
    r = client.get("/api/v1/form-schema")
    assert r.status_code == 200
    data = r.json()

    assert data["version"] == "v2"
    assert data["required_hint"] == "带 * 为必填项"

    zones = [z["value"] for z in data["zones"]]
    assert "D" in zones, "开放 D 区报名"

    questions = [q for g in data["groups"] for q in g["questions"]]
    assert len(questions) == 12
    keys = {q["key"] for q in questions}
    assert {
        "founded_year",
        "social_links",
        "brand_intro",
        "channels",
        "has_physical_store",
        "attended_other_events",
        "past_experience",
        "brand_specialty",
        "target_consumers",
        "planned_activities",
        "willing_to_promote",
        "authorize_media",
    } <= keys

    # 文案要求
    assert "2026.11.8" in data["copy"]["feedback"]
    assert "2026.11.10" in data["copy"]["feedback"]
    assert "2026.11.28" in data["copy"]["feedback"]
    assert "2026.12.1" in data["copy"]["feedback"]
    assert "增加入选概率" in data["copy"]["items_hint"]

    # 只有过往参展经历不是必填
    optional = {q["key"] for q in questions if not q["required"]}
    assert optional == {"past_experience"}


def _survey_payload():
    return {
        "founded_year": 2018,
        "social_links": ["https://instagram.com/p/abc", "https://xhslink.com/xyz"],
        "brand_intro": "这是一段用于测试的品牌简介。" * 10,  # 130 字
        "channels": ["online_store", "market_stall"],
        "has_physical_store": True,
        "attended_other_events": False,
        "past_experience": "2024 年参加过深圳湾市集",
        "brand_specialty": "专营 90 年代日本 archive。" * 10,
        "target_consumers": "vintage",
        "planned_activities": ["limited", "onsite"],
        "willing_to_promote": "provide_material",
        "authorize_media": "agree",
    }


def test_submit_with_survey_v2(client):
    """12 道新题能正常提交并落库。"""
    r = client.post("/api/v1/applications", json=_payload(zones=["D"], **_survey_payload()))
    assert r.status_code == 201, r.text
    app_id = r.json()["id"]

    from app import db

    row = db.fetch_one("SELECT * FROM application WHERE id = ?", [app_id])
    assert row["founded_year"] == 2018
    assert row["has_physical_store"] == 1
    assert row["attended_other_events"] == 0
    assert row["target_consumers"] == "vintage"
    assert row["authorize_media"] == "agree"
    import json as _json

    assert _json.loads(row["social_links"])[0].startswith("https://")
    assert _json.loads(row["channels"]) == ["online_store", "market_stall"]
    assert _json.loads(row["zones"]) == ["D"]


def test_survey_validation(client):
    """新字段的校验规则。"""
    # 品牌简介不足 100 字
    r = client.post("/api/v1/applications", json=_payload(brand_intro="太短了"))
    assert r.status_code == 422

    # 链接格式不对
    r = client.post("/api/v1/applications", json=_payload(social_links=["instagram.com/abc"]))
    assert r.status_code == 422

    # 「没有特别安排」不能与其他同时选
    r = client.post(
        "/api/v1/applications",
        json=_payload(planned_activities=["none", "limited"]),
    )
    assert r.status_code == 422

    # 年份越界
    r = client.post("/api/v1/applications", json=_payload(founded_year=1800))
    assert r.status_code == 422


def test_survey_backward_compatible(client):
    """不传新字段也要能提交（前端未上线前的兼容）。"""
    r = client.post("/api/v1/applications", json=_payload())
    assert r.status_code == 201, r.text

    from app import db

    row = db.fetch_one("SELECT * FROM application WHERE id = ?", [r.json()["id"]])
    assert row["founded_year"] is None
    assert row["brand_intro"] is None


def test_survey_strict_mode(client, monkeypatch):
    """SURVEY_REQUIRED=1 时缺项直接 422，并指出缺了哪些。"""
    from app import config

    monkeypatch.setattr(config.settings, "survey_required", True)
    r = client.post("/api/v1/applications", json=_payload())
    assert r.status_code == 422
    assert "必填项未填写" in r.text

    r = client.post("/api/v1/applications", json=_payload(**_survey_payload()))
    assert r.status_code == 201, r.text
