
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.ai.context import SpendlyContext

from app.tools.transaction_tools import (
    calculate_balance,
    delete_transaction_tool,
    get_transactions,
    record_expenses,
    record_income,
    update_transaction_tool,
    summarize_transactions,
    compare_monthly_summary,
    summarize_expenses_by_category,
)

load_dotenv()

model = ChatGroq(
    model=os.getenv("LLM_NAME", "llama-3.3-70b-versatile"),
    temperature=0,
)

tools = [
    record_expenses,
    record_income,
    get_transactions,
    calculate_balance,
    update_transaction_tool,
    delete_transaction_tool,
    summarize_transactions,
    compare_monthly_summary,
    summarize_expenses_by_category,
]

model_with_tools = model.bind_tools(tools)


SYSTEM_PROMPT = """
You are Spendly AI, a reliable personal finance assistant.

CURRENT DATE:
{current_date}

TRANSACTION RECORDING RULES:

1. Required fields for every transaction:
   - Amount
   - Category
   - Description
   - Transaction date

2. Never invent, assume, or automatically fill a missing field.

3. Never convert a negative amount into a positive amount.

4. Negative and zero amounts are invalid for both income and expenses.

5. If any required field is missing, ask the user for that field.
   Do not call a recording tool until every field is provided.

6. Never use today's date automatically.

7. Only use today's date when the user explicitly says:
   "today", "use today's date", "take today date", or equivalent.

8. When the user explicitly says today, use CURRENT DATE above.

9. Accept explicit relative dates such as yesterday and tomorrow
   only when the user provides them.

10. NEVER treat "add it yourself" as permission to invent
    an amount, category, description, or date.

11. Preserve pending transaction information across clarification turns.

12. When a user answers a clarification question:
    - Read the earlier pending transaction from conversation history.
    - Preserve all previously supplied valid fields.
    - Update only the field the user has clarified.
    - Ask only for the remaining missing fields.

13. Never start a new transaction when the user is answering
    a clarification question about an existing transaction.

14. For multiple transactions, every transaction must be complete
    before calling a recording tool. Never partially record a batch.

AVAILABLE TOOLS:

- record_expenses: Record expenses.
- record_income: Record income.
- get_transactions: Retrieve transactions.
- calculate_balance: Calculate balance.
- update_transaction_tool: Update with human approval.
- delete_transaction_tool: Delete with human approval.
- summarize_transactions: Calculate financial totals.
- summarize_expenses_by_category: Category breakdown.
- compare_monthly_summary: Monthly comparison.

TOOL RULES:

- Use the appropriate tool for stored financial information.
- Never claim an operation succeeded unless the tool confirms it.
- If a tool returns success=False, explain the failure.
- Never retry with invented or modified transaction details.
- Respect the authenticated user's data isolation.
- Updating and deleting require human approval.

CONVERSATION RULES:

- Understand the complete conversation history.
- Do not ask for information already supplied.
- Do not invent missing information.
- Keep clarification questions short.
- If the user asks what happened, explain the pending transaction
  and its remaining missing fields.

RESPONSE FORMATTING:

- Use concise Markdown.
- Use ₹ for Indian Rupee amounts.
- Use tables for multiple transaction records.
- Never expose internal implementation details.
- Never claim a database operation succeeded without confirmation.

Financial accuracy is more important than completing a transaction.
"""


def is_negative_transaction_request(message: str) -> bool:
    """Detect explicitly negative monetary amounts in transaction requests."""

    text = message.lower()

    transaction_keywords = (
        "income",
        "expense",
        "spent",
        "spend",
        "received",
        "earned",
        "salary",
        "transaction",
        "record",
        "add",
    )

    if not any(keyword in text for keyword in transaction_keywords):
        return False

    negative_patterns = [
        r"(?<!\w)-\s*(?:₹\s*)?\d+(?:,\d{3})*(?:\.\d+)?",
        r"₹\s*-\s*\d+(?:,\d{3})*(?:\.\d+)?",
    ]

    return any(re.search(pattern, text) for pattern in negative_patterns)


def call_model(state: MessagesState) -> dict:
    """Call the LLM with conversation history and transaction safeguards."""

    messages = state["messages"]

    if messages and isinstance(messages[-1], HumanMessage):
        user_message = messages[-1].content

        if isinstance(user_message, str) and is_negative_transaction_request(
            user_message
        ):
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I cannot record a negative transaction amount. "
                            "Please provide a positive amount."
                        )
                    )
                ]
            }

    current_date = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).date().isoformat()

    system_message = SystemMessage(
        content=SYSTEM_PROMPT.format(current_date=current_date)
    )

    response = model_with_tools.invoke(
        [system_message, *messages]
    )

    return {"messages": [response]}


def build_graph(checkpointer: BaseCheckpointSaver):
    """Build the assistant graph with persistent checkpointing."""

    builder = StateGraph(
        MessagesState,
        context_schema=SpendlyContext,
    )

    builder.add_node("assistant", call_model)
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "assistant")

    builder.add_conditional_edges(
        "assistant",
        tools_condition,
        {
            "tools": "tools",
            END: END,
        },
    )

    builder.add_edge("tools", "assistant")

    return builder.compile(checkpointer=checkpointer)
