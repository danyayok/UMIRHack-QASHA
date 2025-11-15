import pytest
from pydantic import ValidationError
from datetime import datetime
from app.schemas import (
    UserCreate, UserOut, Token, ProjectCreate, ProjectOut, AnalysisCreate,
    AnalysisOut, AnalysisStatus, AgentCreate, AgentOut, AgentMeta,
    PerformanceMetrics, FuzzResults, StaticMetrics, Artifacts, AgentPayload,
    AgentReportCreate, AgentReportOut, TestRunBase, TestRunCreate, TestRunOut,
    TestBatchBase, TestBatchCreate, TestBatchOut, GeneratedTestBase,
    GeneratedTestCreate, GeneratedTestOut, TestBatchWithTests,
    TestGenerationResult, TestCaseStepBase, TestCaseBase, TestCaseCreate,
    TestCaseOut, TestCaseFileBase, TestCaseFileCreate, TestCaseFileOut,
    TestGenerationConfig, TestCaseGenerationConfig, TestGenerationWithCasesConfig,
    TestCaseParsingConfig
)

@pytest.fixture
def user_create_data():
    return {
        "email": "test@example.com",
        "password": "securepassword",
        "full_name": "Test User"
    }

@pytest.fixture
def user_out_data():
    return {
        "id": 1,
        "email": "test@example.com",
        "full_name": "Test User",
        "is_active": True,
        "created_at": datetime.now()
    }

@pytest.fixture
def token_data():
    return {
        "access_token": "sample_token",
        "token_type": "bearer"
    }

@pytest.fixture
def project_create_data():
    return {
        "name": "Test Project",
        "description": "A test project",
        "repo_url": "https://github.com/test/test-project",
        "branch": "main",
        "technology_stack": ["python", "fastapi"]
    }

@pytest.fixture
def project_out_data():
    return {
        "id": 1,
        "name": "Test Project",
        "description": "A test project",
        "repo_url": "https://github.com/test/test-project",
        "branch": "main",
        "technology_stack": ["python", "fastapi"],
        "test_framework": "pytest",
        "owner_id": 1,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "coverage": 85.5
    }

@pytest.fixture
def analysis_create_data():
    return {
        "project_id": 1,
        "generate_tests": True,
        "push_to_repo": False,
        "branch_name": "qa-autopilot-tests"
    }

@pytest.fixture
def agent_create_data():
    return {
        "name": "Test Agent",
        "description": "A test agent",
        "capabilities": ["code_analysis", "test_generation"]
    }

@pytest.fixture
def agent_out_data():
    return {
        "id": 1,
        "name": "Test Agent",
        "description": "A test agent",
        "owner_id": 1,
        "is_active": True,
        "capabilities": ["code_analysis", "test_generation"],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }

@pytest.fixture
def agent_meta_data():
    return {
        "hostname": "test-host",
        "timestamp": datetime.now(),
        "duration_seconds": 120.5
    }

@pytest.fixture
def agent_payload_data():
    return {
        "performance": PerformanceMetrics(functions=[{"name": "func1", "time": 0.1}]),
        "fuzz": FuzzResults(issues_found=[{"type": "memory_leak", "severity": "high"}]),
        "concurrency": {"max_threads": 10},
        "static_metrics": StaticMetrics(complexity={"func1": 5}),
        "artifacts": Artifacts(logs=["log1", "log2"])
    }

@pytest.fixture
def agent_report_create_data(agent_meta_data, agent_payload_data):
    return {
        "agent_name": "TestAgent",
        "project_id": 1,
        "run_id": "run_123",
        "meta": agent_meta_data,
        "payload": agent_payload_data
    }

@pytest.fixture
def test_run_base_data():
    return {
        "project_id": 1,
        "analysis_id": 1,
        "status": "completed",
        "results": {"passed": 10, "failed": 2},
        "coverage": 90.0,
        "duration": 120.0
    }

@pytest.fixture
def test_batch_base_data():
    return {
        "name": "Batch 1",
        "description": "First test batch",
        "framework": "pytest",
        "ai_provider": "openai",
        "coverage_improvement": 10.0,
        "total_tests": 50,
        "config": {"parallel": True}
    }

