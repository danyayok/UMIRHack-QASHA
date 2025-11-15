import pytest
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, JSON, Boolean, Float
from sqlalchemy.orm import relationship
from pydantic import ValidationError
from app.models import (
    TestGenerationConfig,
    TestGenerationWithCasesConfig,
    User,
    Project,
    Analysis,
    TestRun,
    Agent,
    AgentReport,
    TestBatch,
    GeneratedTest,
    TestCase,
    TestCaseFile
)
from app.db.session import Base


def test_test_generation_config_defaults():
    config = TestGenerationConfig()
    assert config.framework == "auto"
    assert config.coverage_target == 80
    assert config.generate_unit_tests is True
    assert config.generate_integration_tests is True
    assert config.generate_e2e_tests is False
    assert config.include_comments is True
    assert config.generate_documentation is False
    assert config.documentation_format == "txt"
    assert config.test_pattern == "standard"
    assert config.test_directory == ""
    assert config.custom_test_path is False


def test_test_generation_config_custom_values():
    config = TestGenerationConfig(
        framework="pytest",
        coverage_target=90,
        generate_unit_tests=False,
        generate_integration_tests=False,
        generate_e2e_tests=True,
        include_comments=False,
        generate_documentation=True,
        documentation_format="md",
        test_pattern="custom",
        test_directory="/tests",
        custom_test_path=True
    )
    assert config.framework == "pytest"
    assert config.coverage_target == 90
    assert config.generate_unit_tests is False
    assert config.generate_integration_tests is False
    assert config.generate_e2e_tests is True
    assert config.include_comments is False
    assert config.generate_documentation is True
    assert config.documentation_format == "md"
    assert config.test_pattern == "custom"
    assert config.test_directory == "/tests"
    assert config.custom_test_path is True


def test_test_generation_config_invalid_coverage():
    with pytest.raises(ValidationError):
        TestGenerationConfig(coverage_target=-1)
    with pytest.raises(ValidationError):
        TestGenerationConfig(coverage_target=101)


def test_test_generation_with_cases_config_defaults():
    config = TestGenerationWithCasesConfig()
    assert config.generate_test_cases is False
    assert config.test_case_format == "excel"
    assert config.test_case_level == "detailed"
    assert config.include_test_steps is True
    assert config.include_expected_results is True
    assert config.include_ui_interactions is True
    assert config.test_case_template == "standard"


def test_test_generation_with_cases_config_custom_values():
    config = TestGenerationWithCasesConfig(
        generate_test_cases=True,
        test_case_format="json",
        test_case_level="basic",
        include_test_steps=False,
        include_expected_results=False,
        include_ui_interactions=False,
        test_case_template="custom"
    )
    assert config.generate_test_cases is True
    assert config.test_case_format == "json"
    assert config.test_case_level == "basic"
    assert config.include_test_steps is False
    assert config.include_expected_results is False
    assert config.include_ui_interactions is False
    assert config.test_case_template == "custom"


def test_user_model_fields():
    assert hasattr(User, 'id')
    assert hasattr(User, 'email')
    assert hasattr(User, 'hashed_password')
    assert hasattr(User, 'full_name')
    assert hasattr(User, 'is_active')
    assert hasattr(User, 'created_at')
    assert hasattr(User, 'generated_tests')
    assert hasattr(User, 'projects')
    assert hasattr(User, 'agents')


def test_project_model_fields():
    assert hasattr(Project, 'id')
    assert hasattr(Project, 'name')
    assert hasattr(Project, 'description')
    assert hasattr(Project, 'repo_url')
    assert hasattr(Project, 'branch')
    assert hasattr(Project, 'technology_stack')
    assert hasattr(Project, 'test_framework')
    assert hasattr(Project, 'owner_id')
    assert hasattr(Project, 'created_at')
    assert hasattr(Project, 'updated_at')
    assert hasattr(Project, 'generated_tests')
    assert hasattr(Project, 'owner')
    assert hasattr(Project, 'analyses')
    assert hasattr(Project, 'test_runs')
    assert hasattr(Project, 'agent_reports')
    assert hasattr(Project, 'test_batches')
    assert hasattr(Project, 'test_cases')
    assert hasattr(Project, 'test_case_files')


def test_analysis_model_fields():
    assert hasattr(Analysis, 'id')
    assert hasattr(Analysis, 'project_id')
    assert hasattr(Analysis, 'status')
    assert hasattr(Analysis, 'result')
    assert hasattr(Analysis, 'generated_tests')
    assert hasattr(Analysis, 'commit_hash')
    assert hasattr(Analysis, 'branch_name')
    assert hasattr(Analysis, 'error_message')
    assert hasattr(Analysis, 'created_at')
    assert hasattr(Analysis, 'project')
    assert hasattr(Analysis, 'test_runs')


