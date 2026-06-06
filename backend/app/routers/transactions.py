from datetime import date
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from arq.connections import ArqRedis

from app.core.database import get_db
from app.core.dependencies import get_db_user_id, get_redis_pool
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionRead, TransactionCreate, TransactionUpdate, TransactionPaginated
from app.services import transactions as txn_service
from app.services.ingestion import parse_csv_stream, ingest_transactions, fetch_mock_bank_data
from app.services.normalizer import normalize_transaction_data

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])

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
    
    if async_mode:
        job = await redis.enqueue_job("process_csv_upload", str(user_id), csv_content)
        return {"job_id": job.job_id, "status": "processing"}
        
    normalized, quarantined = await parse_csv_stream(csv_content)
    result = await ingest_transactions(db, user_id, normalized)
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
    if async_mode:
        job = await redis.enqueue_job("fetch_mock_bank_data_task", str(user_id))
        return {"job_id": job.job_id, "status": "processing"}
        
    raw_data = await fetch_mock_bank_data()
    normalized = [normalize_transaction_data(item, source="bank_api") for item in raw_data]
    result = await ingest_transactions(db, user_id, normalized)
    return result

@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def create_manual_transaction(
    payload: TransactionCreate,
    force: bool = False,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Create a new manual transaction, with duplicate checking."""
    txn_dict = payload.model_dump()
    txn_dict["source"] = "manual"
    
    from app.services.deduplication import compute_transaction_hash
    h = compute_transaction_hash(user_id, txn_dict["date"], txn_dict["amount"], txn_dict["merchant"])
    
    if not force:
        query = select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.hash == h
        )
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
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
    else:
        txn_dict["merchant"] = f"{txn_dict['merchant']} (duplicate)"
        
    txn = await txn_service.create_transaction(db, user_id, txn_dict)
    await db.commit()
    return txn

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
    """Retrieve a paginated and filtered list of transactions for the current user."""
    conditions = [Transaction.user_id == user_id]
    
    if start_date:
        conditions.append(Transaction.date >= start_date)
    if end_date:
        conditions.append(Transaction.date <= end_date)
    if category:
        conditions.append(Transaction.category == category.lower())
    if merchant:
        conditions.append(Transaction.merchant.ilike(f"%{merchant}%"))
        
    where_clause = and_(*conditions)
    
    count_query = select(func.count()).select_from(Transaction).where(where_clause)
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()
    
    query = select(Transaction).where(where_clause).order_by(desc(Transaction.date)).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size
    }

@router.get("/{id}", response_model=TransactionRead)
async def read_transaction(
    id: UUID,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Read a specific transaction details for the current user."""
    query = select(Transaction).where(
        Transaction.id == id,
        Transaction.user_id == user_id
    )
    result = await db.execute(query)
    txn = result.scalar_one_or_none()
    if not txn:
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
    db: AsyncSession = Depends(get_db)
):
    """Update transaction details and adjust monthly rollups accordingly."""
    update_dict = payload.model_dump(exclude_unset=True)
    txn = await txn_service.update_transaction(db, user_id, id, update_dict)
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    await db.commit()
    return txn

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction_route(
    id: UUID,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Delete a transaction and decrement the corresponding monthly rollup."""
    deleted = await txn_service.delete_transaction(db, user_id, id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    await db.commit()
    return None
