
import os
import uuid
from contextlib import asynccontextmanager
from datetime import date

import pymysql
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.ai.graph import build_graph
from app.tools.transaction_store import (
    get_balance,
    get_category_summary,
    get_transaction_summary,
    list_transactions,
)


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
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ------------------------------------------------------------------
# Request and response schemas
# ------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    thread_id: str | None = None


class ApprovalRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=200)
    approved: bool


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    approval_required: bool = False
    approval_request: dict | None = None


# ------------------------------------------------------------------
# Graph execution
# ------------------------------------------------------------------

def invoke_graph(thread_id: str, graph_input: dict | Command) -> dict:
    """Run the graph using a fresh MySQL connection."""
    connection = get_mysql_connection()

    try:
        checkpointer = PyMySQLSaver(connection)
        graph = build_graph(checkpointer)

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        return graph.invoke(graph_input, config=config)

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

def format_result(result: dict, thread_id: str) -> ChatResponse:
    """Convert a graph result into the frontend response format."""
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
    content = messages[-1].content if messages else ""

    if not isinstance(content, str):
        content = str(content)

    return ChatResponse(
        response=content,
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
def chat(request: ChatRequest) -> ChatResponse:
    """Process a chat message and return the assistant response."""
    thread_id = request.thread_id or str(uuid.uuid4())

    if not request.message.strip():
        raise HTTPException(
            status_code=422,
            detail="Message cannot be empty.",
        )

    try:
        if has_pending_approval(thread_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    "This conversation has a pending approval. "
                    "Please approve or reject it using /approval "
                    "before sending another message."
                ),
            )

        result = invoke_graph(
            thread_id,
            {
                "messages": [
                    HumanMessage(content=request.message)
                ]
            },
        )

        return format_result(result, thread_id)

    except HTTPException:
        raise

    except Exception as error:
        print(
            f"Chat request failed for thread_id={thread_id}: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "The chat request could not be completed. "
                "Please try again."
            ),
        ) from None


# ------------------------------------------------------------------
# Dashboard endpoint
# ------------------------------------------------------------------

@app.get("/dashboard/summary")
def dashboard_summary() -> dict:
    """Return financial summaries for the current month."""
    try:
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        today_str = today.isoformat()

        balance = get_balance()

        income = get_transaction_summary(
            transaction_type="income",
            start_date=month_start,
            end_date=today_str,
        )

        expenses = get_transaction_summary(
            transaction_type="expense",
            start_date=month_start,
            end_date=today_str,
        )

        categories = get_category_summary(
            start_date=month_start,
            end_date=today_str,
        )

        recent_transactions = list_transactions()[:5]

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
            f"Dashboard summary request failed: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "The dashboard summary could not be loaded. "
                "Please try again."
            ),
        ) from None


# ------------------------------------------------------------------
# Approval endpoint
# ------------------------------------------------------------------

@app.post("/approval", response_model=ChatResponse)
def handle_approval(request: ApprovalRequest) -> ChatResponse:
    """Resume a graph execution with the user's approval decision."""
    try:
        if not has_pending_approval(request.thread_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    "This conversation has no pending approval "
                    "to process."
                ),
            )

        result = invoke_graph(
            request.thread_id,
            Command(
                resume={
                    "approved": request.approved,
                }
            ),
        )

        return format_result(result, request.thread_id)

    except HTTPException:
        raise

    except Exception as error:
        print(
            f"Approval request failed for thread_id={request.thread_id}: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "The approval request could not be completed. "
                "Please try again."
            ),
        ) from None
