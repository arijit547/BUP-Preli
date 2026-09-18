"""API route handlers for GridWise endpoints."""

from fastapi import APIRouter, Depends
from app.schemas.request import OptimizeEnergyRequest
from app.schemas.response import HealthResponse, OptimizeEnergyResponse
from app.services.optimization_service import OptimizationService

router = APIRouter()


def get_optimization_service() -> OptimizationService:
    """Dependency injector for OptimizationService."""
    return OptimizationService()


@router.get("/health", response_model=HealthResponse, summary="Readiness Health Check")
async def health_check() -> HealthResponse:
    """Readiness endpoint returning status=ok when service is initialized."""
    return HealthResponse(status="ok")


@router.post(
    "/optimize-energy",
    response_model=OptimizeEnergyResponse,
    summary="Optimize 24-Hour Campus Energy Schedule",
)
async def optimize_energy(
    request: OptimizeEnergyRequest,
    service: OptimizationService = Depends(get_optimization_service),
) -> OptimizeEnergyResponse:
    """Process operator notes via LLM, apply constraints, solve LP, replay and return plan."""
    return await service.optimize(request)
