from fastapi import APIRouter

from fare_watch.schemas import HealthRead

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> HealthRead:
    """Report that the application is up.

    Returns:
        The health status.
    """
    return HealthRead(status="ok")
