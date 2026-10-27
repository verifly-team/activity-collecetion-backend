import io
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_PATH", "/tmp/vf_test/app.db")
os.environ.setdefault("UPLOAD_DIR", "/tmp/vf_test/uploads")
os.environ.setdefault("MAX_FILE_MB", "1")

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    base = tmp_path_factory.mktemp("vf")
    os.environ["DATABASE_PATH"] = str(base / "app.db")
    os.environ["UPLOAD_DIR"] = str(base / "uploads")
    from app import config

    config.settings.database_path = str(base / "app.db")
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
    assert client.get("/healthz").json() == {"ok": True}


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
