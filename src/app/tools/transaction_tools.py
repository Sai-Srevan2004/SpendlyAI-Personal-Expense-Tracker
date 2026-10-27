
from langchain_core.tools import tool

from app.schemas.intent import TransactionItem

from langgraph.types import interrupt

from datetime import date

from app.tools.transaction_store import (
    get_transaction_summary,
    add_transactions,
    get_balance,
    list_transactions,
    update_transaction as update_transaction_record,
    delete_transaction as delete_transaction_record,
    get_category_summary,
    compare_monthly_transactions
)



def validate_batch(transactions: list[dict]) -> list[TransactionItem]:
    """Validate every transaction before saving any of them."""
    if not transactions:
        raise ValueError("At least one transaction is required.")

    items = [
        TransactionItem.model_validate(transaction)
        for transaction in transactions
    ]

    for item in items:
        if item.amount is None or item.amount <= 0:
            raise ValueError(
                "Every transaction must have a positive amount."
            )

        if not item.category:
            raise ValueError(
                "Every transaction needs a category."
            )

        if not item.description or not item.description.strip():
            raise ValueError(
                "Every transaction needs a description."
            )

    return items


def validate_transaction_update(
    amount: float | None = None,
    category: str | None = None,
    description: str | None = None,
) -> str | None:
    """Validate supplied transaction update fields."""

    if amount is not None and amount <= 0:
        return "Amount must be greater than zero."

    if category is not None and not category.strip():
        return "Category cannot be empty."

    if description is not None and not description.strip():
        return "Description cannot be empty."

    return None

def validate_transaction_date(
    transaction_date: str | None,
) -> str | None:
    """Validate supported transaction date formats."""

    if transaction_date is None:
        return None

    normalized_date = transaction_date.strip().lower()

    if normalized_date in {"today", "yesterday", "tomorrow"}:
        return None

    try:
        date.fromisoformat(normalized_date)
    except (ValueError, TypeError):
        return (
            "Invalid transaction date. Use YYYY-MM-DD, "
            "today, yesterday, or tomorrow."
        )

    return None

@tool
def record_expenses(transactions: list[dict]) -> dict:
    """Record one or more personal expenses."""
    items = validate_batch(transactions)
    created = add_transactions(items, "expense")

    return {
        "success": True,
        "count": len(created),
        "transactions": created,
    }


@tool
def record_income(transactions: list[dict]) -> dict:
    """Record one or more personal income transactions."""
    items = validate_batch(transactions)
    created = add_transactions(items, "income")

    return {
        "success": True,
        "count": len(created),
        "transactions": created,
    }



