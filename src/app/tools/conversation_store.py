
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.conversation import Conversation


def get_or_create_conversation(
    db: Session,
    user_id: int,
) -> str:
    """Return the existing thread ID or create one for the user."""

    conversation = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .first()
    )

    if conversation:
        return conversation.thread_id

    conversation = Conversation(
        user_id=user_id,
        thread_id=str(uuid.uuid4()),
    )

    db.add(conversation)

    try:
        db.commit()
        db.refresh(conversation)

        return conversation.thread_id

    except IntegrityError:
        # Another simultaneous request may have created it.
        db.rollback()

        conversation = (
            db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .first()
        )

        if conversation:
            return conversation.thread_id

        raise
