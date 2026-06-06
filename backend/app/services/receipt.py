import asyncio
import base64
import json
from typing import Dict, Any
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.llm_config import llm_config
from app.core.logger import get_logger
from app.services.llm import llm_client

logger = get_logger(__name__)


class ReceiptParseResult(BaseModel):
    """Pydantic model representing structured receipt extraction fields."""
    merchant: str = Field(description="Name of the merchant/store")
    amount: float = Field(description="Total amount spent")
    date: str = Field(description="Date of the transaction in YYYY-MM-DD format")
    currency: str = Field(description="3-letter currency code, uppercase ISO format")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")


async def parse_receipt_image(image_base64: str, mime_type: str = "image/jpeg") -> Dict[str, Any]:
    """Parse receipt image using Gemini Vision API with structured JSON output, falling back to mock details."""
    if llm_client.is_mock:
        logger.debug("parse_receipt_image — returning mock result (mock mode)")
        return {
            "merchant": "Starbucks Coffee",
            "amount": 12.40,
            "date": "2026-06-03",
            "currency": "USD",
            "confidence": 0.95
        }

    logger.info("parse_receipt_image — calling Gemini Vision API mime_type=%s", mime_type)
    cleaned_base64 = image_base64
    if "," in image_base64:
        cleaned_base64 = image_base64.split(",")[1]

    image_bytes = base64.b64decode(cleaned_base64)

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt = (
        "Analyze this receipt image and extract the merchant name, total transaction amount, "
        "transaction date, currency (3 letter ISO code, default to USD if not specified), and your "
        "extraction confidence score (0.0 to 1.0). Return the response in strict JSON format."
    )

    loop = asyncio.get_event_loop()

    response = await loop.run_in_executor(
        None,
        lambda: client.models.generate_content(
            model=llm_config.model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ReceiptParseResult,
                temperature=0.1
            )
        )
    )

    result_text = response.text.strip()
    parsed = json.loads(result_text)
    logger.info(
        "Receipt parsed — merchant=%s amount=%.2f confidence=%.2f",
        parsed.get("merchant"), parsed.get("amount", 0), parsed.get("confidence", 0)
    )
    return parsed
