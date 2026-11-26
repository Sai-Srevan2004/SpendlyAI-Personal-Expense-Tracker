
from app.database import Base, engine
from app.models import (
    User,
    Transaction,
    Conversation,
    RefreshSession,
)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    print("Spendly AI database tables created successfully.")


if __name__ == "__main__":
    init_db()
