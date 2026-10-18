from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.edge_auth import get_current_edge
from app.db.session import get_db
from app.models.edge_device import EdgeDevice
from app.schemas.edge import EdgeFailure, EdgeLibrary, EdgeLibraryState, EdgePoll, EdgePollResponse, EdgeProgress, EdgeProgressResponse
from app.schemas.job_history import JobHistoryRead
from app.services.edge import EdgeService

# Called by edge devices with their token, never by the web app.
router = APIRouter(prefix="/edge/agent", tags=["edge agent"])
service = EdgeService()
# A gzipped listing of a very large library stays well below this.
MAX_REPORT_BYTES = 200 * 1024 * 1024


def _job(db: Session, edge: EdgeDevice, job_id: str):
    job = service.job(db, edge, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/poll", response_model=EdgePollResponse, summary="Edge check-in", description="Report status and drives; returns settings, libraries and waiting jobs.")
def poll(data: EdgePoll, edge: EdgeDevice = Depends(get_current_edge), db: Session = Depends(get_db)):
    return service.poll(db, edge, data)


@router.get("/libraries", response_model=list[EdgeLibrary], summary="Edge libraries", description="The libraries assigned to this device.")
def libraries(edge: EdgeDevice = Depends(get_current_edge), db: Session = Depends(get_db)):
    return service.libraries(db, edge)


@router.get(
    "/libraries/{library_id}/state",
    response_model=EdgeLibraryState,
    summary="Indexed files of a library",
    description="Size, time and hash presence per relative path, so only new or changed files are hashed.",
)
def library_state(library_id: str, edge: EdgeDevice = Depends(get_current_edge), db: Session = Depends(get_db)):
    library = service.library(db, edge, library_id)
    if library is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    return service.library_state(db, library)


@router.post("/jobs/{job_id}/progress", response_model=EdgeProgressResponse, summary="Edge job progress", description="Returns cancelled=true when the job was cancelled.")
def job_progress(job_id: str, data: EdgeProgress, edge: EdgeDevice = Depends(get_current_edge), db: Session = Depends(get_db)):
    return {"cancelled": service.progress(db, _job(db, edge, job_id), data.done, data.total, data.details)}


@router.post("/jobs/{job_id}/fail", response_model=JobHistoryRead, summary="Edge job failed", description="The device could not run the job; the reason is shown in the web app.")
def job_failed(job_id: str, data: EdgeFailure, edge: EdgeDevice = Depends(get_current_edge), db: Session = Depends(get_db)):
    job = _job(db, edge, job_id)
    service.fail(db, job, data.error)
    return job


@router.post(
    "/jobs/{job_id}/report",
    response_model=JobHistoryRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Edge scan result",
    description="The gzipped JSON listing of the whole library; the server's worker stores it.",
)
async def job_report(job_id: str, request: Request, edge: EdgeDevice = Depends(get_current_edge), db: Session = Depends(get_db)):
    job = _job(db, edge, job_id)
    if job.task_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This job already has its report")
    body = await request.body()
    if len(body) > MAX_REPORT_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Report too large")
    try:
        return service.save_report(db, job, body)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unreadable report: {exc}") from exc
