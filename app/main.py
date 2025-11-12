from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import auth, projects, agents, ai_route
from app.db.session import init_models

app = FastAPI(title="QA Autopilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(ai_route.router, prefix="/api/v1/ai", tags=["ai"])

@app.on_event("startup")
async def on_startup():
    await init_models()

@app.get("/")
async def root():
    return {"message": "QA Autopilot API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}