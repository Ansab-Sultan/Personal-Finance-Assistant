from pydantic_settings import BaseSettings

class LLMConfig(BaseSettings):
    """Configuration class for LLM parameters overridable via environment variables."""
    model: str = "gemini-2.5-flash"
    router_max_tokens: int = 256
    react_max_tokens: int = 8192
    synthesizer_max_tokens: int = 8192
    router_temperature: float = 0.0
    react_temperature: float = 0.1
    synthesizer_temperature: float = 0.3

llm_config = LLMConfig()
