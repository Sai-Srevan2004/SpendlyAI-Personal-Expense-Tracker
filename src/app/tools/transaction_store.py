
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy import delete, func, select

from app.database import SessionLocal
from app.models.transaction import Transaction
from app.schemas.intent import TransactionItem



def parse_transaction_date(value: str | None) -> date:
    """Parse a date explicitly provided for a transaction."""

    if value is None or not value.strip():
        raise ValueError("Transaction date is required.")

    normalized = value.strip().lower()

    relative_dates = {
        "today": date.today(),
        "yesterday": date.today() - timedelta(days=1),
        "tomorrow": date.today() + timedelta(days=1),
    }

    if normalized in relative_dates:
        return relative_dates[normalized]

    try:
        parsed = date.fromisoformat(normalized)

        if parsed.isoformat() != normalized:
            raise ValueError

        return parsed

    except ValueError as error:
        raise ValueError(
            "Invalid date. Use YYYY-MM-DD, today, yesterday, or tomorrow."
        ) from error



def transaction_to_dict(transaction: Transaction) -> dict:
    return {
        "id": transaction.id,
        "type": transaction.type,
        "amount": float(transaction.amount),
        "category": transaction.category,
        "description": transaction.description,
        "date": transaction.transaction_date.isoformat(),
    }


def add_transactions(
    user_id: int,
    items: list[TransactionItem],
    transaction_type: str,
) -> list[dict]:
    if transaction_type not in {"expense", "income"}:
        raise ValueError("Invalid transaction type.")

    if not items:
        raise ValueError("At least one transaction is required.")

    transactions = []

    for item in items:
        try:
            amount = Decimal(str(item.amount))
        except (InvalidOperation, ValueError, TypeError) as error:
            raise ValueError("Amount must be a valid number.") from error

        if not amount.is_finite() or amount <= 0:
            raise ValueError("Amount must be a finite positive number.")

        if not item.category or not item.category.strip():
            raise ValueError("Category cannot be empty.")

        if not item.description or not item.description.strip():
            raise ValueError("Description cannot be empty.")

        transactions.append(
            Transaction(
                id=str(uuid4()),
                user_id=user_id,
                type=transaction_type,
                amount=amount,
                category=item.category.strip(),
                description=item.description.strip(),
                transaction_date=parse_transaction_date(
                    item.transaction_date
                ),
            )
        )

    with SessionLocal() as session:
        try:
            session.add_all(transactions)
            session.commit()

            return [
                transaction_to_dict(transaction)
                for transaction in transactions
            ]
        except Exception:
            session.rollback()
            raise


def resolve_date_range(
    date_filter: str | None,
) -> tuple[date | None, date | None]:
    if not date_filter:
        return None, None

    today = date.today()
    value = date_filter.strip().lower()

    if value == "today":
        return today, today

    if value == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday

    if value == "this month":
        return today.replace(day=1), today

    if value == "last month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end

    if value == "this week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)

    if value == "last week":
        this_week_start = today - timedelta(days=today.weekday())
        end = this_week_start - timedelta(days=1)
        return end - timedelta(days=6), end

    raise ValueError(
        "Unsupported date filter. Use today, yesterday, this week, "
        "last week, this month, or last month."
    )


def get_date_bounds(
    date_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[date | None, date | None]:
    filter_start, filter_end = resolve_date_range(date_filter)

    def parse_custom_date(value: str) -> date:
        try:
            normalized = value.strip()
            parsed = date.fromisoformat(normalized)

            if parsed.isoformat() != normalized:
                raise ValueError

            return parsed
        except (ValueError, AttributeError) as error:
            raise ValueError(
                "Invalid date. Use YYYY-MM-DD format."
            ) from error

    if start_date:
        filter_start = parse_custom_date(start_date)

    if end_date:
        filter_end = parse_custom_date(end_date)

    if filter_start and filter_end and filter_start > filter_end:
        raise ValueError("Start date cannot be later than end date.")

    return filter_start, filter_end


def apply_date_filters(
    statement,
    filter_start: date | None,
    filter_end: date | None,
):
    if filter_start:
        statement = statement.where(
            Transaction.transaction_date >= filter_start
        )

    if filter_end:
        statement = statement.where(
            Transaction.transaction_date <= filter_end
        )

    return statement


def list_transactions(
    user_id: int,
    transaction_type: str | None = None,
    category: str | None = None,
    date_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    filter_start, filter_end = get_date_bounds(
        date_filter, start_date, end_date
    )

    with SessionLocal() as session:
        statement = select(Transaction).where(
            Transaction.user_id == user_id
        )

        if transaction_type:
            statement = statement.where(
                Transaction.type == transaction_type
            )

        if category:
            statement = statement.where(
                func.lower(Transaction.category)
                == category.strip().lower()
            )

        statement = apply_date_filters(
            statement, filter_start, filter_end
        )

        statement = statement.order_by(
            Transaction.created_at.desc()
        )

        transactions = session.scalars(statement).all()

        return [
            transaction_to_dict(transaction)
            for transaction in transactions
        ]


def get_transaction(
    user_id: int,
    transaction_id: str,
) -> dict | None:
    with SessionLocal() as session:
        transaction = session.scalar(
            select(Transaction).where(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id,
            )
        )

        if transaction is None:
            return None

        return transaction_to_dict(transaction)


def get_balance(user_id: int) -> float:
    with SessionLocal() as session:
        income = session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.user_id == user_id,
                Transaction.type == "income",
            )
        )

        expenses = session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.user_id == user_id,
                Transaction.type == "expense",
            )
        )

        return float(Decimal(str(income)) - Decimal(str(expenses)))


