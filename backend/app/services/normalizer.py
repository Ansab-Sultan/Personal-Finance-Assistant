from datetime import date, datetime
from typing import Any, Dict, List, Optional
import re

CANONICAL_CATEGORIES = {
    "groceries",
    "restaurants",
    "transport",
    "fuel",
    "utilities",
    "rent",
    "health",
    "entertainment",
    "shopping",
    "subscriptions",
    "travel",
    "education",
    "income",
    "transfer",
    "uncategorized"
}

CATEGORY_MAPPING = {
    "restaurant": "restaurants",
    "dining": "restaurants",
    "cafe": "restaurants",
    "food": "restaurants",
    "supermarket": "groceries",
    "grocery": "groceries",
    "rent": "rent",
    "mortgage": "rent",
    "housing": "rent",
    "uber": "transport",
    "taxi": "transport",
    "transportation": "transport",
    "fuel": "fuel",
    "gas": "fuel",
    "electric": "utilities",
    "water": "utilities",
    "internet": "utilities",
    "netflix": "subscriptions",
    "spotify": "subscriptions",
    "movie": "entertainment",
    "pharmacy": "health",
    "doctor": "health",
    "hospital": "health",
    "healthcare": "health",
    "subscription": "subscriptions",
    "travel": "travel",
    "flight": "travel",
    "hotel": "travel",
    "education": "education",
    "tuition": "education",
    "course": "education",
    "income": "income",
    "salary": "income",
    "payout": "income",
    "transfer": "transfer",
    "wire": "transfer"
}

def parse_date(date_str: str) -> date:
    """Parse a date string from various common formats into a datetime.date object."""
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {date_str}")

def parse_amount(amount_str: str) -> float:
    """Parse an amount string, removing currency symbols, commas and whitespace."""
    clean_str = re.sub(r"[^\d\.\-]", "", amount_str.strip())
    if not clean_str:
        raise ValueError(f"Could not parse amount: {amount_str}")
    return float(clean_str)

def normalize_category(raw_category: str) -> str:
    """Map a raw category string to a canonical category."""
    if not raw_category:
        return "uncategorized"
    
    clean_cat = raw_category.strip().lower()
    if clean_cat in CANONICAL_CATEGORIES:
        return clean_cat
        
    for keyword, mapped in CATEGORY_MAPPING.items():
        if keyword in clean_cat:
            return mapped
            
    return "uncategorized"

def normalize_transaction_data(raw_data: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Normalize raw transaction dictionary fields to the canonical transaction schema."""
    date_val = parse_date(str(raw_data.get("date")))
    amount_val = parse_amount(str(raw_data.get("amount")))
    
    merchant = str(raw_data.get("merchant", "")).strip()
    raw_desc = str(raw_data.get("description", raw_data.get("raw_description", ""))).strip()
    if not merchant:
        merchant = raw_desc if raw_desc else "Unknown Merchant"
        
    category = normalize_category(str(raw_data.get("category", "")))
    currency = str(raw_data.get("currency", "USD")).strip().upper()
    if not re.match(r"^[A-Z]{3}$", currency):
        currency = "USD"
        
    return {
        "date": date_val,
        "amount": amount_val,
        "currency": currency,
        "merchant": merchant,
        "raw_description": raw_desc or merchant,
        "category": category,
        "source": source
    }
