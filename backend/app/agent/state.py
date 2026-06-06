from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    """The graph state representing our conversational assistant context."""
    user_id: str
    message: str
    image_base64: Optional[str]
    image_name: Optional[str]
    system_instruction: str
    messages: List[Dict[str, str]]
    route: str
    intent: str
    tool_parameters: Dict[str, Any]
    tool_results: Dict[str, Any]
    response: str
