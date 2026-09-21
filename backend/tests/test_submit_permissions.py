"""创建质控作业的角色权限测例:auditor 只读被拒,bioops 可创建并跑通流水线。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import router
from app.database import Base, get_db
from app.models import Job
from app.pipeline.runner import run_pipeline_sync
from fastapi import FastAPI


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

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db

    # 端点里的 BackgroundTasks 走 SessionLocal(指向真实 Postgres),测试中禁掉,
    # 改为在测例里显式驱动流水线。
    monkeypatch.setattr("app.api._run_job_background", lambda job_id: None)

    with TestClient(app) as c:
        c._TestingSessionLocal = TestingSessionLocal  # type: ignore[attr-defined]
        yield c


def _token(client, username, password):
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200
    return resp.headers["authorization"] if "authorization" in resp.headers else (
        f"Bearer {resp.json()['access_token']}"
    )


def test_auditor_create_rejected(client):
    token = _token(client, "auditor", "audit123456")

    resp = client.post(
        "/api/jobs", json={"fastqText": GOOD_FASTQ}, headers={"Authorization": token}
    )

    assert resp.status_code == 403
    assert "运维" in resp.json()["detail"]
    assert client._TestingSessionLocal().query(Job).count() == 0


def test_anonymous_create_rejected(client):
    resp = client.post("/api/jobs", json={"fastqText": GOOD_FASTQ})
    assert resp.status_code == 401
    assert client._TestingSessionLocal().query(Job).count() == 0


def test_bioops_create_succeeds_and_runs(client):
    token = _token(client, "bioops", "fastq123456")

    resp = client.post(
        "/api/jobs", json={"fastqText": GOOD_FASTQ}, headers={"Authorization": token}
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["created_by"] == "bioops"
    job_id = data["id"]

    db = client._TestingSessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    assert job is not None
    assert job.status == "pending"

    # 运维账号触发的后台流水线本身仍可正常跑通
    run_pipeline_sync(db, job)
    assert job.status == "success"
    assert {s.status for s in job.stages if s.actor_name != "ReportActor"} or True
    assert all(s.status == "success" for s in job.stages)
    assert job.metrics["reads"] == 2
    db.close()

    # 只读账号仍可查看历史与详情
    auditor_token = _token(client, "auditor", "audit123456")
    listing = client.get("/api/jobs", headers={"Authorization": auditor_token})
    assert listing.status_code == 200
    assert any(j["id"] == job_id and j["created_by"] == "bioops" for j in listing.json())

    detail = client.get(
        f"/api/jobs/{job_id}", headers={"Authorization": auditor_token}
    )
    assert detail.status_code == 200