@pytest.fixture
def generated_test_base_data():
    return {
        "name": "test_example",
        "file_path": "/tests/test_example.py",
        "test_type": "unit",
        "framework": "pytest",
        "content": "def test_example(): pass",
        "target_file": "/src/example.py",
        "priority": "high",
        "ai_provider": "openai",
        "coverage_estimate": 5.0
    }

@pytest.fixture
def test_case_step_base_data():
    return {
        "step_number": 1,
        "action": "Open application",
        "expected_result": "Application opens successfully",
        "data": {"url": "http://example.com"}
    }

@pytest.fixture
def test_case_base_data(test_case_step_base_data):
    return {
        "name": "TC001",
        "description": "Test case for login",
        "test_case_id": "TC001",
        "priority": "high",
        "test_type": "functional",
        "preconditions": "User exists",
        "postconditions": "User logged in",
        "steps": [test_case_step_base_data]
    }

@pytest.fixture
def test_case_file_base_data():
    return {
        "filename": "test_cases.xlsx",
        "original_filename": "TestCases.xlsx",
        "file_format": "xlsx",
        "file_size": 1024
    }

@pytest.fixture
def test_generation_config_data():
    return {
        "generate_unit_tests": True,
        "generate_api_tests": True,
        "generate_integration_tests": True,
        "generate_e2e_tests": False,
        "max_unit_tests": 10,
        "max_api_tests": 10,
        "max_integration_tests": 5,
        "max_e2e_tests": 2,
        "framework": "pytest",
        "test_style": "descriptive",
        "include_comments": True,
        "include_assertions": True,
        "coverage_target": 80.0
    }

@pytest.fixture
def test_case_generation_config_data():
    return {
        "generate_test_cases": True,
        "test_case_format": "excel",
        "test_case_level": "detailed",
        "include_test_steps": True,
        "include_expected_results": True,
        "include_ui_interactions": True,
        "test_case_template": "standard"
    }

def test_user_create_valid(user_create_data):
    user = UserCreate(**user_create_data)
    assert user.email == user_create_data["email"]
    assert user.password == user_create_data["password"]
    assert user.full_name == user_create_data["full_name"]

def test_user_create_invalid_email():
    with pytest.raises(ValidationError):
        UserCreate(email="invalid-email", password="securepassword")

def test_user_create_short_password():
    with pytest.raises(ValidationError):
        UserCreate(email="test@example.com", password="123")

def test_user_out_valid(user_out_data):
    user = UserOut(**user_out_data)
    assert user.id == user_out_data["id"]
    assert user.email == user_out_data["email"]
    assert user.is_active == user_out_data["is_active"]

def test_token_valid(token_data):
    token = Token(**token_data)
    assert token.access_token == token_data["access_token"]
    assert token.token_type == token_data["token_type"]

def test_project_create_valid(project_create_data):
    project = ProjectCreate(**project_create_data)
    assert project.name == project_create_data["name"]
    assert project.branch == project_create_data["branch"]

def test_project_create_invalid_name():
    with pytest.raises(ValidationError):
        ProjectCreate(name="", description="A test project")

def test_project_out_valid(project_out_data):
    project = ProjectOut(**project_out_data)
    assert project.id == project_out_data["id"]
    assert project.name == project_out_data["name"]
    assert project.coverage == project_out_data["coverage"]

def test_analysis_create_valid(analysis_create_data):
    analysis = AnalysisCreate(**analysis_create_data)
    assert analysis.project_id == analysis_create_data["project_id"]
    assert analysis.generate_tests == analysis_create_data["generate_tests"]
    assert analysis.branch_name == analysis_create_data["branch_name"]

def test_analysis_create_default_branch():
    analysis = AnalysisCreate(project_id=1, generate_tests=True)
    assert analysis.branch_name == "qa-autopilot-tests"

def test_agent_create_valid(agent_create_data):
    agent = AgentCreate(**agent_create_data)
    assert agent.name == agent_create_data["name"]
    assert agent.capabilities == agent_create_data["capabilities"]

