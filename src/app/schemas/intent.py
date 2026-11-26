
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


IntentType = Literal[
    "add_expense",
    "add_income",
    "query_expenses",
    "query_income",
    "query_balance",
    "query_transactions",
    "update_transaction",
    "delete_transaction",
    "general_question",
    "unclear",
]

Category = Literal[
    "Food",
    "Transport",
    "Shopping",
    "Bills",
    "Entertainment",
    "Health",
    "Education",
    "Travel",
    "Accommodation",
    "Groceries",
    "Salary",
    "Freelancing",
    "Business",
    "Investment",
    "Gift",
    "Other",
]


class TransactionItem(BaseModel):
    """One transaction mentioned in a user's message."""

    model_config = ConfigDict(extra="forbid")

    amount: float | None = Field(
        default=None,
        allow_inf_nan=False,
        description=(
            "Amount explicitly provided by the user. "
            "Preserve negative values. Return null if missing."
        ),
    )

    category: Category | None = Field(
        default=None,
        description=(
            "Transaction category explicitly supported by the "
            "user's message. Return null if missing."
        ),
    )

    description: str | None = Field(
        default=None,
        description=(
            "Description explicitly provided by the user. "
            "Do not invent one. Return null if missing."
        ),
    )

    transaction_date: str | None = Field(
        default=None,
        description=(
            "Date expression explicitly provided by the user, "
            "such as today, yesterday, or YYYY-MM-DD. "
            "Never default to today. Return null if missing."
        ),
    )


class TransactionIntent(BaseModel):
    """Structured interpretation of the user's complete message."""

    model_config = ConfigDict(extra="forbid")

    intent: IntentType

    transactions: list[TransactionItem] = Field(
        default_factory=list,
        description="All distinct transactions mentioned by the user.",
    )

    clarification_needed: bool = Field(
        default=False,
        description=(
            "True when the user's request needs clarification "
            "before it can be processed."
        ),
    )

    clarification_question: str | None = Field(
        default=None,
        description=(
            "Ask specifically for missing or ambiguous information. "
            "Return null when clarification is unnecessary."
        ),
    )
