import asyncio
import json
from typing import Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core.llm_config import llm_config
from app.core.logger import get_logger
from app.agent.state import AgentState
from app.agent import tools

from google import genai
from google.genai import types

logger = get_logger(__name__)

class RouterOutput(BaseModel):
    """Pydantic model representing structured classification output from the router.

    The tool_parameters field is a JSON-encoded string to avoid additionalProperties
    in the schema, which is unsupported by the Gemini Developer API.
    """
    route: str = Field(description="Must be either 'fast_lane' or 'react'")
    intent: str = Field(description="Identified intent, e.g. spending_query, budget_check, user_memory_write, temporal_comparison, finance_summary, subscriptions_read, anomalies_read, receipt_ocr, cutback_suggestion, merchant_lookup, out_of_domain")
    tool_parameters: str = Field(default="{}", description="JSON-encoded string of extracted parameters for the tool, e.g. '{\"category\": \"groceries\", \"period\": \"monthly\"}'")

class AgentStepOutput(BaseModel):
    """Pydantic model representing a single step of reasoning in the ReAct loop.

    The action_input field is a JSON-encoded string to avoid additionalProperties
    in the schema, which is unsupported by the Gemini Developer API.
    """
    thought: str = Field(description="The model's current reasoning about what to do next")
    action: str = Field(description="The name of the tool to execute, or 'none' if finished")
    action_input: str = Field(default="{}", description="JSON-encoded string of parameters to pass to the tool, e.g. '{\"categories\": [\"groceries\"], \"period\": \"monthly\"}'")
    final_answer: str = Field(default="", description="The final plain English answer to the user")

async def router_node(state: AgentState) -> Dict[str, Any]:
    """Classify the user intent and extract query parameters, routing to either fast_lane or react."""
    msg = state.get("message", "").strip()
    user_id = state.get("user_id", "?")

    logger.info("router_node invoked — user_id=%s message_len=%d", user_id, len(msg))

    if state.get("image_base64"):
        logger.debug("router_node — image detected, routing to fast_lane:receipt_ocr")
        return {
            "route": "fast_lane",
            "intent": "receipt_ocr",
            "tool_parameters": {
                "image_base64": state["image_base64"],
                "image_name": state.get("image_name") or "receipt.jpg"
            }
        }
        
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    prompt = (
        "You are the routing and parameter extraction module of a personal finance assistant.\n"
        f"Analyze the user's message: '{msg}'\n"
        f"Available preferences context: {state.get('system_instruction', '')}\n\n"
        "Classify the intent into one of the following:\n"
        "- 'spending_query': Calculating spending totals for SPECIFIC categories and periods.\n"
        "- 'budget_check': Comparing spending vs limit for a category.\n"
        "- 'user_memory_write': Setting/saving a preference key (e.g. pay date, exclusions).\n"
        "- 'temporal_comparison': Comparing spending between two periods.\n"
        "- 'finance_summary': Category-wise rollup totals breakdown.\n"
        "- 'transactions_list': User wants to see or list their recent transactions (no specific category filter).\n"
        "- 'subscriptions_read': Reading detected subscriptions.\n"
        "- 'anomalies_read': Reading flagged transaction anomalies.\n"
        "- 'cutback_suggestion': Recommendations on where to cut back.\n"
        "- 'merchant_lookup': Looking up details for a merchant.\n"
        "- 'out_of_domain': Off-topic questions (weather, general knowledge).\n\n"
        "Routing Decision Rules:\n"
        "- Route to 'fast_lane' ONLY for simple lookups ('spending_query', 'budget_check', 'user_memory_write', 'temporal_comparison', 'subscriptions_read', 'anomalies_read', 'transactions_list') where a template can display the answer.\n"
        "- Route to 'react' for complex reasoning ('cutback_suggestion', 'merchant_lookup', 'finance_summary', 'out_of_domain', or multi-part/ambiguous requests).\n\n"
        "IMPORTANT: If the user asks to list, show, or see their transactions without specifying a category or spending amount, use 'transactions_list'.\n"
        "Extract appropriate tool parameters (e.g. category, period, categories, merchant, key, value, action).\n"
        "If the query is out of range or unanswerable, classify the intent but set parameters accordingly."
    )
    
    if llm_config.model == "mock" or (settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.startswith("dummy")):
        intent = "spending_query"
        route = "fast_lane"
        params = {"categories": ["groceries"], "period": "monthly"}
        if "budget" in msg.lower():
            intent = "budget_check"
            params = {"category": "groceries", "period": "monthly"}
        elif "cutback" in msg.lower() or "cut back" in msg.lower():
            intent = "cutback_suggestion"
            route = "react"
        elif "summary" in msg.lower() or "summarize" in msg.lower():
            intent = "finance_summary"
            route = "react"
            params = {"period": "monthly"}
        elif "remember" in msg.lower() or "preference" in msg.lower() or "exclude" in msg.lower():
            intent = "user_memory_write"
            params = {"action": "write", "key": "exclude_from_food", "value": "groceries"}
        elif "compare" in msg.lower() or "vs" in msg.lower():
            intent = "temporal_comparison"
            route = "fast_lane"
            params = {"category": "groceries", "period_a": "2026-06", "period_b": "2026-05"}
        elif "subscription" in msg.lower():
            intent = "subscriptions_read"
            route = "fast_lane"
            params = {}
        elif "anomaly" in msg.lower() or "anomalies" in msg.lower():
            intent = "anomalies_read"
            route = "fast_lane"
            params = {}
        elif "transaction" in msg.lower() or "show" in msg.lower() or "list" in msg.lower():
            intent = "transactions_list"
            route = "fast_lane"
            params = {"limit": 5}
        return {
            "route": route,
            "intent": intent,
            "tool_parameters": params
        }

        

    loop = asyncio.get_event_loop()
    
    response = await loop.run_in_executor(
        None,
        lambda: client.models.generate_content(
            model=llm_config.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RouterOutput,
                temperature=0.0
            )
        )
    )
    
    result = json.loads(response.text.strip())
    raw_params = result.get("tool_parameters") or "{}"
    if isinstance(raw_params, str):
        try:
            parsed_params = json.loads(raw_params)
        except (json.JSONDecodeError, ValueError):
            parsed_params = {}
    else:
        parsed_params = raw_params
    logger.info(
        "router_node classified — user_id=%s route=%s intent=%s",
        user_id, result["route"], result["intent"]
    )
    return {
        "route": result["route"],
        "intent": result["intent"],
        "tool_parameters": parsed_params
    }

