
import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from app.schemas.intent import TransactionIntent

load_dotenv()

model = ChatGroq(
    model=os.getenv("LLM_NAME", "llama-3.3-70b-versatile"),
    temperature=0,
)

extractor = model.with_structured_output(TransactionIntent)

SYSTEM_PROMPT = """
You interpret messages for a personal expense and income tracker.

Your job is to extract user-provided information accurately.
Never invent, assume, or silently fill missing information.

TRANSACTION EXTRACTION RULES:

1. Extract every distinct transaction mentioned.
2. Each transaction must be a separate list item.
3. Never invent an amount, category, description, or date.
4. If a field is not explicitly provided, return None for that field.
5. Never use today's date as a default.
6. Only use today's date when the user explicitly says "today".
7. Preserve relative dates such as yesterday and tomorrow.
8. Preserve negative amounts as negative. Never convert -500 into 500.
9. Zero, negative, NaN, and infinite amounts must not be treated as valid.
10. Never use the category itself as an invented description.
11. Never create a description just because the user says
    "add one yourself" or "decide yourself".
12. Never assume missing information from previous transactions.

REQUIRED TRANSACTION INFORMATION:

Every new transaction requires:
- Amount
- Category
- Description
- Transaction date

If any required information is missing, the application must
ask the user for the missing information before recording.

CATEGORY RULES:

Expense categories:
Food, Transport, Shopping, Bills, Entertainment, Health,
Education, Travel, Accommodation, Groceries, Other.

Income categories:
Salary, Freelancing, Business, Investment, Gift, Other.

Hotel or lodging expenses should normally use Accommodation.

INTENT RULES:

- Questions about spending, income, balance, or history are queries.
- Requests to change or delete transactions are not new transactions.
- If wording could mean one or multiple transactions, ask for clarification.
- If an essential amount is missing, ask for it.
- Preserve the association between each amount and its description.
- Do not combine separate transactions.
- Do not assume identical amounts refer to the same transaction.

FINANCIAL ACCURACY:

- Never calculate authoritative financial totals.
- Never claim a transaction was saved, updated, or deleted.
- Never treat an invalid amount as a valid transaction.

DATE RULES:

- Preserve the exact date expression provided by the user.
- Missing date must remain None.
- Do not infer a date from the conversation timestamp.
- Do not convert an unspecified date into today.

Return only information supported by the user's message.
"""


def extract_intent(message: str) -> TransactionIntent:
    """Convert a user message into a structured interpretation."""

    if not message or not message.strip():
        raise ValueError("Message cannot be empty.")

    return extractor.invoke(
        [
            ("system", SYSTEM_PROMPT),
            ("human", message.strip()),
        ]
    )
