
import { useEffect, useState } from "react";
import {
  Bot,
  Plus,
  Send,
  Wallet,
  Sparkles,
  Check,
  X,
  LoaderCircle,
  MessageCircle,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";
const STORAGE_KEY = "spendly_chat_state";

const WELCOME_MESSAGE = {
  role: "assistant",
  content:
    "Hey! 👋 I'm your personal finance assistant. Ask me about your expenses, record income, or manage your transactions.",
};

const suggestions = [
  "How much did I spend last week?",
  "Show all my expenses",
  "What is my current balance?",
  "Break down my spending by category",
];

function loadChatState() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);

    if (!saved) {
      return {
        messages: [WELCOME_MESSAGE],
        threadId: null,
        approval: null,
      };
    }

    const parsed = JSON.parse(saved);

    return {
      messages: Array.isArray(parsed.messages)
        ? parsed.messages
        : [WELCOME_MESSAGE],
      threadId: parsed.threadId || null,
      approval: parsed.approval || null,
    };
  } catch {
    return {
      messages: [WELCOME_MESSAGE],
      threadId: null,
      approval: null,
    };
  }
}

function App() {
  const [initialState] = useState(loadChatState);

  const [messages, setMessages] = useState(initialState.messages);
  const [input, setInput] = useState("");
  const [threadId, setThreadId] = useState(initialState.threadId);
  const [approval, setApproval] = useState(initialState.approval);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [dashboard, setDashboard] = useState(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [dashboardError, setDashboardError] = useState("");

  async function loadDashboard() {
    try {
      setDashboardError("");

      const response = await fetch(`${API_URL}/dashboard/summary`);

      if (!response.ok) {
        throw new Error("Failed to load dashboard data.");
      }

      const data = await response.json();
      setDashboard(data);
    } catch (error) {
      setDashboardError(error.message);
    } finally {
      setDashboardLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  // Save the current conversation whenever its state changes.
  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          messages,
          threadId,
          approval,
        })
      );
    } catch (err) {
      console.error("Unable to save chat history:", err);
    }
  }, [messages, threadId, approval]);

  async function sendMessage(text = input) {
    const message = text.trim();

    if (!message || loading || approval) return;

    setMessages((previous) => [
      ...previous,
      { role: "user", content: message },
    ]);
    setInput("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          ...(threadId ? { thread_id: threadId } : {}),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Unable to process your message."
        );
      }

      setThreadId(data.thread_id);

      if (data.approval_required) {
        setApproval({
          thread_id: data.thread_id,
          request: data.approval_request,
        });
      }

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: data.response,
        },
      ]);
    } catch (err) {
      setError(err.message || "Unable to connect to the server.");
    } finally {
      setLoading(false);
    }
  }

  async function respondToApproval(approved) {
    if (!approval || loading) return;

    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/approval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: approval.thread_id,
          approved,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Unable to submit your decision."
        );
      }

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: data.response,
        },
      ]);

      if (data.approval_required) {
        setApproval({
          thread_id: data.thread_id,
          request: data.approval_request,
        });
      } else {
        setApproval(null);
      }
    } catch (err) {
      setError(err.message || "Unable to submit your decision.");
    } finally {
      setLoading(false);
    }
  }

  function startNewChat() {
    if (loading || approval) return;

    setThreadId(null);
    setApproval(null);
    setError("");
    setInput("");
    setMessages([
      {
        role: "assistant",
        content:
          "New conversation started! What would you like to do with your finances?",
      },
    ]);
  }

  const approvalMessage =
    approval?.request?.message ||
    "Do you approve this transaction change?";

  const transaction = approval?.request?.transaction;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Wallet size={23} />
          </div>
          <div>
            <h2>
              Spendly<span>.</span>
            </h2>
            <p>AI FINANCE ASSISTANT</p>
          </div>
        </div>

        <button
          className="new-chat-button"
          onClick={startNewChat}
          disabled={loading || Boolean(approval)}
          title={
            approval
              ? "Resolve the pending approval before starting a new chat."
              : "Start a new conversation"
          }
        >
          <Plus size={18} />
          New conversation
        </button>

        <div className="sidebar-label">YOUR WORKSPACE</div>
        <div className="sidebar-item active">
          <MessageCircle size={18} />
          AI Assistant
          <span className="online-dot" />
        </div>

        <div className="sidebar-bottom">
          <div className="status-card">
            <span className="status-indicator" />
            <div>
              <strong>Assistant online</strong>
              <p>Ready to help you</p>
            </div>
          </div>
          <p className="sidebar-footer">
            PERSONAL FINANCE · PRIVATE BY DESIGN
          </p>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <div className="eyebrow">YOUR PERSONAL FINANCE SPACE</div>
            <h1>
              AI Assistant <span className="sparkle">✦</span>
            </h1>
          </div>
          <div className="topbar-right">
            <span className="connection-dot" />
            <span>AI connected</span>
            <div className="avatar">
              <Bot size={21} />
            </div>
          </div>
        </header>

        <section className="chat-container">
          <div className="welcome-banner">
            <div className="welcome-icon">
              <Sparkles size={24} />
            </div>
            <div>
              <h2>Your money, your way.</h2>
              <p>
                Track spending, understand your habits, and manage your
                finances through conversation.
              </p>
            </div>
          </div>

          <section className="dashboard-section">
            <div className="dashboard-heading">
              <div>
                <h2>Financial Overview</h2>
                <p>Your personal finances at a glance</p>
              </div>
            </div>

            {dashboardLoading ? (
              <p>Loading your financial overview...</p>
            ) : dashboardError ? (
              <p className="dashboard-error">{dashboardError}</p>
            ) : dashboard ? (
              <div className="dashboard-grid">
                <div className="dashboard-card">
                  <span>Current Balance</span>
                  <h3>
                    ₹{Number(dashboard.balance).toLocaleString("en-IN", {
                      maximumFractionDigits: 2,
                    })}
                  </h3>
                </div>

                <div className="dashboard-card">
                  <span>Monthly Income</span>
                  <h3 className="income-value">
                    +₹{Number(dashboard.monthly_income).toLocaleString("en-IN", {
                      maximumFractionDigits: 2,
                    })}
                  </h3>
                </div>

                <div className="dashboard-card">
                  <span>Monthly Expenses</span>
                  <h3 className="expense-value">
                    -₹{Number(dashboard.monthly_expenses).toLocaleString("en-IN", {
                      maximumFractionDigits: 2,
                    })}
                  </h3>
                </div>

                <div className="dashboard-card">
                  <span>Transactions This Month</span>
                  <h3>{dashboard.monthly_transaction_count}</h3>
                </div>
              </div>
            ) : null}
          </section>

          <div className="messages">
            {messages.map((message, index) => (
              <div
                className={`message-row ${message.role}`}
                key={`${index}-${message.role}`}
              >
                <div className={`message-avatar ${message.role}`}>
                  {message.role === "assistant" ? (
                    <Bot size={19} />
                  ) : (
                    <span>You</span>
                  )}
                </div>

                <div className="message-content">
                  <div className="message-author">
                    {message.role === "assistant" ? "Spendly AI" : "You"}
                  </div>

                  <div className="message-bubble">
                    {message.role === "assistant" ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.content}
                      </ReactMarkdown>
                    ) : (
                      message.content
                    )}
                  </div>
                </div>
              </div>
            ))}

            {loading && (
              <div className="loading-message">
                <LoaderCircle size={18} className="spinner" />
                <span>Thinking through your request...</span>
              </div>
            )}

            {approval && (
              <div className="approval-card">
                <div className="approval-heading">
                  <div className="approval-icon">
                    <ShieldIcon />
                  </div>
                  <div>
                    <h3>Approval required</h3>
                    <p>Review this action before it proceeds.</p>
                  </div>
                </div>

                <p className="approval-message">{approvalMessage}</p>

                {transaction && (
                  <div className="transaction-preview">
                    <div>
                      <span>TRANSACTION</span>
                      <strong>
                        {transaction.description || transaction.category}
                      </strong>
                    </div>
                    <div className="transaction-amount">
                      ₹{Number(transaction.amount).toLocaleString("en-IN")}
                    </div>
                    <div className="transaction-meta">
                      {transaction.category} · {transaction.date}
                    </div>
                  </div>
                )}

                <div className="approval-actions">
                  <button
                    className="reject-button"
                    disabled={loading}
                    onClick={() => respondToApproval(false)}
                  >
                    <X size={17} /> Reject
                  </button>
                  <button
                    className="approve-button"
                    disabled={loading}
                    onClick={() => respondToApproval(true)}
                  >
                    <Check size={17} /> Approve action
                  </button>
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="error-banner">
              <span>{error}</span>
              <button
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                <X size={16} />
              </button>
            </div>
          )}

          {!approval && (
            <div className="composer-area">
              <div className="suggestion-label">TRY ASKING</div>
              <div className="suggestions">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    className="suggestion-chip"
                    disabled={loading}
                    onClick={() => sendMessage(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>

              <form
                className="composer"
                onSubmit={(event) => {
                  event.preventDefault();
                  sendMessage();
                }}
              >
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Ask anything about your expenses..."
                  rows={1}
                  disabled={loading || Boolean(approval)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      sendMessage();
                    }
                  }}
                />
                <button
                  type="submit"
                  className="send-button"
                  disabled={!input.trim() || loading || Boolean(approval)}
                  aria-label="Send message"
                >
                  {loading ? (
                    <LoaderCircle size={19} className="spinner" />
                  ) : (
                    <Send size={19} />
                  )}
                </button>
              </form>
              <p className="composer-hint">
                <span>↵</span> to send · Shift + ↵ for a new line
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function ShieldIcon() {
  return (
    <svg
      width="21"
      height="21"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

export default App;