def test_agent_create_invalid_name():
    with pytest.raises(ValidationError):
        AgentCreate(name="", description="A test agent")

def test_agent_out_valid(agent_out_data):
    agent = AgentOut(**agent_out_data)
    assert agent.id == agent_out_data["id"]
    assert agent.name == agent_out_data["name"]
    assert agent.is_active == agent_out_data["is_active"]

def test_agent_meta_valid(agent_meta_data):
    meta = AgentMeta(**agent_meta_data)
    assert meta.hostname == agent_meta_data["hostname"]
    assert meta.duration_seconds == agent_meta_data["duration_seconds"]

def test_agent_report_create_valid(agent_report_create_data):
    report = AgentReportCreate(**agent_report_create_data)
    assert report.agent_name == agent_report_create_data["agent_name"]
    assert report.project_id == agent_report_create_data["project_id"]

def test_agent_report_create_missing_required():
    with pytest.raises(ValidationError):
        AgentReportCreate(agent_name="")

def test_test_run_base_valid(test_run_base_data):
    run = TestRunBase(**test_run_base_data)
    assert run.project_id == test_run_base_data["project_id"]
    assert run.status == test_run_base_data["status"]
    assert run.coverage == test_run_base_data["coverage"]

def test_test_batch_base_valid(test_batch_base_data):
    batch = TestBatchBase(**test_batch_base_data)
    assert batch.name == test_batch_base_data["name"]
    assert batch.total_tests == test_batch_base_data["total_tests"]

def test_generated_test_base_valid(generated_test_base_data):
    test = GeneratedTestBase(**generated_test_base_data)
    assert test.name == generated_test_base_data["name"]
    assert test.framework == generated_test_base_data["framework"]
    assert test.priority == generated_test_base_data["priority"]

def test_test_case_step_base_valid(test_case_step_base_data):
    step = TestCaseStepBase(**test_case_step_base_data)
    assert step.step_number == test_case_step_base_data["step_number"]
    assert step.action == test_case_step_base_data["action"]

def test_test_case_base_valid(test_case_base_data):
    case = TestCaseBase(**test_case_base_data)
    assert case.name == test_case_base_data["name"]
    assert case.test_case_id == test_case_base_data["test_case_id"]
    assert case.priority == test_case_base_data["priority"]

def test_test_case_file_base_valid(test_case_file_base_data):
    file = TestCaseFileBase(**test_case_file_base_data)
    assert file.filename == test_case_file_base_data["filename"]
    assert file.file_format == test_case_file_base_data["file_format"]

def test_test_generation_config_valid(test_generation_config_data):
    config = TestGenerationConfig(**test_generation_config_data)
    assert config.generate_unit_tests == test_generation_config_data["generate_unit_tests"]
    assert config.framework == test_generation_config_data["framework"]
    assert config.coverage_target == test_generation_config_data["coverage_target"]

def test_test_generation_config_invalid_coverage():
    with pytest.raises(ValidationError):
        TestGenerationConfig(coverage_target=150.0)

def test_test_case_generation_config_valid(test_case_generation_config_data):
    config = TestCaseGenerationConfig(**test_case_generation_config_data)
    assert config.generate_test_cases == test_case_generation_config_data["generate_test_cases"]
    assert config.test_case_format == test_case_generation_config_data["test_case_format"]

def test_test_generation_with_cases_config():
    data = {
        "generate_unit_tests": True,
        "framework": "pytest",
        "test_case_config": {
            "generate_test_cases": True,
            "test_case_format": "excel"
        }
    }
    config = TestGenerationWithCasesConfig(**data)
    assert config.generate_unit_tests == data["generate_unit_tests"]
    assert config.test_case_config.generate_test_cases == data["test_case_config"]["generate_test_cases"]

def test_test_case_parsing_config():
    data = {
        "document_type": "excel",
        "sheet_name": "TestCases",
        "test_cases_column": "A",
        "expected_results_column": "B",
        "parse_comments": True,
        "generate_from_spec": True
    }
    config = TestCaseParsingConfig(**data)
    assert config.document_type == data["document_type"]
    assert config.sheet_name == data["sheet_name"]
    assert config.parse_comments == data["parse_comments"]