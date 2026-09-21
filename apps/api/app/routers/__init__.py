from .auth import auth_router
from .chat import chat_router
from .courses import courses_router
from .files import course_files_router, files_router
from .folder import folders_router
from .ingestion_runs import ingestion_runs_router
from .milestone import milestones_router
from .rag import rag_router

__all__ = [
    "auth_router",
    "files_router",
    "rag_router",
    "ingestion_runs_router",
    "chat_router",
    "courses_router",
    "folders_router",
    "course_files_router",
    "milestones_router",
]
