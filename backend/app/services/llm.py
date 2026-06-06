import asyncio
from typing import AsyncGenerator, List, Dict
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class GeminiClient:
    """LLM service client managing interactions with Google GenAI SDK and mock fallbacks."""

    def __init__(self) -> None:
        """Initialize Client or configure mock mode based on configuration keys."""
        self.is_mock = (
            not settings.GEMINI_API_KEY or
            settings.GEMINI_API_KEY.startswith("dummy") or
            "placeholder" in settings.GEMINI_API_KEY
        )
        if not self.is_mock:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            logger.info("GeminiClient initialized in LIVE mode")
        else:
            logger.info("GeminiClient initialized in MOCK mode (no live API calls)")

    async def generate_chat_response_stream(
        self,
        messages: List[Dict[str, str]],
        system_instruction: str
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response for the chat thread."""
        if self.is_mock:
            logger.debug("generate_chat_response_stream — returning mock reply")
            reply = (
                "Hello! This is a mock response from the Personal Finance Assistant. "
                "I am running in mock mode because a dummy Gemini API key is configured. "
                "However, all chat message history, rolling summaries, and preferences are fully operational in the database!"
            )
            for word in reply.split(" "):
                yield f" {word}"
                await asyncio.sleep(0.04)
            return

        logger.debug("generate_chat_response_stream — calling Gemini API messages=%d", len(messages))
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])]
                )
            )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7
        )

        loop = asyncio.get_event_loop()
        try:
            response_stream = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content_stream(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=config
                )
            )
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            logger.error("Gemini streaming API error: %s", exc)
            yield f"\n[Error calling Gemini API: {str(exc)}. Falling back to mock responses.]"

    async def summarize(self, existing_summary: str, old_turns: List[Dict[str, str]]) -> str:
        """Produce a consolidated running summary of conversation history."""
        if self.is_mock:
            logger.debug("summarize — mock mode, skipping LLM call for %d turns", len(old_turns))
            return (
                f"Mock consolidated summary. Folded in {len(old_turns)} older conversation turns. "
                f"Previous summary was: '{existing_summary}'."
            )

        turns_text = "\n".join([f"{t['role']}: {t['content']}" for t in old_turns])
        prompt = (
            "Write a concise running summary of the conversation history so far, "
            "incorporating the new turns into the existing summary. Do not lose key facts "
            "about the user's preferences, pay cycle details, or budget constraints.\n\n"
            f"Existing Summary:\n{existing_summary}\n\n"
            f"New Turns to merge:\n{turns_text}"
        )

        loop = asyncio.get_event_loop()
        try:
            logger.debug("summarize — calling Gemini API for %d turns", len(old_turns))
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
            )
            return response.text.strip()
        except Exception as exc:
            logger.error("Gemini summarize API error: %s", exc)
            return f"Summary refresh failed due to API error: {str(exc)}"


llm_client = GeminiClient()