async def fast_lane_node(state: AgentState) -> Dict[str, Any]:
    """Execute a single database tool directly and format the result using a template."""
    intent = state.get("intent")
    params = state.get("tool_parameters", {})
    user_id = UUID(state["user_id"])

    logger.info("fast_lane_node invoked — user_id=%s intent=%s", user_id, intent)

    async with AsyncSessionLocal() as session:
        if intent == "spending_query":
            cats = params.get("categories") or params.get("category")
            if isinstance(cats, str):
                cats = [cats]
            if not cats:
                cats = ["groceries"]
            period = params.get("period") or "monthly"
            
            res = await tools.spending_query_tool(session, user_id, cats, period)
            cats_str = ", ".join(cats)
            ans = f"You spent **${res['total_spent']:.2f}** on **{cats_str}** this {period}."
            return {"response": ans}
            
        elif intent == "budget_check":
            cat = params.get("category") or "groceries"
            period = params.get("period") or "monthly"
            
            res = await tools.budget_tracker_tool(session, user_id, cat, period)
            if res["state"] == "not_configured":
                ans = f"You don't have a **{cat}** budget configured for this period. However, you have spent **${res['spent']:.2f}** on **{cat}**."
            else:
                ans = (
                    f"Your budget status for **{cat}** ({period}) is **{res['state'].upper()}**. "
                    f"Spent: **${res['spent']:.2f}** of limit **${res['limit']:.2f}**. "
                    f"Remaining: **${res['remaining']:.2f}**."
                )
            return {"response": ans}
            
        elif intent == "user_memory_write" or intent == "user_memory":
            act = params.get("action") or "write"
            key = params.get("key")
            val = params.get("value")
            
            res = await tools.user_memory_tool(session, user_id, act, key, val)
            if "error" in res:
                return {"response": f"Failed: {res['error']}"}
            if act == "write":
                ans = f"Saved preference **{key}** to **{val}**."
            elif act == "read":
                ans = f"Preference keys configured: {res}"
            else:
                ans = f"Preference key deleted: {res.get('success')}"
            return {"response": ans}
            
        elif intent == "temporal_comparison":
            cat = params.get("category") or "groceries"
            period_a = params.get("period_a") or date.today().strftime("%Y-%m")
            period_b = params.get("period_b") or (date.today() - timedelta(days=30)).strftime("%Y-%m")
            
            res = await tools.temporal_comparison_tool(session, user_id, cat, period_a, period_b)
            ans = (
                f"Spending on **{cat}** was **${res['amount_a']:.2f}** in {period_a} and **${res['amount_b']:.2f}** in {period_b}. "
                f"Difference: **${res['difference']:.2f}** ({res['percentage_change']:+.1f}%)."
            )
            return {"response": ans}
            
        elif intent == "subscriptions_read":
            res = await tools.subscription_detector_tool(session, user_id)
            subs = res["subscriptions"]
            if not subs:
                ans = "I found no detected recurring subscriptions in your transaction history."
            else:
                lines = ["Here are your detected recurring subscriptions:"]
                for s in subs:
                    lines.append(f"- **{s['merchant']}**: ${s['amount']:.2f}/month (confidence: {s['confidence']:.0%})")
                ans = "\n".join(lines)
            return {"response": ans}
            
        elif intent == "anomalies_read":
            res = await tools.anomaly_detector_tool(session, user_id)
            anoms = res["anomalies"]
            if not anoms:
                ans = "I found no flagged anomalies in your transactions."
            else:
                lines = ["Here are your flagged anomalies:"]
                for a in anoms:
                    lines.append(f"- **{a['category']}**: ${a['amount']:.2f} — *{a['reason']}*")
                ans = "\n".join(lines)
            return {"response": ans}

        elif intent == "transactions_list":
            limit = int(params.get("limit") or 5)
            res = await tools.transactions_list_tool(session, user_id, limit)
            txns = res["transactions"]
            if not txns:
                ans = "You have no transactions yet."
            else:
                lines = [f"Here are your last {len(txns)} transactions:"]
                for t in txns:
                    sign = "+" if t["amount"] >= 0 else "-"
                    lines.append(f"- **{t['merchant']}** ({t['category']}) on {t['date']}: {sign}${abs(t['amount']):.2f} {t['currency']}")
                ans = "\n".join(lines)
            return {"response": ans}
            
        elif intent == "receipt_ocr":
            base64_data = params.get("image_base64")
            name = params.get("image_name") or "receipt.jpg"
            res = await tools.receipt_ocr_tool(session, user_id, base64_data, name)
            if not res.get("success"):
                return {"response": f"Failed to parse receipt image: {res.get('error')}"}
            p = res["parsed_data"]
            ans = (
                f"I parsed the receipt from **{p['merchant']}** for **${p['amount']:.2f} {p['currency']}** "
                f"dated **{p['date']}** (confidence: {p['confidence']:.0%}). "
                f"Would you like me to record this transaction?"
            )
            return {"response": ans}
            
        return {"response": "No matching template found."}

