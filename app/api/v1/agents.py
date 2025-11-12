from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.schemas import AgentReportCreate, AgentReportOut, AgentCreate, AgentOut
from app.models import Agent, AgentReport

router = APIRouter()

async def get_agent_by_token(db: AsyncSession, token: str):
    res = await db.execute(select(Agent).where(Agent.token == token))
    return res.scalar_one_or_none()

@router.post("/cpp/report", response_model=AgentReportOut)
async def receive_cpp_report(
        report_in: AgentReportCreate,
        x_agent_token: str = Header(None),
        db: AsyncSession = Depends(get_db)
):
    if not x_agent_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Agent-Token"
        )
    agent = await get_agent_by_token(db, x_agent_token)
    if not agent or agent.name != report_in.agent_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent token or name"
        )
    ar = AgentReport(
        agent_id=agent.id,
        project_id=report_in.project_id,
        run_id=report_in.run_id,
        payload=report_in.payload.model_dump(),
        short_summary=None
    )
    # Simple summary
    try:
        perf = report_in.payload.performance
        if isinstance(perf, dict) and perf.get("functions"):
            top = perf["functions"][:3]
            names = [f.get("name", "?") for f in top]
            ar.short_summary = "Top functions: " + ", ".join(names)
    except Exception:
        pass
    db.add(ar)
    await db.commit()
    await db.refresh(ar)
    return AgentReportOut.model_validate(ar)

@router.post("/register", response_model=AgentOut)
async def register_agent(
        agent_in: AgentCreate,
        db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Agent).where(Agent.name == agent_in.name))
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Agent name already exists")

    import secrets
    token = secrets.token_hex(32)

    a = Agent(
        name=agent_in.name,
        token=token,
        description=agent_in.description,
        capabilities=agent_in.capabilities
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return AgentOut.model_validate(a)

@router.get("/", response_model=list[AgentOut])
async def list_agents(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Agent))
    agents = res.scalars().all()
    return [AgentOut.model_validate(agent) for agent in agents]