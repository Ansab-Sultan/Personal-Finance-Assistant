from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.nodes import router_node, fast_lane_node, react_agent_node, synthesizer_node

def build_graph() -> StateGraph:
    """Build and compile the conversational assistant LangGraph workflow."""
    builder = StateGraph(AgentState)
    
    builder.add_node("router", router_node)
    builder.add_node("fast_lane", fast_lane_node)
    builder.add_node("react_agent", react_agent_node)
    builder.add_node("synthesizer", synthesizer_node)
    
    builder.set_entry_point("router")
    
    def route_decision(state: AgentState) -> str:
        return state.get("route", "fast_lane")
        
    builder.add_conditional_edges(
        "router",
        route_decision,
        {
            "fast_lane": "fast_lane",
            "react": "react_agent"
        }
    )
    
    builder.add_edge("fast_lane", END)
    builder.add_edge("react_agent", "synthesizer")
    builder.add_edge("synthesizer", END)
    
    return builder.compile()

compiled_agent = build_graph()