@tool
def get_transactions(
    transaction_type: str = "all",
    category: str | None = None,
    date_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Retrieve transactions filtered by type, category, and date.

    date_filter supports today, yesterday, this week, last week,
    this month, or last month.
    Use start_date and end_date for a custom date range in YYYY-MM-DD format.
    """
    if transaction_type not in {"all", "expense", "income"}:
        return {
            "success": False,
            "error": "Use all, expense, or income.",
        }

    try:
        selected_type = (
            None if transaction_type == "all" else transaction_type
        )

        transactions = list_transactions(
            transaction_type=selected_type,
            category=category,
            date_filter=date_filter,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "success": True,
            "count": len(transactions),
            "transactions": transactions,
        }

    except (ValueError, TypeError) as error:
        return {
            "success": False,
            "error": str(error),
        }


@tool
def calculate_balance() -> dict:
    """Calculate recorded income minus recorded expenses."""
    return {
        "success": True,
        "balance": get_balance(),
    }



@tool
def update_transaction_tool(
    transaction_id: str,
    amount: float | None = None,
    category: str | None = None,
    description: str | None = None,
    transaction_date: str | None = None,
) -> dict:
    """Update a transaction only after the user confirms the proposed changes."""

    if all(
        value is None
        for value in (amount, category, description, transaction_date)
    ):
        return {
            "success": False,
            "error": "Provide at least one field to update.",
        }

    
    validation_error = validate_transaction_update(
        amount=amount,
        category=category,
        description=description,
    )

    if validation_error:
        return {
            "success": False,
            "error": validation_error,
        }

    date_error = validate_transaction_date(transaction_date)

    if date_error:
        return {
            "success": False,
            "error": date_error,
        }


    transactions = list_transactions()
    existing = next(
        (item for item in transactions if item["id"] == transaction_id),
        None,
    )

    if existing is None:
        return {
            "success": False,
            "error": "Transaction not found. Retrieve transactions first.",
        }

    changes = {
        key: value
        for key, value in {
            "amount": amount,
            "category": category,
            "description": description,
            "date": transaction_date,
        }.items()
        if value is not None
    }

    # Pause the graph and wait for the user's decision.
    decision = interrupt({
        "action": "update_transaction",
        "transaction": existing,
        "proposed_changes": changes,
        "message": "Approve these transaction changes?",
    })

    if not isinstance(decision, dict) or decision.get("approved") is not True:
        return {
            "success": False,
            "cancelled": True,
            "message": "Transaction update cancelled.",
        }

    updated = update_transaction_record(
        transaction_id=transaction_id,
        amount=amount,
        category=category,
        description=description,
        transaction_date=transaction_date,
    )

    if updated is None:
        return {
            "success": False,
            "error": "Transaction no longer exists.",
        }

    return {
        "success": True,
        "message": "Transaction updated successfully.",
        "transaction": updated,
    }


@tool
def delete_transaction_tool(transaction_id: str) -> dict:
    """Delete a transaction only after the user confirms its deletion."""

    transactions = list_transactions()
    existing = next(
        (item for item in transactions if item["id"] == transaction_id),
        None,
    )

    if existing is None:
        return {
            "success": False,
            "error": "Transaction not found. Retrieve transactions first.",
        }

    # Pause the graph before deleting anything.
    decision = interrupt({
        "action": "delete_transaction",
        "transaction": existing,
        "message": "Approve deletion of this transaction?",
    })

    if not isinstance(decision, dict) or decision.get("approved") is not True:
        return {
            "success": False,
            "cancelled": True,
            "message": "Transaction deletion cancelled.",
        }

    deleted = delete_transaction_record(transaction_id)

    if deleted is None:
        return {
            "success": False,
            "error": "Transaction no longer exists.",
        }

    return {
        "success": True,
        "message": "Transaction deleted successfully.",
        "transaction": deleted,
    }


@tool
def summarize_transactions(
    transaction_type: str = "expense",
    date_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Calculate the total amount and count of income or expenses.

    Use this for questions such as:
    - How much did I spend this month?
    - How much income did I earn last week?
    - What were my total expenses between two dates?

    transaction_type must be expense or income.
    date_filter supports today, yesterday, this week, last week,
    this month, or last month.
    Use start_date and end_date for a custom date range (YYYY-MM-DD).
    """
    if transaction_type not in {"expense", "income"}:
        return {
            "success": False,
            "error": "transaction_type must be expense or income.",
        }

    try:
        summary = get_transaction_summary(
            transaction_type=transaction_type,
            date_filter=date_filter,
            start_date=start_date,
            end_date=end_date,
        )

        return {"success": True, **summary}

    except (ValueError, TypeError) as error:
        return {"success": False, "error": str(error)}



@tool
def summarize_expenses_by_category(
    date_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Break down expenses by category for a date range.

    Use for questions about spending by category or the biggest
    spending category. Supports today, yesterday, this week,
    last week, this month, and last month.
    """
    try:
        categories = get_category_summary(
            date_filter=date_filter,
            start_date=start_date,
            end_date=end_date,
        )
        return {
            "success": True,
            "categories": categories,
        }
    except (ValueError, TypeError) as error:
        return {"success": False, "error": str(error)}


@tool
def compare_monthly_summary(
    transaction_type: str = "expense",
) -> dict:
    """Compare this month's and last month's income or expenses."""
    if transaction_type not in {"expense", "income"}:
        return {
            "success": False,
            "error": "transaction_type must be expense or income.",
        }

    try:
        result = compare_monthly_transactions(transaction_type)
        return {"success": True, **result}
    except (ValueError, TypeError) as error:
        return {"success": False, "error": str(error)}
