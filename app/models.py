from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, JSON, Boolean, Float, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    generated_tests = relationship("GeneratedTest", back_populates="user")

    projects: Mapped[list["Project"]] = relationship(back_populates="owner")
    agents: Mapped[list["Agent"]] = relationship(back_populates="owner")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    repo_url: Mapped[str | None] = mapped_column(String)
    branch: Mapped[str] = mapped_column(String, default="main")
    technology_stack: Mapped[list | None] = mapped_column(JSON)
    test_framework: Mapped[str | None] = mapped_column(String)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    generated_tests = relationship("GeneratedTest", back_populates="project", cascade="all, delete-orphan")
    owner: Mapped["User"] = relationship(back_populates="projects")
    analyses = relationship("Analysis", back_populates="project", cascade="all, delete-orphan")
    test_runs = relationship("TestRun", back_populates="project", cascade="all, delete-orphan")
    agent_reports = relationship("AgentReport", back_populates="project", cascade="all, delete-orphan")
    test_batches: Mapped[list["TestBatch"]] = relationship(back_populates="project", cascade="all, delete-orphan")

class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String, default="pending")
    result: Mapped[dict | None] = mapped_column(JSON)
    generated_tests: Mapped[dict | None] = mapped_column(JSON)
    commit_hash: Mapped[str | None] = mapped_column(String)
    branch_name: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="analyses")
    test_runs: Mapped[list["TestRun"]] = relationship(back_populates="analysis")


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("analyses.id"))
    status: Mapped[str] = mapped_column(String, default="pending")
    results: Mapped[dict | None] = mapped_column(JSON)
    coverage: Mapped[float | None] = mapped_column(Float)
    duration: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="test_runs")
    analysis: Mapped["Analysis"] = relationship(back_populates="test_runs")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    token: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    capabilities: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner: Mapped["User"] = relationship(back_populates="agents")
    reports: Mapped[list["AgentReport"]] = relationship(back_populates="agent")


class AgentReport(Base):
    __tablename__ = "agent_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON)
    short_summary: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String, default="info")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent: Mapped["Agent"] = relationship(back_populates="reports")
    project: Mapped["Project"] = relationship(back_populates="agent_reports")


class TestBatch(Base):
    __tablename__ = "test_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="completed")  # completed, pending, failed
    framework: Mapped[str | None] = mapped_column(String)
    ai_provider: Mapped[str | None] = mapped_column(String)
    coverage_improvement: Mapped[float | None] = mapped_column(Float)
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict | None] = mapped_column(JSON)  # Конфигурация генерации
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    project: Mapped["Project"] = relationship(back_populates="test_batches")
    generated_tests: Mapped[list["GeneratedTest"]] = relationship(back_populates="test_batch", cascade="all, delete-orphan")


class GeneratedTest(Base):
    __tablename__ = "generated_tests"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    test_batch_id = Column(Integer, ForeignKey("test_batches.id"), nullable=True)  # Связь с пачкой
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    test_type = Column(String, nullable=False)  # unit, integration, e2e, api
    framework = Column(String, nullable=False)  # pytest, jest, etc.
    content = Column(Text, nullable=False)
    target_file = Column(String)  # исходный файл который тестируется
    priority = Column(String, default="medium")  # high, medium, low
    generated_by = Column(Integer, ForeignKey("users.id"))
    ai_provider = Column(String)
    coverage_estimate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    project = relationship("Project", back_populates="generated_tests")
    user = relationship("User", back_populates="generated_tests")
    test_batch = relationship("TestBatch", back_populates="generated_tests")