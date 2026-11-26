
from decimal import Decimal, InvalidOperation

from langchain.tools import tool, ToolRuntime
from langgraph.types import interrupt

from app.schemas.intent import TransactionItem
from app.tools.transaction_store import (
    add_transactions,
    get_transaction,
    get_balance,
    list_transactions,
    update_transaction as update_transaction_record,
    delete_transaction as delete_transaction_record,
    get_transaction_summary,
    get_category_summary,
    compare_monthly_transactions,
    get_date_bounds,
    parse_transaction_date,
)


def get_user_id(runtime: ToolRuntime) -> int:
    """Get the authenticated user ID from trusted runtime context."""

    user_id = runtime.context.get("user_id")

    if user_id is None:
        raise ValueError("Authenticated user context is missing.")

    return int(user_id)


def parse_positive_amount(value) -> Decimal:
    """Validate a finite positive transaction amount."""

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Amount must be a valid number.")

    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    return amount


def validate_batch(transactions: list[dict]) -> list[TransactionItem]:
    """Validate every transaction before allowing database insertion."""

    if not transactions:
        raise ValueError("At least one transaction is required.")

    validated_items = []

    for index, transaction in enumerate(transactions, start=1):
        if not isinstance(transaction, dict):
            raise ValueError(
                f"Transaction {index} must be a valid object."
            )

        missing_fields = []

        if transaction.get("amount") is None:
            missing_fields.append("amount")

        if not transaction.get("category"):
            missing_fields.append("category")

        if not transaction.get("description") or not str(
            transaction.get("description")
        ).strip():
            missing_fields.append("description")

        if not transaction.get("transaction_date") or not str(
            transaction.get("transaction_date")
        ).strip():
            missing_fields.append("date")

        if missing_fields:
            raise ValueError(
                f"Transaction {index} is missing: "
                f"{', '.join(missing_fields)}. "
                "Ask the user to provide these details. "
                "Do not invent them."
            )

        amount = parse_positive_amount(transaction["amount"])

        try:
            item = TransactionItem.model_validate(transaction)
        except Exception as error:
            raise ValueError(
                f"Transaction {index} has invalid information: {error}"
            ) from error

        if not item.category:
            raise ValueError(
                f"Transaction {index} needs a category."
            )

        if not item.description or not item.description.strip():
            raise ValueError(
                f"Transaction {index} needs a description."
            )

        if not item.transaction_date:
            raise ValueError(
                f"Transaction {index} needs a date."
            )

        try:
            parse_transaction_date(item.transaction_date)
        except ValueError as error:
            raise ValueError(
                f"Transaction {index}: {error}"
            ) from error

        item.amount = float(amount)
        item.category = item.category
        item.description = item.description.strip()

        validated_items.append(item)

    return validated_items


def validate_transaction_update(
    amount: float | None = None,
    category: str | None = None,
    description: str | None = None,
    transaction_date: str | None = None,
) -> None:
    """Validate optional transaction update fields."""

    if all(
        value is None
        for value in (amount, category, description, transaction_date)
    ):
        raise ValueError("Provide at least one field to update.")

    if amount is not None:
        parse_positive_amount(amount)

    if category is not None and not category.strip():
        raise ValueError("Category cannot be empty.")

    if description is not None and not description.strip():
        raise ValueError("Description cannot be empty.")

    if transaction_date is not None:
        if not transaction_date.strip():
            raise ValueError("Date cannot be empty.")

        parse_transaction_date(transaction_date)


