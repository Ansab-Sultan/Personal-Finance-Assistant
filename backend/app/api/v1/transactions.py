from datetime import date
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from arq.connections import ArqRedis
from arq.jobs import Job


from app.core.database import get_db
from app.core.dependencies import get_db_user_id, get_redis_pool
from app.core.logger import get_logger
from app.schemas.transaction import TransactionRead, TransactionCreate, TransactionUpdate, TransactionPaginated, ReceiptParseRequest
from app.services import transactions as txn_service
from app.services.ingestion import parse_csv_stream, ingest_transactions, fetch_mock_bank_data
from app.services.normalizer import normalize_transaction_data
from app.core.exceptions import DuplicateTransactionError

logger = get_logger(__name__)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/upload-csv", status_code=status.HTTP_202_ACCEPTED)
async def upload_csv(
    file: UploadFile = File(...),
    async_mode: bool = Query(True, alias="async"),
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db),
    redis: ArqRedis = Depends(get_redis_pool)
):
    """Ingest transactions from an uploaded CSV file."""
    content = await file.read()
    csv_content = content.decode("utf-8")
    logger.info(
        "CSV upload — user_id=%s filename=%s size=%d bytes async_mode=%s",
        user_id, file.filename, len(content), async_mode
    )

    if async_mode:
        job = await redis.enqueue_job("process_csv_upload", str(user_id), csv_content)
        logger.debug("CSV job enqueued — job_id=%s user_id=%s", job.job_id, user_id)
        return {"job_id": job.job_id, "status": "processing"}

    normalized, quarantined = await parse_csv_stream(csv_content)
    result = await ingest_transactions(db, user_id, normalized)
    await db.commit()
    logger.info(
        "CSV ingestion complete — user_id=%s inserted=%d duplicates=%d quarantined=%d",
        user_id, result["inserted"], result["duplicates_skipped"], len(quarantined)
    )
    return {
        "inserted": result["inserted"],
        "duplicates_skipped": result["duplicates_skipped"],
        "quarantined_count": len(quarantined),
        "quarantined_items": quarantined,
        "suspected_duplicates": result["suspected_duplicates"]
    }


@router.post("/fetch-bank", status_code=status.HTTP_202_ACCEPTED)
async def fetch_bank(
    async_mode: bool = Query(True, alias="async"),
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db),
    redis: ArqRedis = Depends(get_redis_pool)
):
    """Trigger ingestion from the mock bank API."""
    logger.info("Bank fetch triggered — user_id=%s async_mode=%s", user_id, async_mode)
    if async_mode:
        job = await redis.enqueue_job("fetch_mock_bank_data_task", str(user_id))
        logger.debug("Bank fetch job enqueued — job_id=%s user_id=%s", job.job_id, user_id)
        return {"job_id": job.job_id, "status": "processing"}

    raw_data = await fetch_mock_bank_data()
    normalized = [normalize_transaction_data(item, source="bank_api") for item in raw_data]
    result = await ingest_transactions(db, user_id, normalized)
    await db.commit()
    logger.info(
        "Bank fetch ingestion complete — user_id=%s inserted=%d",
        user_id, result.get("inserted", 0)
    )
    return result



@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def create_manual_transaction(
    payload: TransactionCreate,
    force: bool = False,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db),
    redis: ArqRedis = Depends(get_redis_pool)
):
    """Create a new manual transaction, verifying uniqueness through the transaction service."""
    logger.info(
        "Manual transaction create — user_id=%s merchant=%s amount=%s force=%s",
        user_id, payload.merchant, payload.amount, force
    )
    txn_dict = payload.model_dump()
    try:
        txn = await txn_service.create_manual_transaction(db, user_id, txn_dict, force)
        await db.commit()
        await redis.enqueue_job("recompute_detections_task", str(user_id))
        logger.debug("Manual transaction created — txn_id=%s user_id=%s", txn.id, user_id)
        return txn
    except DuplicateTransactionError as exc:
        existing = exc.existing_transaction
        logger.warning(
            "Duplicate transaction rejected — user_id=%s existing_id=%s",
            user_id, existing.id
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Looks like a duplicate transaction exists.",
                "existing_transaction": {
                    "id": str(existing.id),
                    "date": existing.date.isoformat(),
                    "amount": float(existing.amount),
                    "merchant": existing.merchant
                }
            }
        )


