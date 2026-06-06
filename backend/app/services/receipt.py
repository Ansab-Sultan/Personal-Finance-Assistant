import base64
from typing import Dict, Any
from pydantic import BaseModel, Field
from google.genai import types
from app.core.config import settings
from app.services.llm import llm_client

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
        return {
            "merchant": "Starbucks Coffee",
            "amount": 12.40,
            "date": "2026-06-03",
            "currency": "USD",
            "confidence": 0.95
        }
        
    cleaned_base64 = image_base64
    if "," in image_base64:
        cleaned_base64 = image_base64.split(",")[1]
        
    image_bytes = base64.b64decode(cleaned_base64)
    
    from google import genai
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    prompt = (
        "Analyze this receipt image and extract the merchant name, total transaction amount, "
        "transaction date, currency (3 letter ISO code, default to USD if not specified), and your "
        "extraction confidence score (0.0 to 1.0). Return the response in strict JSON format."
    )
    
    import asyncio
    loop = asyncio.get_event_loop()
    
    response = await loop.run_in_executor(
        None,
        lambda: client.models.generate_content(
            model="gemini-2.5-flash",
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
    
    import json
    result_text = response.text.strip()
    return json.loads(result_text)
