# Spendly AI — AI-Powered Personal Finance Tracker

Spendly AI is an AI-powered personal finance management application that allows users to track income and expenses through natural language conversations.

It combines a conversational AI assistant with a financial dashboard, backed by MySQL. The application supports multiple users, with authentication and user-specific data isolation to ensure that each user can access only their own financial records and conversation history.

Built using FastAPI, LangGraph, ChatGroq, React, and MySQL, Spendly AI provides transaction management, financial summaries, balance tracking, and human-in-the-loop approval for sensitive operations.

## Features

- **User Authentication:** User registration and login with password hashing and JWT-based authentication.
- **Multi-User Support:** Multiple users can maintain independent financial records and conversations.
- **AI-Powered Chat:** Record income and expenses using natural language.
- **Transaction Management:** View, filter, update, and delete transactions.
- **Balance Tracking:** Calculate current balance using recorded income and expenses.
- **Financial Summaries:** Calculate total income and expenses for specific date ranges.
- **Category Analysis:** Summarize expenses by category.
- **Monthly Comparison:** Compare current-month spending with the previous month.
- **Human-in-the-Loop (HITL):** Require user approval before updating or deleting transactions.
- **Financial Dashboard API:** Retrieve balance, monthly income, expenses, category summaries, and recent transactions.
- **Persistent Conversations:** Maintain one persistent conversation per user using LangGraph checkpoints stored in MySQL.
- **Refresh Token Management:** Support access-token renewal and refresh-session management.

## Tech Stack

### Backend

- Python 3.12
- FastAPI
- LangChain
- LangGraph
- ChatGroq
- SQLAlchemy
- MySQL 8
- PyMySQL
- Pydantic
- Uvicorn
- JWT Authentication
- Argon2 Password Hashing

### Frontend

- React
- Vite

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

JWT_SECRET_KEY=your_long_random_secret_key
JWT_ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

CORS_ORIGINS=http://localhost:5173
```

Replace the example values with your own credentials. Never commit your `.env` file or expose your API key, database password, or JWT secret.

Create the database in MySQL if it does not already exist:

```sql
CREATE DATABASE ai_expense_tracker;
```

## Installation and Setup

### 1. Install Backend Dependencies

Open PowerShell in the project root:

```powershell
cd D:\AI\Projects\AI-Expense-tracker
uv sync
```

### 2. Start the Backend

```powershell
uv run uvicorn app.api:app --reload
```

The backend API runs at:

- API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Swagger documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

Keep this terminal running.

### 3. Install Frontend Dependencies

Open another PowerShell terminal:

```powershell
cd D:\AI\Projects\AI-Expense-tracker\frontend
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

Open the URL printed by Vite, usually [http://localhost:5173](http://localhost:5173).

## Authentication and Multi-User Architecture

Spendly AI supports multiple authenticated users.

### Authentication Flow

- Users register with their account details and password.
- Passwords are securely hashed using Argon2.
- Users authenticate through JWT-based login.
- Short-lived access tokens authorize protected API requests.
- Refresh tokens are stored as hashed sessions in MySQL and managed through refresh-token rotation.
- Refresh tokens are delivered through an HttpOnly cookie.

### User Data Isolation

Each user's financial data is associated with their authenticated user ID.

- Users can access only their own transactions.
- Transaction queries and modifications are scoped to the authenticated user.
- Each user has one persistent conversation.
- LangGraph uses a user-specific thread ID to maintain conversation history.
- The frontend does not choose or supply another user's conversation thread ID.
- Authenticated user context is passed to backend tools so database operations remain scoped to the correct user.

## API Endpoints

| Method | Endpoint             | Description                           |
| ------ | -------------------- | ------------------------------------- |
| GET    | `/health`            | Check API health                      |
| POST   | `/chat`              | Send a message to the AI assistant    |
| POST   | `/approval`          | Approve or reject a pending operation |
| GET    | `/dashboard/summary` | Retrieve financial dashboard data     |
| POST   | `/auth/register`     | Register a user                       |
| POST   | `/auth/login`        | Authenticate a user                   |
| POST   | `/auth/refresh`      | Refresh an access token               |
| POST   | `/auth/logout`       | Log out and revoke a refresh session  |

Authentication endpoint paths should match the routes implemented in `app/auth/routes.py`.

### Example: Chat Request

Send a POST request to `/chat`:

```json
{
  "message": "How much did I spend last week?"
}
```

The backend authenticates the user and retrieves their persistent conversation. The frontend does not need to submit a thread ID.

### Example: Approval Request

When an update or deletion requires approval, submit a request to `/approval`:

```json
{
  "approved": true
}
```

Use `true` to approve or `false` to reject the operation.

The backend identifies the authenticated user's conversation automatically.

### Dashboard Summary

The `/dashboard/summary` endpoint provides:

- Current balance
- Monthly income
- Monthly expenses
- Monthly transaction count
- Expense totals by category
- Recent transactions


The values come from the application's MySQL-backed transaction store and are scoped to the authenticated user.

## How It Works

1. A user registers or logs in to Spendly AI.
2. The frontend uses authentication credentials for protected API requests.
3. The user submits a natural language request through the React frontend.
4. FastAPI authenticates the request and identifies the user.
5. The backend retrieves the user's persistent conversation.
6. LangGraph manages the assistant workflow and tool execution.
7. ChatGroq interprets the user's request and selects the appropriate tool.
8. Transaction tools perform user-scoped database operations in MySQL.
9. Sensitive update and deletion operations pause for human approval.
10. LangGraph checkpoints preserve conversation state in MySQL.
11. The backend returns the result to the frontend.
12. The dashboard API retrieves financial summaries belonging to the authenticated user.

The LLM interprets requests, while database-backed tools provide stored transaction records and calculated financial totals.

## Useful Commands

### Backend

Start the API:

```powershell
uv run python uvicorn app.api:app --reload
```

Start the CLI assistant:

```powershell
uv run python -m app.main
```

### Frontend

Start the development server:

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

### Authentication Errors

- Verify that the JWT secret and authentication settings are configured correctly.
- Ensure that protected requests include a valid access token.
- Check whether the refresh session is valid and has not expired or been revoked.

### Groq API Errors

- Verify the `GROQ_API_KEY` value.
- Confirm `LLM_NAME` is a supported model for your account.
- Check the backend terminal for provider error details.

### Pending Approval

Resolve a pending approval before sending another message on the same conversation.

## Security Considerations

- Passwords are hashed using Argon2.
- JWT authentication protects user-specific API endpoints.
- Access tokens are short-lived.
- Refresh tokens are stored as hashes and managed through refresh-session rotation.
- Transaction operations are scoped to the authenticated user.
- Each user has an independent conversation thread.
- Never commit `.env` files or publish credentials.
- Do not expose real financial records in public repositories.
- Configure secure cookies, CSRF protection, appropriate CORS origins, and rate limiting before public production deployment.
- Avoid using the application on shared or untrusted devices.

## Future Improvements

- Complete the dashboard UI with category charts and recent transaction views.
- Refresh dashboard figures after chat operations.
- Add transaction search and pagination.
- Production deployment.
- Monitoring, logging, and error handling.
- Automated testing and security hardening.

## License

MIT