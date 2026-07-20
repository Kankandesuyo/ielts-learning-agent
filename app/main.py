from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.security import enforce_authentication
from app.services.knowledge_service import KnowledgeService
from app.routers import auth, documents, errors, exam, health, knowledge, listening, profile, reading, speaking, study_plan, supervisor, vocabulary, writing


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Indexing is infrastructure work. Keep it automatic so learners only
    # interact with questions and feedback.
    KnowledgeService().build_index(force=False)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="IELTS Learning Agent",
        description="MVP backend for a personalized IELTS study agent.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.middleware("http")(enforce_authentication)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(study_plan.router)
    app.include_router(writing.router)
    app.include_router(speaking.router)
    app.include_router(reading.router)
    app.include_router(listening.router)
    app.include_router(vocabulary.router)
    app.include_router(errors.router)
    app.include_router(supervisor.router)
    app.include_router(documents.router)
    app.include_router(knowledge.router)
    app.include_router(exam.router)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse("app/static/index.html")

    return app


app = create_app()
