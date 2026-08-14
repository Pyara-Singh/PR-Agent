import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from PR_Agent.coding import CodingAgentError, CodingAgentService
from PR_Agent.schemas import CodingDecisionCreate, CodingJobCreate

router = APIRouter(prefix="/coding", tags=["coding"])


def get_service(request: Request) -> CodingAgentService:
    return request.app.state.coding_agent


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_coding_job(
    payload: CodingJobCreate, request: Request, background_tasks: BackgroundTasks
) -> dict:
    service = get_service(request)
    try:
        job = service.create_job(payload.prompt, payload.repository_path)
    except CodingAgentError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    background_tasks.add_task(service.run, job.id)
    return job.public()


@router.get("/jobs/{job_id}")
async def coding_job_show(job_id: str, request: Request) -> dict:
    job = get_service(request).get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Coding job not found")
    return job.public()


@router.post("/jobs/{job_id}/decision")
async def decide_coding_job(job_id: str, payload: CodingDecisionCreate, request: Request) -> dict:
    try:
        job = await get_service(request).decide(
            job_id, payload.approved_paths, payload.commit_message, payload.push
        )
    except CodingAgentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return job.public()


async def coding_event_stream(service: CodingAgentService, job_id: str) -> AsyncIterator[str]:
    previous = ""
    while True:
        job = service.get_job(job_id)
        if job is None:
            yield 'event: error\ndata: {"detail":"Coding job not found"}\n\n'
            return
        data = job.public()
        serialized = json.dumps(data, sort_keys=True)
        if serialized != previous:
            yield f"event: coding_job\ndata: {serialized}\n\n"
            previous = serialized
        if job.status in {"awaiting_approval", "rejected", "committed", "pushed", "failed"}:
            return
        yield ": keepalive\n\n"
        await asyncio.sleep(1)


@router.get("/jobs/{job_id}/events")
async def coding_job_events(job_id: str, request: Request) -> StreamingResponse:
    return StreamingResponse(
        coding_event_stream(get_service(request), job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