def update_transaction(
    user_id: int,
    transaction_id: str,
    amount: float | None = None,
    category: str | None = None,
    description: str | None = None,
    transaction_date: str | None = None,
) -> dict | None:
    with SessionLocal() as session:
        try:
            transaction = session.scalar(
                select(Transaction).where(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id,
                )
            )

            if transaction is None:
                return None

            if amount is not None:
                try:
                    parsed_amount = Decimal(str(amount))
                except (InvalidOperation, ValueError, TypeError) as error:
                    raise ValueError("Invalid amount.") from error

                if not parsed_amount.is_finite() or parsed_amount <= 0:
                    raise ValueError(
                        "Amount must be a finite positive number."
                    )

                transaction.amount = parsed_amount

            if category is not None:
                if not category.strip():
                    raise ValueError("Category cannot be empty.")
                transaction.category = category.strip()

            if description is not None:
                if not description.strip():
                    raise ValueError("Description cannot be empty.")
                transaction.description = description.strip()

            if transaction_date is not None:
                transaction.transaction_date = parse_transaction_date(
                    transaction_date
                )

            session.commit()
            session.refresh(transaction)

            return transaction_to_dict(transaction)

        except Exception:
            session.rollback()
            raise


def delete_transaction(
    user_id: int,
    transaction_id: str,
) -> dict | None:
    with SessionLocal() as session:
        try:
            transaction = session.scalar(
                select(Transaction).where(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id,
                )
            )

            if transaction is None:
                return None

            result = transaction_to_dict(transaction)

            session.delete(transaction)
            session.commit()

            return result

        except Exception:
            session.rollback()
            raise


def clear_transactions(user_id: int) -> None:
    with SessionLocal() as session:
        try:
            session.execute(
                delete(Transaction).where(
                    Transaction.user_id == user_id
                )
            )
            session.commit()
        except Exception:
            session.rollback()
            raise


def get_transaction_summary(
    user_id: int,
    transaction_type: str = "expense",
    date_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    filter_start, filter_end = get_date_bounds(
        date_filter, start_date, end_date
    )

    with SessionLocal() as session:
        statement = select(
            func.coalesce(func.sum(Transaction.amount), 0),
            func.count(Transaction.id),
        ).where(
            Transaction.user_id == user_id,
            Transaction.type == transaction_type,
        )

        statement = apply_date_filters(
            statement, filter_start, filter_end
        )

        total, count = session.execute(statement).one()

        return {
            "type": transaction_type,
            "total": float(total),
            "count": count,
            "start_date": (
                filter_start.isoformat() if filter_start else None
            ),
            "end_date": (
                filter_end.isoformat() if filter_end else None
            ),
        }


def get_category_summary(
    user_id: int,
    date_filter: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    filter_start, filter_end = get_date_bounds(
        date_filter, start_date, end_date
    )

    with SessionLocal() as session:
        statement = (
            select(
                Transaction.category,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.type == "expense",
            )
            .group_by(Transaction.category)
            .order_by(func.sum(Transaction.amount).desc())
        )

        statement = apply_date_filters(
            statement, filter_start, filter_end
        )

        rows = session.execute(statement).all()

        return [
            {
                "category": category,
                "total": float(total),
                "count": count,
            }
            for category, total, count in rows
        ]


def compare_monthly_transactions(
    user_id: int,
    transaction_type: str = "expense",
) -> dict:
    today = date.today()
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    with SessionLocal() as session:
        base_statement = select(
            func.sum(Transaction.amount),
            func.count(Transaction.id),
        ).where(
            Transaction.user_id == user_id,
            Transaction.type == transaction_type,
        )

        current_total, current_count = session.execute(
            base_statement.where(
                Transaction.transaction_date >= this_month_start,
                Transaction.transaction_date <= today,
            )
        ).one()

        previous_total, previous_count = session.execute(
            base_statement.where(
                Transaction.transaction_date >= last_month_start,
                Transaction.transaction_date <= last_month_end,
            )
        ).one()

        current_total = Decimal(str(current_total or 0))
        previous_total = Decimal(str(previous_total or 0))

        difference = current_total - previous_total

        percentage_change = (
            difference / previous_total * Decimal("100")
            if previous_total != 0
            else None
        )

        return {
            "type": transaction_type,
            "this_month": {
                "start_date": this_month_start.isoformat(),
                "end_date": today.isoformat(),
                "total": float(current_total),
                "count": current_count,
            },
            "last_month": {
                "start_date": last_month_start.isoformat(),
                "end_date": last_month_end.isoformat(),
                "total": float(previous_total),
                "count": previous_count,
            },
            "difference": float(difference),
            "percentage_change": (
                float(percentage_change)
                if percentage_change is not None
                else None
            ),
        }