def test_test_run_model_fields():
    assert hasattr(TestRun, 'id')
    assert hasattr(TestRun, 'project_id')
    assert hasattr(TestRun, 'analysis_id')
    assert hasattr(TestRun, 'status')
    assert hasattr(TestRun, 'results')
    assert hasattr(TestRun, 'coverage')
    assert hasattr(TestRun, 'duration')
    assert hasattr(TestRun, 'created_at')
    assert hasattr(TestRun, 'project')
    assert hasattr(TestRun, 'analysis')


def test_agent_model_fields():
    assert hasattr(Agent, 'id')
    assert hasattr(Agent, 'name')
    assert hasattr(Agent, 'token')
    assert hasattr(Agent, 'description')
    assert hasattr(Agent, 'owner_id')
    assert hasattr(Agent, 'is_active')
    assert hasattr(Agent, 'capabilities')
    assert hasattr(Agent, 'created_at')
    assert hasattr(Agent, 'updated_at')
    assert hasattr(Agent, 'owner')
    assert hasattr(Agent, 'reports')


def test_agent_report_model_fields():
    assert hasattr(AgentReport, 'id')
    assert hasattr(AgentReport, 'agent_id')
    assert hasattr(AgentReport, 'project_id')
    assert hasattr(AgentReport, 'run_id')
    assert hasattr(AgentReport, 'payload')
    assert hasattr(AgentReport, 'short_summary')
    assert hasattr(AgentReport, 'severity')
    assert hasattr(AgentReport, 'created_at')
    assert hasattr(AgentReport, 'agent')
    assert hasattr(AgentReport, 'project')


def test_test_batch_model_fields():
    assert hasattr(TestBatch, 'id')
    assert hasattr(TestBatch, 'project_id')
    assert hasattr(TestBatch, 'name')
    assert hasattr(TestBatch, 'description')
    assert hasattr(TestBatch, 'status')
    assert hasattr(TestBatch, 'framework')
    assert hasattr(TestBatch, 'ai_provider')
    assert hasattr(TestBatch, 'coverage_improvement')
    assert hasattr(TestBatch, 'total_tests')
    assert hasattr(TestBatch, 'config')
    assert hasattr(TestBatch, 'created_at')
    assert hasattr(TestBatch, 'updated_at')
    assert hasattr(TestBatch, 'project')
    assert hasattr(TestBatch, 'generated_tests')
    assert hasattr(TestBatch, 'test_cases')


def test_generated_test_model_fields():
    assert hasattr(GeneratedTest, 'id')
    assert hasattr(GeneratedTest, 'project_id')
    assert hasattr(GeneratedTest, 'test_batch_id')
    assert hasattr(GeneratedTest, 'name')
    assert hasattr(GeneratedTest, 'file_path')
    assert hasattr(GeneratedTest, 'test_type')
    assert hasattr(GeneratedTest, 'framework')
    assert hasattr(GeneratedTest, 'content')
    assert hasattr(GeneratedTest, 'target_file')
    assert hasattr(GeneratedTest, 'priority')
    assert hasattr(GeneratedTest, 'generated_by')
    assert hasattr(GeneratedTest, 'ai_provider')
    assert hasattr(GeneratedTest, 'coverage_estimate')
    assert hasattr(GeneratedTest, 'created_at')
    assert hasattr(GeneratedTest, 'project')
    assert hasattr(GeneratedTest, 'user')
    assert hasattr(GeneratedTest, 'test_batch')


def test_test_case_model_fields():
    assert hasattr(TestCase, 'id')
    assert hasattr(TestCase, 'project_id')
    assert hasattr(TestCase, 'test_batch_id')
    assert hasattr(TestCase, 'name')
    assert hasattr(TestCase, 'description')
    assert hasattr(TestCase, 'test_case_id')
    assert hasattr(TestCase, 'priority')
    assert hasattr(TestCase, 'test_type')
    assert hasattr(TestCase, 'status')
    assert hasattr(TestCase, 'steps')
    assert hasattr(TestCase, 'preconditions')
    assert hasattr(TestCase, 'postconditions')
    assert hasattr(TestCase, 'created_by')
    assert hasattr(TestCase, 'created_at')
    assert hasattr(TestCase, 'updated_at')
    assert hasattr(TestCase, 'project')
    assert hasattr(TestCase, 'test_batch')
    assert hasattr(TestCase, 'creator')


def test_test_case_file_model_fields():
    assert hasattr(TestCaseFile, 'id')
    assert hasattr(TestCaseFile, 'project_id')
    assert hasattr(TestCaseFile, 'filename')
    assert hasattr(TestCaseFile, 'original_filename')
    assert hasattr(TestCaseFile, 'file_format')
    assert hasattr(TestCaseFile, 'file_size')
    assert hasattr(TestCaseFile, 'content')
    assert hasattr(TestCaseFile, 'parsed_data')
    assert hasattr(TestCaseFile, 'status')
    assert hasattr(TestCaseFile, 'error_message')
    assert hasattr(TestCaseFile, 'uploaded_by')
    assert hasattr(TestCaseFile, 'uploaded_at')
    assert hasattr(TestCaseFile, 'project')
    assert hasattr(TestCaseFile, 'uploader')