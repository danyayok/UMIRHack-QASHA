import pytest
from datetime import datetime
from app.schemas_agent import AgentMeta, AgentPayload, AgentReportCreate, AgentReportOut

class TestAgentMeta:
    def test_valid_agent_meta(self):
        data = {
            "hostname": "test-host",
            "timestamp": datetime(2023, 1, 1, 12, 0, 0),
            "duration_seconds": 42.5
        }
        meta = AgentMeta(**data)
        assert meta.hostname == "test-host"
        assert meta.timestamp == datetime(2023, 1, 1, 12, 0, 0)
        assert meta.duration_seconds == 42.5

    @pytest.mark.parametrize("hostname,duration", [
        (None, None),
        ("host", 10.0),
        ("", 0.0)
    ])
    def test_optional_fields(self, hostname, duration):
        data = {
            "hostname": hostname,
            "timestamp": datetime.now(),
            "duration_seconds": duration
        }
        meta = AgentMeta(**data)
        assert meta.hostname == hostname
        assert meta.duration_seconds == duration

class TestAgentPayload:
    def test_valid_payload(self):
        data = {
            "performance": {"metric": 99},
            "fuzz": [1, 2, 3],
            "concurrency": None,
            "static_metrics": "test",
            "artifacts": {}
        }
        payload = AgentPayload(**data)
        assert payload.performance == {"metric": 99}
        assert payload.fuzz == [1, 2, 3]
        assert payload.concurrency is None
        assert payload.static_metrics == "test"
        assert payload.artifacts == {}

    def test_empty_payload(self):
        payload = AgentPayload()
        assert payload.performance is None
        assert payload.fuzz is None
        assert payload.concurrency is None
        assert payload.static_metrics is None
        assert payload.artifacts is None

class TestAgentReportCreate:
    def test_valid_report_create(self):
        meta = AgentMeta(
            hostname="host",
            timestamp=datetime(2023, 1, 1),
            duration_seconds=10.0
        )
        payload = AgentPayload(performance={"cpu": 50})
        report = AgentReportCreate(
            agent_name="test_agent",
            project_id=1,
            run_id="run_123",
            meta=meta,
            payload=payload
        )
        assert report.agent_name == "test_agent"
        assert report.project_id == 1
        assert report.run_id == "run_123"
        assert report.meta == meta
        assert report.payload == payload

    def test_required_agent_name(self):
        meta = AgentMeta(timestamp=datetime(2023, 1, 1))
        payload = AgentPayload()
        with pytest.raises(ValueError):
            AgentReportCreate(agent_name=None, meta=meta, payload=payload)

class TestAgentReportOut:
    def test_valid_report_out(self):
        report = AgentReportOut(
            id=1,
            agent_id=2,
            project_id=3,
            run_id="run_456",
            short_summary="Test summary",
            created_at=datetime(2023, 1, 1, 12, 0, 0)
        )
        assert report.id == 1
        assert report.agent_id == 2
        assert report.project_id == 3
        assert report.run_id == "run_456"
        assert report.short_summary == "Test summary"
        assert report.created_at == datetime(2023, 1, 1, 12, 0, 0)

    def test_optional_fields_out(self):
        report = AgentReportOut(
            id=1,
            agent_id=2,
            created_at=datetime(2023, 1, 1)
        )
        assert report.project_id is None
        assert report.run_id is None
        assert report.short_summary is None