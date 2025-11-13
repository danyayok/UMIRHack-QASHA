from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    repo_url: Optional[str] = None
    branch: str = Field(default="main")
    technology_stack: Optional[List[str]] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    repo_url: Optional[str]
    branch: str
    technology_stack: Optional[List[str]]
    test_framework: Optional[str]
    owner_id: int
    created_at: datetime
    updated_at: datetime
    coverage: int = 0

    model_config = ConfigDict(from_attributes=True)


class AnalysisCreate(BaseModel):
    project_id: int
    generate_tests: bool = True
    push_to_repo: bool = False
    branch_name: Optional[str] = Field(default="qa-autopilot-tests")


class AnalysisOut(BaseModel):
    id: int
    project_id: int
    status: str
    result: Optional[Dict[str, Any]] = None
    generated_tests: Optional[Dict[str, Any]] = None
    commit_hash: Optional[str] = None
    branch_name: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisStatus(BaseModel):
    id: int
    status: str
    progress: int
    message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    capabilities: Optional[List[str]] = None


class AgentOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: Optional[int]
    is_active: bool
    capabilities: Optional[List[str]]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentMeta(BaseModel):
    hostname: Optional[str] = None
    timestamp: datetime
    duration_seconds: Optional[float] = None


class PerformanceMetrics(BaseModel):
    functions: Optional[List[Dict[str, Any]]] = None


class FuzzResults(BaseModel):
    issues_found: Optional[List[Dict[str, Any]]] = None


class StaticMetrics(BaseModel):
    complexity: Optional[Dict[str, Any]] = None


class Artifacts(BaseModel):
    logs: Optional[List[str]] = None


class AgentPayload(BaseModel):
    performance: Optional[PerformanceMetrics] = None
    fuzz: Optional[FuzzResults] = None
    concurrency: Optional[Dict[str, Any]] = None
    static_metrics: Optional[StaticMetrics] = None
    artifacts: Optional[Artifacts] = None


class AgentReportCreate(BaseModel):
    agent_name: str = Field(..., description="Registered agent name")
    project_id: Optional[int] = None
    run_id: Optional[str] = None
    meta: AgentMeta
    payload: AgentPayload


class AgentReportOut(BaseModel):
    id: int
    agent_id: int
    project_id: Optional[int]
    run_id: Optional[str]
    short_summary: Optional[str]
    severity: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TestRunBase(BaseModel):
    project_id: int
    analysis_id: Optional[int] = None
    status: str
    results: Optional[Dict[str, Any]] = None
    coverage: Optional[float] = None
    duration: Optional[float] = None

class TestRunCreate(TestRunBase):
    pass

class TestRunOut(TestRunBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)