import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from proofmerge.database import SessionFactory, get_session
from proofmerge.demo import DEMO_DATA
from proofmerge.events import KafkaReviewQueue
from proofmerge.models import ReviewStatus
from proofmerge.repository import (
    create_review,
    get_review,
    list_reviews,
    save_human_decision,
    upsert_pull_request,
)
from proofmerge.schemas import (
    DemoReviewCreate,
    HumanDecisionCreate,
    ReviewList,
    ReviewRead,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])


async def dispatch_review(
    request: Request, background_tasks: BackgroundTasks, review_id: str
) -> None:
    settings = request.app.state.settings
    if settings.queue_backend == "kafka":
        await KafkaReviewQueue(settings).publish(review_id)
    else:
        background_tasks.add_task(request.app.state.orchestrator.run, review_id)


@router.get("", response_model=ReviewList)
async def reviews_index(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> ReviewList:
    items, total = await list_reviews(session, limit=limit, offset=offset)
    return ReviewList(items=[ReviewRead.model_validate(item) for item in items], total=total)


@router.get("/{review_id}", response_model=ReviewRead)
async def review_show(
    review_id: str,
    session: AsyncSession = Depends(get_session),
) -> ReviewRead:
    review = await get_review(session, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return ReviewRead.model_validate(review)


@router.post("/demo", response_model=ReviewRead, status_code=status.HTTP_202_ACCEPTED)
async def create_demo_review(
    payload: DemoReviewCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> ReviewRead:
    pull_request = await upsert_pull_request(session, DEMO_DATA[payload.scenario])
    review = await create_review(session, pull_request)
    await dispatch_review(request, background_tasks, review.id)
    loaded = await get_review(session, review.id)
    if loaded is None:
        raise HTTPException(status_code=500, detail="Review could not be created")
    return ReviewRead.model_validate(loaded)


@router.post("/{review_id}/rerun", response_model=ReviewRead, status_code=status.HTTP_202_ACCEPTED)
async def rerun_review(
    review_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> ReviewRead:
    review = await get_review(session, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.status == ReviewStatus.running:
        raise HTTPException(status_code=409, detail="Review is already running")
    review.status = ReviewStatus.queued
    review.summary = "Review queued for another evidence pass"
    review.error = ""
    await session.commit()
    await dispatch_review(request, background_tasks, review.id)
    return ReviewRead.model_validate(review)


@router.post("/{review_id}/decision", response_model=ReviewRead)
async def decide_review(
    review_id: str,
    payload: HumanDecisionCreate,
    session: AsyncSession = Depends(get_session),
) -> ReviewRead:
    review = await get_review(session, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.status != ReviewStatus.awaiting_approval:
        raise HTTPException(status_code=409, detail="Review is not awaiting human approval")
    await save_human_decision(
        session,
        review,
        decision=payload.decision,
        reviewer=payload.reviewer,
        note=payload.note,
    )
    loaded = await get_review(session, review.id)
    if loaded is None:
        raise HTTPException(status_code=500, detail="Decision could not be loaded")
    return ReviewRead.model_validate(loaded)


async def review_event_stream(review_id: str) -> AsyncIterator[str]:
    last_version = ""
    while True:
        async with SessionFactory() as session:
            review = await get_review(session, review_id)
            if review is None:
                yield 'event: error\ndata: {"detail":"Review not found"}\n\n'
                return
            data = ReviewRead.model_validate(review).model_dump(mode="json")
            version = json.dumps(data, sort_keys=True)
            if version != last_version:
                yield f"event: review\ndata: {json.dumps(data)}\n\n"
                last_version = version
            if review.status in {
                ReviewStatus.awaiting_approval,
                ReviewStatus.approved,
                ReviewStatus.rejected,
                ReviewStatus.failed,
            }:
                return
        yield ": keepalive\n\n"
        await asyncio.sleep(1)


@router.get("/{review_id}/events")
async def review_events(review_id: str) -> StreamingResponse:
    return StreamingResponse(
        review_event_stream(review_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
