from uuid import UUID
from app.core.database import AsyncSessionLocal
from app.services.ingestion import parse_csv_stream, ingest_transactions, fetch_mock_bank_data
from app.services.normalizer import normalize_transaction_data

async def process_csv_upload(ctx, user_id_str: str, csv_content: str) -> dict:
    """Background task to parse and ingest a CSV file for a user."""
    user_id = UUID(user_id_str)
    normalized, quarantined = await parse_csv_stream(csv_content)
    
    async with AsyncSessionLocal() as session:
        result = await ingest_transactions(session, user_id, normalized)
        
    return {
        "inserted": result["inserted"],
        "duplicates_skipped": result["duplicates_skipped"],
        "quarantined_count": len(quarantined),
        "quarantined_items": quarantined,
        "suspected_duplicates": result["suspected_duplicates"]
    }

async def fetch_mock_bank_data_task(ctx, user_id_str: str) -> dict:
    """Background task to fetch and ingest mock bank transactions for a user."""
    user_id = UUID(user_id_str)
    raw_data = await fetch_mock_bank_data()
    
    normalized = []
    for item in raw_data:
        normalized.append(normalize_transaction_data(item, source="bank_api"))
        
    async with AsyncSessionLocal() as session:
        result = await ingest_transactions(session, user_id, normalized)
        
    return result
