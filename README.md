
# Spendly AI — Personal Expense Tracker

Spendly AI is an AI-powered personal finance tracker that helps users manage expenses and income through natural language conversations. It combines a conversational AI assistant with a financial dashboard backed by MySQL.

## Features

- **AI-Powered Chat:** Record income and expenses using natural language.
- **Transaction Management:** View, filter, update, and delete transactions.
- **Balance Tracking:** Calculate your current balance using recorded income and expenses.
- **Financial Summaries:** Calculate total income and expenses for specific date ranges.
- **Category Analysis:** Summarize expenses by category.
- **Monthly Comparison:** Compare current-month spending with the previous month.
- **Human-in-the-Loop (HITL):** Require approval before updating or deleting transactions.
- **Financial Dashboard API:** Retrieve balance, monthly income, expenses, category summaries, and recent transactions.
- **Persistent Conversations:** Store LangGraph checkpoints in MySQL and preserve frontend chat state in browser local storage.

## Tech Stack

### Backend
- Python
- FastAPI
- LangChain
- LangGraph
- ChatGroq
- SQLAlchemy
- MySQL 8
- PyMySQL
- Pydantic
- Uvicorn

### Frontend
- React
- Vite

## Project Structure

```text
AI-Expense-tracker/
├── src/
│   └── app/
│       ├── ai/
│       │   └── graph.py
│       ├── models/
│       │   └── transaction.py
│       ├── schemas/
│       │   └── intent.py
│       ├── tools/
│       │   ├── transaction_store.py
│       │   └── transaction_tools.py
│       ├── api.py
│       ├── database.py
│       └── main.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
├── .env
├── pyproject.toml
└── README.md
```

## Prerequisites

Install the following:

- Python 3.12 or a compatible version
- uv
- Node.js and npm
- MySQL 8
- Groq API key

## Environment Configuration

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
LLM_NAME=llama-3.3-70b-versatile

DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=ai_expense_tracker
```

Replace the example values with your own credentials. Never commit your `.env` file or expose your API key and database password.

Create the database in MySQL if it does not already exist:

```sql
CREATE DATABASE ai_expense_tracker;
```

## Installation and Setup

### 1. Install Backend Dependencies

Open PowerShell in the project root:

```powershell
cd D:\AI_projects\AI-Expense-tracker
uv sync
```

### 2. Start the Backend

```powershell
uv run uvicorn app.api:app --reload
```

The backend API runs at:

- API: http://127.0.0.1:8000
- Swagger documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

Keep this terminal running.

### 3. Install Frontend Dependencies

Open another PowerShell terminal:

```powershell
cd D:\AI_projects\AI-Expense-tracker\frontend
npm install
```

If Recharts is not already installed:

```powershell
npm install recharts
```

### 4. Start the Frontend

```powershell
npm run dev
```

Open the URL printed by Vite, usually:

http://localhost:5173

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Check API health |
| POST | `/chat` | Send a message to the AI assistant |
| POST | `/approval` | Approve or reject a pending operation |
| GET | `/dashboard/summary` | Retrieve financial dashboard data |

### Example: Chat Request

Send a POST request to `/chat`:

```json
{
  "message": "How much did I spend last week?"
}
```

The response includes the assistant's answer and a `thread_id`. Reuse that thread ID for subsequent messages in the same conversation.

### Example: Approval Request

When an update or deletion requires approval, submit the corresponding thread ID to `/approval`:

```json
{
  "thread_id": "your-thread-id",
  "approved": true
}
```

Use `true` to approve or `false` to reject the operation.

### Dashboard Summary

The `/dashboard/summary` endpoint provides:

- Current balance
- Monthly income
- Monthly expenses
- Monthly transaction count
- Expense totals by category
- Recent transactions
- Reporting period

The values come from the application's MySQL-backed transaction store.

## How It Works

1. The user enters a natural language request in the React frontend.
2. React sends the request to the FastAPI backend.
3. LangGraph manages the assistant workflow and tool execution.
4. ChatGroq interprets the user's intent and determines which available tool to use.
5. Transaction tools read or modify records in MySQL.
6. Sensitive update and deletion operations pause for human approval.
7. The backend returns the result to the frontend.
8. The dashboard API retrieves financial summaries from the transaction store.

The LLM interprets requests, while database-backed tools provide stored transaction records and calculated financial totals.

## Useful Commands

### Backend

Start the API:

```powershell
uv run uvicorn app.api:app --reload
```

Start the CLI assistant:

```powershell
uv run python -m app.main
```

### Frontend

Start development server:

```powershell
npm run dev
```

Create a production build:

```powershell
npm run build
```

## Troubleshooting

### MySQL Connection Errors
- Verify that the MySQL server is running.
- Check the database connection settings in `.env`.
- Confirm that the database exists and the configured user has access.

### Frontend Cannot Reach the Backend
- Confirm the backend is running on port `8000`.
- Check the browser console and backend terminal for errors.
- Verify that FastAPI CORS allows `http://localhost:5173`.

### Groq API Errors
- Verify the `GROQ_API_KEY` value.
- Confirm `LLM_NAME` is a supported model for your account.
- Check the backend terminal for provider error details.

### Pending Approval
Resolve a pending approval before sending another message on the same conversation thread.

## Security Considerations

- Never commit `.env` or publish credentials.
- Do not expose real financial records in public repositories.
- This project is currently intended for personal use.
- Before public deployment, implement appropriate authentication, authorization, rate limiting, and other production security controls.
- Browser local storage is not a secure vault; avoid using the application on shared or untrusted devices.

## Future Improvements

- Complete the dashboard UI with category charts and recent transaction views.
- Refresh dashboard figures after chat operations.
- Add transaction search and pagination.
- Add authentication if multi-user support is introduced.
- Add production deployment and monitoring.

## License

No license has been specified yet. Add a `LICENSE` file before distributing the project under an open-source license.
