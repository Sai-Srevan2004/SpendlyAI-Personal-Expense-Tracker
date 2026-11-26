
import os
from contextlib import asynccontextmanager
from datetime import date

import pymysql
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.graph import build_graph
from app.auth.dependencies import get_current_user
from app.auth.routes import router as auth_router
from app.database import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.tools.conversation_store import get_or_create_conversation

from app.tools.transaction_store import (
    get_balance,
    get_category_summary,
    get_transaction_summary,
    list_transactions,
)
import traceback

load_dotenv(override=True)


# ------------------------------------------------------------------
# Database connection
# ------------------------------------------------------------------

def get_mysql_connection():
    """Create a MySQL connection using environment configuration."""
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "ai_expense_tracker"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=10,
        init_command="SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
    )


# ------------------------------------------------------------------
# Application lifecycle
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize graph checkpoint tables at startup."""
    connection = None

    try:
        connection = get_mysql_connection()
        checkpointer = PyMySQLSaver(connection)
        checkpointer.setup()

        print("MySQL checkpoint initialization completed.")

    except Exception as error:
        print(
            f"Application startup failed: "
            f"{type(error).__name__}: {error}"
        )
        raise

    finally:
        if connection is not None:
            connection.close()

    yield

    print("Application shutdown completed.")


app = FastAPI(
    title="AI Expense Tracker API",
    description="Manage personal finances through an AI assistant.",
    version="0.1.0",
    lifespan=lifespan,
)


app.include_router(auth_router)


# ------------------------------------------------------------------
# CORS
# ------------------------------------------------------------------

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Request and response schemas
# ------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class ApprovalRequest(BaseModel):
    approved: bool


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    approval_required: bool = False
    approval_request: dict | None = None


# ------------------------------------------------------------------
# Graph execution
# ------------------------------------------------------------------

def invoke_graph(
    thread_id: str,
    graph_input: dict | Command,
    user_id: int,
) -> dict:
    """Run the graph with authenticated user context."""
    connection = get_mysql_connection()

    try:
        checkpointer = PyMySQLSaver(connection)
        graph = build_graph(checkpointer)

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        return graph.invoke(
            graph_input,
            config=config,
            context={
                "user_id": user_id,
            },
        )

    finally:
        connection.close()


def has_pending_approval(thread_id: str) -> bool:
    """Check whether this conversation is waiting for approval."""
    connection = get_mysql_connection()

    try:
        checkpointer = PyMySQLSaver(connection)
        graph = build_graph(checkpointer)

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        state = graph.get_state(config)

        return any(task.interrupts for task in state.tasks)

    finally:
        connection.close()


# ------------------------------------------------------------------
# Graph result formatting
# ------------------------------------------------------------------

def extract_message_text(content) -> str:
    """Extract readable text from LangChain message content."""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []

        for block in content:
            if isinstance(block, str):
                text_parts.append(block)

            elif isinstance(block, dict):
                if block.get("type") == "text":
                    text = block.get("text", "")
                    if isinstance(text, str):
                        text_parts.append(text)

        return "\n".join(text_parts).strip()

    return ""


def format_result(result: dict, thread_id: str) -> ChatResponse:
    """Convert the final graph response into the API response."""

    interrupts = result.get("__interrupt__", [])

    if interrupts:
        approval_request = interrupts[0].value

        return ChatResponse(
            response=(
                "Your approval is required before this operation "
                "can proceed."
            ),
            thread_id=thread_id,
            approval_required=True,
            approval_request=approval_request,
        )

    messages = result.get("messages", [])

    # Find the latest assistant message containing a final response.
    for message in reversed(messages):
        if not isinstance(message, AIMessage):
            continue

        # Skip intermediate tool-call messages.
        if message.tool_calls:
            continue

        content = extract_message_text(message.content)

        if content:
            return ChatResponse(
                response=content,
                thread_id=thread_id,
            )

    return ChatResponse(
        response="I couldn't generate a response. Please try again.",
        thread_id=thread_id,
    )



# ------------------------------------------------------------------
# Health endpoint
# ------------------------------------------------------------------

@app.get("/health")
def health_check() -> dict:
    """Report whether the API process is responding."""
    return {"status": "ok"}


# ------------------------------------------------------------------
# Chat endpoint
# ------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Process a chat message for the authenticated user."""

    if not request.message.strip():
        raise HTTPException(
            status_code=422,
            detail="Message cannot be empty.",
        )

    thread_id = get_or_create_conversation(
        db=db,
        user_id=current_user.id,
    )

    try:
        if has_pending_approval(thread_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    "This conversation has a pending approval. "
                    "Please resolve it before sending another message."
                ),
            )

        result = invoke_graph(
            thread_id=thread_id,
            graph_input={
                "messages": [
                    HumanMessage(content=request.message)
                ]
            },
            user_id=current_user.id,
        )

        return format_result(result, thread_id)

    except HTTPException:
        raise

    except Exception as error:
        print(
            f"Chat request failed for user_id={current_user.id}: "
            f"{type(error).__name__}: {error}"
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="The chat request could not be completed.",
        ) from None


# ------------------------------------------------------------------
# Dashboard endpoint
# ------------------------------------------------------------------

@app.get("/dashboard/summary")
def dashboard_summary(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return financial summaries for the authenticated user."""

    try:
        user_id = current_user.id

        today = date.today()
        month_start = today.replace(day=1).isoformat()
        today_str = today.isoformat()

        balance = get_balance(user_id)

        income = get_transaction_summary(
            user_id=user_id,
            transaction_type="income",
            start_date=month_start,
            end_date=today_str,
        )

        expenses = get_transaction_summary(
            user_id=user_id,
            transaction_type="expense",
            start_date=month_start,
            end_date=today_str,
        )

        categories = get_category_summary(
            user_id=user_id,
            start_date=month_start,
            end_date=today_str,
        )

        recent_transactions = list_transactions(
            user_id=user_id,
        )[:5]

        return {
            "balance": balance,
            "monthly_income": income["total"],
            "monthly_expenses": expenses["total"],
            "monthly_transaction_count": (
                income["count"] + expenses["count"]
            ),
            "expense_categories": categories,
            "recent_transactions": recent_transactions,
            "period": {
                "start_date": month_start,
                "end_date": today_str,
            },
        }

    except Exception as error:
        print(
            f"Dashboard summary failed for user_id={current_user.id}: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="The dashboard summary could not be loaded.",
        ) from None


# ------------------------------------------------------------------
# Approval endpoint
# ------------------------------------------------------------------

@app.post("/approval", response_model=ChatResponse)
def handle_approval(
    request: ApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Resume only the authenticated user's conversation."""

    conversation = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    thread_id = conversation.thread_id

    try:
        if not has_pending_approval(thread_id):
            raise HTTPException(
                status_code=409,
                detail="This conversation has no pending approval.",
            )

        result = invoke_graph(
            thread_id=thread_id,
            graph_input=Command(
                resume={
                    "approved": request.approved,
                }
            ),
            user_id=current_user.id,
        )

        return format_result(result, thread_id)

    except HTTPException:
        raise

    except Exception as error:
        print(
            f"Approval request failed for user_id={current_user.id}: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="The approval request could not be completed.",
        ) from None