async def react_agent_node(state: AgentState) -> Dict[str, Any]:
    """Execute a structured ReAct loop using the LLM, invoking tools iteratively to form a final narrated response."""
    user_id = UUID(state["user_id"])
    logger.info("react_agent_node invoked — user_id=%s intent=%s", user_id, state.get("intent"))

    if llm_config.model == "mock" or (settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.startswith("dummy")):
        intent = state.get("intent")
        if intent == "cutback_suggestion":
            return {"response": "Based on your spending, I suggest cutbacks in **dining out** by 15% to save **$15.00**."}
        elif intent == "finance_summary":
            return {"response": "This month you spent **$150.00** total. Income was **$2500.00**."}
        elif intent == "merchant_lookup":
            return {"response": "Uber is a ride-sharing and food delivery service app."}
        return {"response": "I am unable to answer this off-topic query. Please ask me about personal finance."}
        
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    tool_results = {}
    conversation_history = "\n".join([f"{m['role']}: {m['content']}" for m in state.get("messages", [])])
    
    system_prompt = (
        f"{state.get('system_instruction', '')}\n"
        "You are a helpful personal finance ReAct assistant. You solve user queries by running tools, "
        "observing results, and producing a final plain English summary. Respond inside the structured schema.\n\n"
        "Available Tools:\n"
        "- spending_query_tool(categories: List[str], period: str)\n"
        "- budget_tracker_tool(category: str, period: str)\n"
        "- user_memory_tool(action: str, key: str, value: str)\n"
        "- finance_summary_tool(period: str)\n"
        "- temporal_comparison_tool(category: str, period_a: str, period_b: str)\n"
        "- subscription_detector_tool()\n"
        "- anomaly_detector_tool()\n"
        "- cutback_suggestion_tool()\n"
        "- merchant_lookup_tool(merchant: str)\n\n"
        "Instructions:\n"
        "- If the query is off-topic or out-of-domain, immediately populate final_answer stating you only handle finance, with action='none'.\n"
        "- Use the tools sequentially. Set 'action' to the tool name and populate 'action_input' with JSON parameters.\n"
        "- Observe the tool result in the next cycle, thought again, and call another tool or produce the final_answer."
    )
    
    async with AsyncSessionLocal() as session:
        for step in range(5):
            history_prompt = (
                f"User Message: {state['message']}\n\n"
                f"Conversation history:\n{conversation_history}\n\n"
                f"Tool results so far: {tool_results}\n\n"
                "Plan your next step."
            )
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=llm_config.model,
                    contents=[
                        types.Content(role="user", parts=[types.Part.from_text(text=history_prompt)])
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        response_schema=AgentStepOutput,
                        temperature=0.1
                    )
                )
            )
            
            res = json.loads(response.text.strip())
            action = res.get("action", "none").strip()
            logger.debug(
                "react_agent_node step %d — user_id=%s action=%s",
                step, user_id, action
            )

            if action == "none" or not action:
                return {"response": res.get("final_answer", "")}

            raw_args = res.get("action_input") or "{}"
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except (json.JSONDecodeError, ValueError):
                    args = {}
            else:
                args = raw_args
            
            try:
                if action == "spending_query_tool":
                    cats = args.get("categories") or [args.get("category", "groceries")]
                    p = args.get("period", "monthly")
                    val = await tools.spending_query_tool(session, user_id, cats, p)
                elif action == "budget_tracker_tool":
                    cat = args.get("category", "groceries")
                    p = args.get("period", "monthly")
                    val = await tools.budget_tracker_tool(session, user_id, cat, p)
                elif action == "user_memory_tool":
                    act = args.get("action", "read")
                    k = args.get("key")
                    v = args.get("value")
                    val = await tools.user_memory_tool(session, user_id, act, k, v)
                elif action == "finance_summary_tool":
                    p = args.get("period", "monthly")
                    val = await tools.finance_summary_tool(session, user_id, p)
                elif action == "temporal_comparison_tool":
                    cat = args.get("category", "groceries")
                    pa = args.get("period_a") or date.today().strftime("%Y-%m")
                    pb = args.get("period_b") or (date.today() - timedelta(days=30)).strftime("%Y-%m")
                    val = await tools.temporal_comparison_tool(session, user_id, cat, pa, pb)
                elif action == "subscription_detector_tool":
                    val = await tools.subscription_detector_tool(session, user_id)
                elif action == "anomaly_detector_tool":
                    val = await tools.anomaly_detector_tool(session, user_id)
                elif action == "cutback_suggestion_tool":
                    val = await tools.cutback_suggestion_tool(session, user_id)
                elif action == "merchant_lookup_tool":
                    m = args.get("merchant", "")
                    val = await tools.merchant_lookup_tool(m)
                else:
                    val = {"error": f"Tool '{action}' not found"}
            except Exception as e:
                val = {"error": f"Tool execution failed: {str(e)}"}
                logger.error("react_agent_node tool error — user_id=%s action=%s error=%s", user_id, action, e)

            tool_results[action] = val
            logger.debug("react_agent_node tool result — action=%s result_keys=%s", action, list(val.keys()) if isinstance(val, dict) else "?")

        logger.warning("react_agent_node timed out — user_id=%s", user_id)
        return {"response": "ReAct agent timed out. Please try a simpler question."}

async def synthesizer_node(state: AgentState) -> Dict[str, Any]:
    """Pass-through node representing response synthesis."""
    user_id = state.get("user_id", "?")
    resp = state.get("response", "")
    logger.debug("synthesizer_node — user_id=%s response_len=%d", user_id, len(resp))
    return {"response": resp}