def validate_date_range(
    date_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> None:
    """Validate optional date filters."""

    get_date_bounds(date_filter, start_date, end_date)


@tool
def record_expenses(
    transactions: list[dict],
    runtime: ToolRuntime,
) -> dict:
    """Record one or more personal expenses."""

    try:
        user_id = get_user_id(runtime)
        items = validate_batch(transactions)

        saved = add_transactions(
            user_id=user_id,
            items=items,
            transaction_type="expense",
        )

        return {
            "success": True,
            "message": "Expenses recorded successfully.",
            "transactions": saved,
        }

    except (ValueError, TypeError) as error:
        return {
            "success": False,
            "message": str(error),
            "transactions": [],
        }


@tool
def record_income(
    transactions: list[dict],
    runtime: ToolRuntime,
) -> dict:
    """Record one or more personal income transactions."""

    try:
        user_id = get_user_id(runtime)
        items = validate_batch(transactions)

        saved = add_transactions(
            user_id=user_id,
            items=items,
            transaction_type="income",
        )

        return {
            "success": True,
            "message": "Income recorded successfully.",
            "transactions": saved,
        }

    except (ValueError, TypeError) as error:
        return {
            "success": False,
            "message": str(error),
            "transactions": [],
        }


@tool
def get_transactions(
    runtime: ToolRuntime,
    transaction_type: str | None = None,
    category: str | None = None,
    date_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Retrieve the authenticated user's transactions."""

    try:
        user_id = get_user_id(runtime)

        if transaction_type not in (None, "expense", "income"):
            raise ValueError("Invalid transaction type.")

        validate_date_range(date_filter, start_date, end_date)

        transactions = list_transactions(
            user_id=user_id,
            transaction_type=transaction_type,
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
            "message": str(error),
            "transactions": [],
        }


@tool
def calculate_balance(runtime: ToolRuntime) -> dict:
    """Calculate the authenticated user's current balance."""

    try:
        user_id = get_user_id(runtime)

        return {
            "success": True,
            "balance": get_balance(user_id),
        }

    except (ValueError, TypeError) as error:
        return {
            "success": False,
            "message": str(error),
        }


@tool
def update_transaction_tool(
    transaction_id: str,
    runtime: ToolRuntime,
    amount: float | None = None,
    category: str | None = None,
    description: str | None = None,
    transaction_date: str | None = None,
) -> dict:
    """Update a transaction after user approval."""

    try:
        user_id = get_user_id(runtime)

        validate_transaction_update(
            amount=amount,
            category=category,
            description=description,
            transaction_date=transaction_date,
        )

        existing = get_transaction(user_id, transaction_id)

        if existing is None:
            return {
                "success": False,
                "message": "Transaction not found.",
            }

        approval = interrupt(
            {
                "action": "update_transaction",
                "transaction": existing,
                "changes": {
                    "amount": amount,
                    "category": category,
                    "description": description,
                    "transaction_date": transaction_date,
                },
                "message": "Please approve or reject this update.",
            }
        )

        approved = (
            approval is True
            or (
                isinstance(approval, dict)
                and approval.get("approved") is True
            )
        )

        if not approved:
            return {
                "success": False,
                "message": "Transaction update rejected.",
            }

        updated = update_transaction_record(
            user_id=user_id,
            transaction_id=transaction_id,
            amount=amount,
            category=category,
            description=description,
            transaction_date=transaction_date,
        )

        if updated is None:
            return {
                "success": False,
                "message": "Transaction not found.",
            }

        return {
            "success": True,
            "message": "Transaction updated successfully.",
            "transaction": updated,
        }

    except (ValueError, TypeError) as error:
        return {
            "success": False,
            "message": str(error),
        }


@tool
def delete_transaction_tool(
    transaction_id: str,
    runtime: ToolRuntime,
) -> dict:
    """Delete a transaction after user approval."""

    try:
        user_id = get_user_id(runtime)

        existing = get_transaction(user_id, transaction_id)

        if existing is None:
            return {
                "success": False,
                "message": "Transaction not found.",
            }

        approval = interrupt(
            {
                "action": "delete_transaction",
                "transaction": existing,
                "message": "Please approve or reject this deletion.",
            }
        )

        approved = (
            approval is True
            or (
                isinstance(approval, dict)
                and approval.get("approved") is True
            )
        )

        if not approved:
            return {
                "success": False,
                "message": "Transaction deletion rejected.",
            }

        deleted = delete_transaction_record(
            user_id=user_id,
            transaction_id=transaction_id,
        )

        if deleted is None:
            return {
                "success": False,
                "message": "Transaction not found.",
            }

        return {
            "success": True,
            "message": "Transaction deleted successfully.",
            "transaction": deleted,
        }

    except (ValueError, TypeError) as error:
        return {
            "success": False,
            "message": str(error),
        }


@tool
def summarize_transactions(
    runtime: ToolRuntime,
    transaction_type: str = "expense",
    date_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Summarize the authenticated user's income or expenses."""

    try:
        user_id = get_user_id(runtime)

        if transaction_type not in ("expense", "income"):
            raise ValueError("Invalid transaction type.")

        validate_date_range(date_filter, start_date, end_date)

        summary = get_transaction_summary(
            user_id=user_id,
            transaction_type=transaction_type,
            date_filter=date_filter,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "success": True,
            "summary": summary,
        }

    except (ValueError, TypeError) as error:
        return {
            "success": False,
            "message": str(error),
        }


@tool
def summarize_expenses_by_category(
    runtime: ToolRuntime,
    date_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Summarize the authenticated user's expenses by category."""

    try:
        user_id = get_user_id(runtime)

        validate_date_range(date_filter, start_date, end_date)

        summary = get_category_summary(
            user_id=user_id,
            date_filter=date_filter,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "success": True,
            "categories": summary,
        }

    except (ValueError, TypeError) as error:
        return {
            "success": False,
            "message": str(error),
        }


@tool
def compare_monthly_summary(
    runtime: ToolRuntime,
    transaction_type: str = "expense",
) -> dict:
    """Compare the user's current month with the previous month."""

    try:
        user_id = get_user_id(runtime)

        if transaction_type not in ("expense", "income"):
            raise ValueError("Invalid transaction type.")

        comparison = compare_monthly_transactions(
            user_id=user_id,
            transaction_type=transaction_type,
        )

        return {
            "success": True,
            "comparison": comparison,
        }

    except (ValueError, TypeError) as error:
        return {
            "success": False,
            "message": str(error),
        }
