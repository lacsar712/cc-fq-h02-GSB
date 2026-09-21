"""提交权限测例：auditor 创建被拒（403），bioops 创建成功（201）。

用 SQLite 内存库 + dependency override 隔离，不需要 Postgres。
TestClient 会等 BackgroundTasks 执行完，因此 bioops 创建后流水线已跑完。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api as api_module
from app.database import Base, get_db
from app.main import app

GOOD_FASTQ = """@SEQ1
ACGTACGT
+
IIIIHHHH
@SEQ2
NNNNACGT
+
IIIIIIII
"""


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # 后台任务经 api.SessionLocal 直连数据库，指到同一个测试库
    monkeypatch.setattr(api_module, "SessionLocal", TestingSessionLocal)
    # 不用 with 语法，避免 lifespan 去连仓库配置的 Postgres
    yield TestClient(app)
    app.dependency_overrides.clear()


def _login(client, username, password):
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_auditor_create_job_forbidden(client):
    headers = _login(client, "auditor", "audit123456")
    resp = client.post("/api/jobs", json={"fastqText": GOOD_FASTQ}, headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "仅运维账号可提交质控作业"
    # 直调被拒后不应有任何作业落库
    assert client.get("/api/jobs", headers=headers).json() == []


def test_bioops_create_job_succeeds(client):
    headers = _login(client, "bioops", "fastq123456")
    resp = client.post("/api/jobs", json={"fastqText": GOOD_FASTQ}, headers=headers)
    assert resp.status_code == 201, resp.text
    job = resp.json()
    assert job["created_by"] == "bioops"
    assert [s["actor_name"] for s in job["stages"]] == [
        "ParseActor",
        "QualityHistActor",
        "NContentActor",
        "ReportActor",
    ]

    # TestClient 会等 BackgroundTasks 跑完，再查详情应已跑完流水线
    detail = client.get(f"/api/jobs/{job['id']}", headers=headers).json()
    assert detail["status"] == "success"
    assert detail["metrics"]["reads"] == 2
    assert detail["metrics"]["mean_quality"] > 0
    assert all(s["status"] == "success" for s in detail["stages"])


def test_create_job_requires_login(client):
    resp = client.post("/api/jobs", json={"fastqText": GOOD_FASTQ})
    assert resp.status_code == 401
