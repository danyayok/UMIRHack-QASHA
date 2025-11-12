from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime

class AgentMeta(BaseModel):
    hostname: Optional[str]
    timestamp: datetime
    duration_seconds: Optional[float]

class AgentPayload(BaseModel):
    performance: Optional[Any]
    fuzz: Optional[Any]
    concurrency: Optional[Any]
    static_metrics: Optional[Any]
    artifacts: Optional[Any]

class AgentReportCreate(BaseModel):
    agent_name: str = Field(..., description="Registered agent name")
    project_id: Optional[int]
    run_id: Optional[str]
    meta: AgentMeta
    payload: AgentPayload

class AgentReportOut(BaseModel):
    id: int
    agent_id: int
    project_id: Optional[int]
    run_id: Optional[str]
    short_summary: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}
