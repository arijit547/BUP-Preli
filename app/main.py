"""FastAPI main application entrypoint with robust error sanitization."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.routes import router
from app.core.config import settings
from app.core.logging import logger
from app.directives.validator import DirectiveValidationError
from app.optimizer.highs_solver import SolverError
from app.validation.replay import ReplayValidationError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logger.info(
        "Starting GridWise Backend Service",
        extra={
            "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_MODEL,
            "port": settings.PORT,
        },
    )
    yield
    logger.info("Shutting down GridWise Backend Service")


app = FastAPI(
    title="GridWise LLM Energy Optimization Backend",
    description="Smart Campus 24-Hour Energy Scheduling & Operator Directive Interpretation",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for public judging harnesses
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Sanitize structural request validation errors into a clean 400 Bad Request."""
    errors = exc.errors()
    simplified_errors = []
    for err in errors:
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Validation error")
        simplified_errors.append(f"{loc}: {msg}")

    logger.warning("Request validation failed", extra={"errors": simplified_errors})
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Invalid request schema", "errors": simplified_errors},
    )


@app.exception_handler(DirectiveValidationError)
async def directive_validation_handler(request: Request, exc: DirectiveValidationError):
    """Handle directive guardrail validation failures as 422 Unprocessable Entity."""
    logger.warning("Directive guardrail check failed", extra={"error": str(exc)})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": f"Directive validation error: {str(exc)}"},
    )


@app.exception_handler(SolverError)
async def solver_exception_handler(request: Request, exc: SolverError):
    """Handle solver infeasibility or numerical failure safely without leaking internals."""
    logger.error("Linear programming solver failed", extra={"error": str(exc)})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Optimization solver error"},
    )


@app.exception_handler(ReplayValidationError)
async def replay_exception_handler(request: Request, exc: ReplayValidationError):
    """Handle schedule replay verification failure safely."""
    logger.error("Independent replay validator failed", extra={"error": str(exc)})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Schedule physical verification failed"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all handler ensuring no stack traces or secrets are ever exposed."""
    logger.error("Unhandled service exception", extra={"error_type": type(exc).__name__, "err_detail": str(exc)})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Optimization service internal error"},
    )


# Register API routes
app.include_router(router)
