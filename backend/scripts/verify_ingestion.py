import asyncio
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import DBAPIError

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.transaction import Transaction, MonthlyCategoryRollup, TransactionCategory
from app.models.budget import Budget, BudgetPeriod
from app.models.preference import UserPreference
from app.services.ingestion import parse_csv_stream, ingest_transactions, fetch_mock_bank_data
from app.services.normalizer import normalize_transaction_data
from app.services.transactions import (
    create_transaction,
    update_transaction,
    delete_transaction,
    get_month_str
)
from app.services.budget import (
    create_or_update_budget,
    get_budget,
    list_budgets,
    delete_budget,
    compute_budget_status,
    get_all_budget_statuses
)
from app.services.memory import (
    upsert_preference,
    get_preference_by_key,
    get_preferences,
    delete_preference
)
from app.models.chat import ChatMessage, MessageRole
from app.services import chat as chat_service
from app.services.llm import llm_client

async def setup_test_users(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Create two test users in the database and return their UUIDs."""
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()
    
    user1 = User(
        id=user1_id,
        clerk_id=f"clerk_{user1_id}",
        email="user1@example.com"
    )
    user2 = User(
        id=user2_id,
        clerk_id=f"clerk_{user2_id}",
        email="user2@example.com"
    )
    
    session.add_all([user1, user2])
    await session.commit()
    return user1_id, user2_id

async def cleanup_data(session: AsyncSession, user1_id: uuid.UUID, user2_id: uuid.UUID) -> None:
    """Clean up all inserted test user data, transactions, budgets, preferences, and rollups."""
    await session.execute(delete(UserPreference).where(UserPreference.user_id.in_([user1_id, user2_id])))
    await session.execute(delete(Budget).where(Budget.user_id.in_([user1_id, user2_id])))
    await session.execute(delete(MonthlyCategoryRollup).where(MonthlyCategoryRollup.user_id.in_([user1_id, user2_id])))
    await session.execute(delete(Transaction).where(Transaction.user_id.in_([user1_id, user2_id])))
    await session.execute(delete(ChatMessage).where(ChatMessage.user_id.in_([user1_id, user2_id])))
    await session.execute(delete(User).where(User.id.in_([user1_id, user2_id])))
    await session.commit()

async def test_csv_parsing_and_quarantine() -> None:
    """Verify CSV parser correctly extracts data and quarantines junk rows."""
    csv_content = """Date,Amount,Merchant,Description,Category,Currency
2026-06-01,-100.00,Starbucks,Coffee,food,USD
invalid-date,-50.00,Target,Shopping,groceries,USD
2026-06-02,,Netflix,Sub,entertainment,USD
2026-06-03,-15.50,Uber,Taxi,transportation,USD
"""
    normalized, quarantined = await parse_csv_stream(csv_content)
    
    assert len(normalized) == 2, f"Expected 2 normalized rows, got {len(normalized)}"
    assert len(quarantined) == 2, f"Expected 2 quarantined rows, got {len(quarantined)}"
    
    assert normalized[0]["merchant"] == "Starbucks"
    assert normalized[0]["amount"] == -100.0
    assert normalized[0]["date"] == date(2026, 6, 1)
    assert normalized[0]["category"] == "restaurants"
    
    assert quarantined[0]["row_number"] == 2
    assert "Could not parse date" in quarantined[0]["reason"]
    assert quarantined[1]["row_number"] == 3
    assert "Missing required fields" in quarantined[1]["reason"]
    
    print("✓ CSV Parsing & Quarantine verification passed.")

async def test_ingestion_and_idempotency(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Verify ingestion creates transactions, drops duplicates, and populates rollups."""
    csv_content = """Date,Amount,Merchant,Description,Category,Currency
2026-06-01,-100.00,Starbucks,Coffee,food,USD
2026-06-03,-15.50,Uber,Taxi,transportation,USD
"""
    normalized, _ = await parse_csv_stream(csv_content)
    result = await ingest_transactions(session, user_id, normalized)
    await session.commit()
    
    assert result["inserted"] == 2, f"Expected 2 inserted, got {result['inserted']}"
    assert result["duplicates_skipped"] == 0
    
    dup_result = await ingest_transactions(session, user_id, normalized)
    await session.commit()
    
    assert dup_result["inserted"] == 0, "Idempotency failed: rows were re-inserted"
    assert dup_result["duplicates_skipped"] == 2
    
    rollup_query = select(MonthlyCategoryRollup).where(MonthlyCategoryRollup.user_id == user_id)
    rollup_res = await session.execute(rollup_query)
    rollups = rollup_res.scalars().all()
    
    assert len(rollups) == 2, f"Expected 2 rollups, got {len(rollups)}"
    
    restaurants_rollup = next(r for r in rollups if r.category == "restaurants")
    assert restaurants_rollup.month == "2026-06"
    assert Decimal(str(restaurants_rollup.total_amount)) == Decimal("-100.00")
    assert restaurants_rollup.txn_count == 1
    
    print("✓ Ingestion & Idempotency & Rollup Init verification passed.")

async def test_mock_bank_data(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Verify mock bank fetch works and integrates with the database."""
    raw_data = await fetch_mock_bank_data()
    assert len(raw_data) > 0, "No mock bank data returned"
    
    normalized = [normalize_transaction_data(item, source="bank_api") for item in raw_data]
    result = await ingest_transactions(session, user_id, normalized)
    await session.commit()
    
    assert result["inserted"] > 0, "No transactions inserted from mock bank data"
    
    print("✓ Mock Bank Ingestion verification passed.")

async def test_single_row_crud_and_rollup_sync(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Verify creating, updating, and deleting single transactions correctly updates rollups."""
    txn_data = {
        "date": date(2026, 6, 10),
        "amount": -50.00,
        "merchant": "Target",
        "raw_description": "Target Store",
        "category": "groceries",
        "currency": "USD"
    }
    
    txn = await create_transaction(session, user_id, txn_data)
    await session.commit()
    
    rollup_query = select(MonthlyCategoryRollup).where(
        MonthlyCategoryRollup.user_id == user_id,
        MonthlyCategoryRollup.month == "2026-06",
        MonthlyCategoryRollup.category == "groceries"
    )
    rollup_res = await session.execute(rollup_query)
    rollup = rollup_res.scalar_one()
    
    initial_amount = Decimal(str(rollup.total_amount))
    initial_count = rollup.txn_count
    
    update_data = {
        "amount": -80.00,
        "category": "groceries"
    }
    await update_transaction(session, user_id, txn.id, update_data)
    await session.commit()
    
    rollup_res = await session.execute(rollup_query)
    rollup = rollup_res.scalar_one()
    assert Decimal(str(rollup.total_amount)) == initial_amount - Decimal("30.00")
    assert rollup.txn_count == initial_count
    
    new_rollup_query = select(MonthlyCategoryRollup).where(
        MonthlyCategoryRollup.user_id == user_id,
        MonthlyCategoryRollup.month == "2026-06",
        MonthlyCategoryRollup.category == "restaurants"
    )
    new_rollup_res = await session.execute(new_rollup_query)
    initial_restaurants_rollup = new_rollup_res.scalar_one_or_none()
    initial_restaurants_count = initial_restaurants_rollup.txn_count if initial_restaurants_rollup else 0

    update_cat_data = {
        "category": "restaurants"
    }
    await update_transaction(session, user_id, txn.id, update_cat_data)
    await session.commit()
    
    rollup_res = await session.execute(rollup_query)
    old_rollup = rollup_res.scalar_one_or_none()
    assert old_rollup is None or old_rollup.txn_count == initial_count - 1
    
    new_rollup_res = await session.execute(new_rollup_query)
    new_rollup = new_rollup_res.scalar_one()
    assert new_rollup.txn_count == initial_restaurants_count + 1
    
    await delete_transaction(session, user_id, txn.id)
    await session.commit()
    
    new_rollup_res = await session.execute(new_rollup_query)
    post_delete_rollup = new_rollup_res.scalar_one_or_none()
    post_delete_count = post_delete_rollup.txn_count if post_delete_rollup else 0
    assert post_delete_count == initial_restaurants_count
    
    print("✓ Single-Row CRUD & Rollup Sync verification passed.")

async def test_budget_tracking(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Verify budget creation, spent status calculations, warning states, and DB constraints."""
    current_month_str = date.today().strftime("%Y-%m")
    
    await session.execute(delete(MonthlyCategoryRollup).where(MonthlyCategoryRollup.user_id == user_id))
    await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
    await session.commit()
    
    budget = await create_or_update_budget(
        session=session,
        user_id=user_id,
        category=TransactionCategory.groceries,
        limit_amount=100.00,
        period=BudgetPeriod.monthly
    )
    await session.commit()
    assert budget.limit_amount == 100.00
    
    status_ok = await compute_budget_status(
        session=session,
        user_id=user_id,
        category=TransactionCategory.groceries,
        period=BudgetPeriod.monthly,
        limit_amount=100.00
    )
    assert status_ok["spent"] == 0.0
    assert status_ok["state"] == "ok"
    assert status_ok["remaining"] == 100.00
    
    txn1 = {
        "date": date.today(),
        "amount": -75.00,
        "merchant": "Supermarket",
        "category": "groceries"
    }
    await create_transaction(session, user_id, txn1)
    await session.commit()
    
    status_75 = await compute_budget_status(
        session=session,
        user_id=user_id,
        category=TransactionCategory.groceries,
        period=BudgetPeriod.monthly,
        limit_amount=100.00
    )
    assert status_75["spent"] == 75.00
    assert status_75["state"] == "ok"
    assert status_75["remaining"] == 25.00
    
    txn2 = {
        "date": date.today(),
        "amount": -10.00,
        "merchant": "Convenience Store",
        "category": "groceries"
    }
    await create_transaction(session, user_id, txn2)
    await session.commit()
    
    status_85 = await compute_budget_status(
        session=session,
        user_id=user_id,
        category=TransactionCategory.groceries,
        period=BudgetPeriod.monthly,
        limit_amount=100.00
    )
    assert status_85["spent"] == 85.00
    assert status_85["state"] == "warning"
    assert status_85["remaining"] == 15.00
    
    txn3 = {
        "date": date.today(),
        "amount": -20.00,
        "merchant": "Whole Foods",
        "category": "groceries"
    }
    await create_transaction(session, user_id, txn3)
    await session.commit()
    
    status_105 = await compute_budget_status(
        session=session,
        user_id=user_id,
        category=TransactionCategory.groceries,
        period=BudgetPeriod.monthly,
        limit_amount=100.00
    )
    assert status_105["spent"] == 105.00
    assert status_105["state"] == "over"
    assert status_105["remaining"] == 0.0
    
    yearly_budget = await create_or_update_budget(
        session=session,
        user_id=user_id,
        category=TransactionCategory.groceries,
        limit_amount=1000.00,
        period=BudgetPeriod.yearly
    )
    await session.commit()
    
    status_yearly = await compute_budget_status(
        session=session,
        user_id=user_id,
        category=TransactionCategory.groceries,
        period=BudgetPeriod.yearly,
        limit_amount=1000.00
    )
    assert status_yearly["spent"] == 105.00
    assert status_yearly["state"] == "ok"
    assert status_yearly["remaining"] == 895.00
    
    all_budgets = await list_budgets(session, user_id)
    assert len(all_budgets) == 2
    
    all_statuses = await get_all_budget_statuses(session, user_id)
    assert len(all_statuses) == 2
    assert any(s["period"] == BudgetPeriod.monthly for s in all_statuses)
    assert any(s["period"] == BudgetPeriod.yearly for s in all_statuses)
    
    invalid_budget = Budget(
        user_id=user_id,
        category="invalid_category_string",
        limit_amount=500.00,
        period=BudgetPeriod.monthly
    )
    session.add(invalid_budget)
    try:
        await session.commit()
        raise AssertionError("Postgres ENUM constraint failed to reject invalid category")
    except DBAPIError:
        await session.rollback()
        
    print("✓ Budget tracking & status & DB ENUM validation passed.")

async def test_user_preferences(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Verify user preference CRUD, spent status exclusions, and database check constraints."""
    await session.execute(delete(UserPreference).where(UserPreference.user_id == user_id))
    await session.execute(delete(MonthlyCategoryRollup).where(MonthlyCategoryRollup.user_id == user_id))
    await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
    await session.commit()
    
    # 1. Upsert and read
    pref = await upsert_preference(session, user_id, "currency_display", "PKR")
    await session.commit()
    assert pref.value == "PKR"
    
    val = await get_preference_by_key(session, user_id, "currency_display")
    assert val == "PKR"
    
    # 2. Key Check constraint validation
    invalid_pref = UserPreference(
        user_id=user_id,
        key="invalid_preference_key",
        value="value"
    )
    session.add(invalid_pref)
    try:
        await session.commit()
        raise AssertionError("Postgres check constraint failed to reject invalid key")
    except DBAPIError:
        await session.rollback()
        
    # 3. Test list and delete
    prefs = await get_preferences(session, user_id)
    assert len(prefs) == 1
    assert prefs[0].key == "currency_display"
    
    # 4. Spent exclusion test
    # Add a restaurants transaction of -150.00
    await create_transaction(session, user_id, {
        "date": date.today(),
        "amount": -150.00,
        "merchant": "Cafe",
        "category": "restaurants"
    })
    # Add a groceries transaction of -100.00
    await create_transaction(session, user_id, {
        "date": date.today(),
        "amount": -100.00,
        "merchant": "Market",
        "category": "groceries"
    })
    await session.commit()
    
    # spent sum for restaurants before exclusion is 150.00
    status_pre = await compute_budget_status(
        session=session,
        user_id=user_id,
        category=TransactionCategory.restaurants,
        period=BudgetPeriod.monthly,
        limit_amount=500.00
    )
    assert status_pre["spent"] == 150.00
    
    # Set exclude_from_food = groceries
    await upsert_preference(session, user_id, "exclude_from_food", "groceries")
    await session.commit()
    
    # spent sum for restaurants after exclusion should be 150.00 - 100.00 = 50.00
    status_post = await compute_budget_status(
        session=session,
        user_id=user_id,
        category=TransactionCategory.restaurants,
        period=BudgetPeriod.monthly,
        limit_amount=500.00
    )
    assert status_post["spent"] == 50.00
    
    # Clean up preference
    await delete_preference(session, user_id, "exclude_from_food")
    await session.commit()
    
    print("✓ User preferences & spend exclusions verification passed.")

async def test_isolation(session: AsyncSession, user1_id: uuid.UUID, user2_id: uuid.UUID) -> None:
    """Verify that a user cannot access or modify another user's data."""
    txn_data = {
        "date": date(2026, 6, 12),
        "amount": -20.00,
        "merchant": "Gas Station",
        "raw_description": "Gas",
        "category": "transport",
        "currency": "USD"
    }
    
    user1_txn = await create_transaction(session, user1_id, txn_data)
    await session.commit()
    
    updated_txn = await update_transaction(session, user2_id, user1_txn.id, {"amount": -30.00})
    await session.commit()
    
    assert updated_txn is None, "Security vulnerability: user2 was able to update user1's transaction"
    
    deleted = await delete_transaction(session, user2_id, user1_txn.id)
    await session.commit()
    
    assert not deleted, "Security vulnerability: user2 was able to delete user1's transaction"
    
    user1_budget = await create_or_update_budget(
        session=session,
        user_id=user1_id,
        category=TransactionCategory.rent,
        limit_amount=1500.00,
        period=BudgetPeriod.monthly
    )
    await session.commit()
    
    fetched_by_user2 = await get_budget(session, user2_id, user1_budget.id)
    assert fetched_by_user2 is None, "Security vulnerability: user2 was able to read user1's budget"
    
    deleted_by_user2 = await delete_budget(session, user2_id, user1_budget.id)
    await session.commit()
    assert not deleted_by_user2, "Security vulnerability: user2 was able to delete user1's budget"
    
    user1_pref = await upsert_preference(session, user1_id, "currency_display", "USD")
    await session.commit()
    
    pref_by_user2 = await get_preference_by_key(session, user2_id, "currency_display")
    assert pref_by_user2 is None, "Security vulnerability: user2 was able to read user1's preference"
    
    deleted_pref_by_user2 = await delete_preference(session, user2_id, "currency_display")
    await session.commit()
    assert not deleted_pref_by_user2, "Security vulnerability: user2 was able to delete user1's preference"
    
    print("✓ User Isolation verification passed.")

async def test_chat_history_and_summarization(
    session: AsyncSession,
    user1_id: uuid.UUID,
    user2_id: uuid.UUID
) -> None:
    """Verify chat message persistence, chronological retrieval, user isolation, and rolling summarization."""
    from datetime import datetime, timezone, timedelta

    msg1 = ChatMessage(
        user_id=user1_id,
        role=MessageRole.user,
        content="Hello assistant",
        created_at=datetime.now(timezone.utc) - timedelta(seconds=2)
    )
    session.add(msg1)
    await session.flush()

    msg2 = ChatMessage(
        user_id=user1_id,
        role=MessageRole.assistant,
        content="Hello user! How can I help you?",
        created_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    session.add(msg2)
    await session.flush()
    await session.commit()

    unsummarized = await chat_service.count_unsummarized(session, user1_id)
    assert unsummarized == 2

    recent = await chat_service.get_recent_messages(session, user1_id, n=10)
    assert len(recent) == 2
    assert recent[0].content == "Hello assistant"
    assert recent[1].content == "Hello user! How can I help you?"

    user2_recent = await chat_service.get_recent_messages(session, user2_id, n=10)
    assert len(user2_recent) == 0

    await session.execute(delete(ChatMessage).where(ChatMessage.user_id == user1_id))
    await session.commit()

    base_time = datetime.now(timezone.utc) - timedelta(minutes=50)
    for i in range(22):
        u_msg = ChatMessage(
            user_id=user1_id,
            role=MessageRole.user,
            content=f"User turn {i}",
            created_at=base_time + timedelta(seconds=i*2)
        )
        a_msg = ChatMessage(
            user_id=user1_id,
            role=MessageRole.assistant,
            content=f"Assistant turn {i}",
            created_at=base_time + timedelta(seconds=i*2 + 1)
        )
        session.add_all([u_msg, a_msg])
    await session.flush()
    await session.commit()

    unsummarized_count = await chat_service.count_unsummarized(session, user1_id)
    assert unsummarized_count == 44

    summary = await chat_service.maybe_refresh_summary(session, user1_id, llm_client)
    await session.commit()

    assert summary is not None
    assert "Mock consolidated summary" in summary

    summary_row = await chat_service.get_summary_row(session, user1_id)
    assert summary_row is not None
    assert summary_row.role == MessageRole.system
    assert summary_row.content == summary

    post_unsummarized_count = await chat_service.count_unsummarized(session, user1_id)
    assert post_unsummarized_count == 20

    recent_after_summary = await chat_service.get_recent_messages(session, user1_id, n=30)
    assert len(recent_after_summary) == 20
    assert recent_after_summary[0].content == "User turn 12"
    assert recent_after_summary[-1].content == "Assistant turn 21"

    summary_check = await chat_service.maybe_refresh_summary(session, user1_id, llm_client)
    assert summary_check == summary

    print("✓ Chat History & Rolling Summarization verification passed.")

async def test_agent_routing() -> None:
    """Verify router node correctly classifies user intents and decides routes."""
    from app.agent.nodes import router_node
    
    state_spending = {
        "user_id": str(uuid.uuid4()),
        "message": "how much did I spend on groceries this month?",
        "system_instruction": "",
        "messages": [],
        "route": "",
        "intent": "",
        "tool_parameters": {}
    }
    res_spending = await router_node(state_spending)
    assert res_spending["route"] == "fast_lane"
    assert res_spending["intent"] == "spending_query"
    
    state_budget = {
        "user_id": str(uuid.uuid4()),
        "message": "am I on budget for food?",
        "system_instruction": "",
        "messages": [],
        "route": "",
        "intent": "",
        "tool_parameters": {}
    }
    res_budget = await router_node(state_budget)
    assert res_budget["route"] == "fast_lane"
    assert res_budget["intent"] == "budget_check"

    state_cutback = {
        "user_id": str(uuid.uuid4()),
        "message": "can you suggest where I can cut back my expenses?",
        "system_instruction": "",
        "messages": [],
        "route": "",
        "intent": "",
        "tool_parameters": {}
    }
    res_cutback = await router_node(state_cutback)
    assert res_cutback["route"] == "react"
    assert res_cutback["intent"] == "cutback_suggestion"

    state_weather = {
        "user_id": str(uuid.uuid4()),
        "message": "what is the weather like in Tokyo?",
        "system_instruction": "",
        "messages": [],
        "route": "",
        "intent": "",
        "tool_parameters": {}
    }
    res_weather = await router_node(state_weather)
    assert res_weather["route"] == "react"
    assert res_weather["intent"] == "out_of_domain"

    print("✓ Agent Routing verification passed.")

async def test_precomputed_subscriptions_and_anomalies(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Verify that subscriptions and anomalies are precomputed and read from database correctly."""
    from app.services.subscriptions import get_detected_subscriptions
    from app.services.anomalies import get_flagged_anomalies
    
    await session.execute(delete(MonthlyCategoryRollup).where(MonthlyCategoryRollup.user_id == user_id))
    await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
    await session.commit()
    
    txn_sub1 = {
        "date": date(2026, 4, 1),
        "amount": -29.99,
        "merchant": "Netflix",
        "category": "subscriptions",
        "currency": "USD"
    }
    txn_sub2 = {
        "date": date(2026, 5, 2),
        "amount": -29.99,
        "merchant": "Netflix",
        "category": "subscriptions",
        "currency": "USD"
    }
    await create_transaction(session, user_id, txn_sub1)
    await create_transaction(session, user_id, txn_sub2)
    
    txn_avg1 = {
        "date": date(2026, 6, 1),
        "amount": -10.00,
        "merchant": "McDonalds",
        "category": "restaurants",
        "currency": "USD"
    }
    txn_avg2 = {
        "date": date(2026, 6, 2),
        "amount": -20.00,
        "merchant": "Subway",
        "category": "restaurants",
        "currency": "USD"
    }
    txn_anomaly = {
        "date": date(2026, 6, 5),
        "amount": -100.00,
        "merchant": "Fancy Dinner",
        "category": "restaurants",
        "currency": "USD"
    }
    await create_transaction(session, user_id, txn_avg1)
    await create_transaction(session, user_id, txn_avg2)
    await create_transaction(session, user_id, txn_anomaly)
    await session.commit()
    
    subs = await get_detected_subscriptions(session, user_id)
    assert len(subs) == 1, f"Expected 1 subscription, got {len(subs)}"
    assert subs[0].merchant == "Netflix"
    assert abs(float(subs[0].amount) - 29.99) < 0.01
    
    anoms = await get_flagged_anomalies(session, user_id)
    assert len(anoms) == 1, f"Expected 1 anomaly, got {len(anoms)}"
    assert abs(float(anoms[0].amount) - 100.00) < 0.01
    assert "more than 2x the category average" in anoms[0].reason
    
    print("✓ Precomputed Subscriptions and Anomalies verification passed.")

async def test_fast_lane_execution(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Verify fast lane node executes deterministic template formatting correctly."""
    from app.agent.nodes import fast_lane_node
    
    await session.execute(delete(MonthlyCategoryRollup).where(MonthlyCategoryRollup.user_id == user_id))
    await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
    await session.commit()
    
    txn = {
        "date": date.today(),
        "amount": -45.50,
        "merchant": "Whole Foods",
        "category": "groceries",
        "currency": "USD"
    }
    await create_transaction(session, user_id, txn)
    await session.commit()
    
    state_spending = {
        "user_id": str(user_id),
        "message": "how much did I spend on groceries?",
        "system_instruction": "",
        "messages": [],
        "route": "fast_lane",
        "intent": "spending_query",
        "tool_parameters": {"categories": ["groceries"], "period": "monthly"}
    }
    res_spending = await fast_lane_node(state_spending)
    assert "spent" in res_spending["response"]
    assert "groceries" in res_spending["response"]
    assert "45.50" in res_spending["response"]
    
    print("✓ Fast Lane Execution verification passed.")

async def test_agent_react_and_declines(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Verify ReAct agent handles complex finance summaries and declines off-topic queries."""
    from app.agent.nodes import react_agent_node
    
    state_summary = {
        "user_id": str(user_id),
        "message": "can you summarize my monthly spending details?",
        "system_instruction": "",
        "messages": [],
        "route": "react",
        "intent": "finance_summary",
        "tool_parameters": {"period": "monthly"}
    }
    res_summary = await react_agent_node(state_summary)
    assert len(res_summary["response"]) > 0
    
    state_offtopic = {
        "user_id": str(user_id),
        "message": "what is the weather like in New York today?",
        "system_instruction": "",
        "messages": [],
        "route": "react",
        "intent": "out_of_domain",
        "tool_parameters": {}
    }
    res_offtopic = await react_agent_node(state_offtopic)
    assert "only" in res_offtopic["response"].lower() or "finance" in res_offtopic["response"].lower() or "unable" in res_offtopic["response"].lower()
    
    print("✓ ReAct Agent & Decline verification passed.")

async def main() -> None:
    """Orchestrate the verification tests."""
    print("Running verification checks...")
    await test_csv_parsing_and_quarantine()
    
    async with AsyncSessionLocal() as session:
        user1_id, user2_id = await setup_test_users(session)
        try:
            await test_ingestion_and_idempotency(session, user1_id)
            await test_mock_bank_data(session, user1_id)
            await test_single_row_crud_and_rollup_sync(session, user1_id)
            await test_budget_tracking(session, user1_id)
            await test_user_preferences(session, user1_id)
            await test_isolation(session, user1_id, user2_id)
            await test_chat_history_and_summarization(session, user1_id, user2_id)
            
            await test_agent_routing()
            await test_precomputed_subscriptions_and_anomalies(session, user1_id)
            await test_fast_lane_execution(session, user1_id)
            await test_agent_react_and_declines(session, user1_id)
            
            print("\nAll checks completed successfully!")
        finally:
            await cleanup_data(session, user1_id, user2_id)

if __name__ == "__main__":
    asyncio.run(main())