@router.get("", response_model=TransactionPaginated)
async def list_transactions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category: Optional[str] = None,
    merchant: Optional[str] = None,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve filtered and paginated list of transactions from the service."""
    logger.debug(
        "Listing transactions — user_id=%s page=%d size=%d category=%s merchant=%s",
        user_id, page, size, category, merchant
    )
    items, total = await txn_service.list_transactions(
        db, user_id, page, size, start_date, end_date, category, merchant
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size
    }


@router.get("/subscriptions")
async def get_user_subscriptions(
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve precomputed subscription detections for the current user."""
    logger.debug("Fetching subscriptions — user_id=%s", user_id)
    from app.services.subscriptions import get_detected_subscriptions
    return await get_detected_subscriptions(db, user_id)


@router.get("/anomalies")
async def get_user_anomalies(
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve precomputed transaction anomalies for the current user."""
    logger.debug("Fetching anomalies — user_id=%s", user_id)
    from app.services.anomalies import get_flagged_anomalies
    return await get_flagged_anomalies(db, user_id)


@router.post("/receipts/parse")
async def parse_receipt(
    payload: ReceiptParseRequest,
    user_id: UUID = Depends(get_db_user_id)
):
    """Parse a receipt image and return extracted transaction fields."""
    logger.info("Receipt parse request — user_id=%s mime_type=%s", user_id, payload.mime_type)
    from app.services.receipt import parse_receipt_image
    try:
        data = await parse_receipt_image(payload.image_base64, payload.mime_type)
        logger.debug("Receipt parsed — user_id=%s merchant=%s", user_id, data.get("merchant"))
        return data
    except Exception as exc:
        logger.error("Receipt parse failed — user_id=%s error=%s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse receipt image: {str(exc)}"
        )


@router.get("/{id}", response_model=TransactionRead)
async def read_transaction(
    id: UUID,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Read a specific transaction details for the current user."""
    logger.debug("Reading transaction — user_id=%s txn_id=%s", user_id, id)
    txn = await txn_service.get_transaction(db, user_id, id)
    if not txn:
        logger.warning("Transaction not found — user_id=%s txn_id=%s", user_id, id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    return txn


@router.patch("/{id}", response_model=TransactionRead)
async def update_transaction_route(
    id: UUID,
    payload: TransactionUpdate,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db),
    redis: ArqRedis = Depends(get_redis_pool)
):
    """Update transaction details and adjust monthly rollups accordingly."""
    logger.info("Updating transaction — user_id=%s txn_id=%s", user_id, id)
    update_dict = payload.model_dump(exclude_unset=True)
    txn = await txn_service.update_transaction(db, user_id, id, update_dict)
    if not txn:
        logger.warning("Transaction not found for update — user_id=%s txn_id=%s", user_id, id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    await db.commit()
    await redis.enqueue_job("recompute_detections_task", str(user_id))
    return txn


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction_route(
    id: UUID,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db),
    redis: ArqRedis = Depends(get_redis_pool)
):
    """Delete a transaction and decrement the corresponding monthly rollup."""
    logger.info("Deleting transaction — user_id=%s txn_id=%s", user_id, id)
    deleted = await txn_service.delete_transaction(db, user_id, id)
    if not deleted:
        logger.warning("Transaction not found for deletion — user_id=%s txn_id=%s", user_id, id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    await db.commit()
    await redis.enqueue_job("recompute_detections_task", str(user_id))
    return None


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    redis: ArqRedis = Depends(get_redis_pool),
    user_id: UUID = Depends(get_db_user_id)
):
    """Retrieve the status and result of a background job."""
    logger.debug("Checking job status — user_id=%s job_id=%s", user_id, job_id)
    job = Job(job_id, redis)
    status_val = await job.status()
    if status_val == "complete":
        result = await job.result()
        return {"status": "complete", "result": result}
    return {"status": status_val}

