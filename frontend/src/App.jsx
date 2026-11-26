
import { useEffect, useState } from "react";
import {
  Wallet,
  Bot,
  Send,
  Sparkles,
  LogOut,
  TrendingUp,
  TrendingDown,
  MessageCircle,
  ShieldCheck,
  Check,
  X,
  LoaderCircle,
  Eye,
  EyeOff,
  Lock,
  Mail,
  UserRound,
} from "lucide-react";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useAuth } from "./context/AuthContext";

import {
  getDashboard,
  sendChatMessage,
  submitApproval,
} from "./services/api";

import "./App.css";

const WELCOME_MESSAGE = {
  role: "assistant",
  content:
    "Hey! 👋 I'm your personal finance assistant. Ask me about your expenses, record income, or manage your transactions.",
};

const SUGGESTIONS = [
  "How much did I spend this month?",
  "Show my recent expenses",
  "What is my current balance?",
  "Break down spending by category",
];

function money(value) {
  return Number(value || 0).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  });
}

/* =================================
   MARKDOWN MESSAGE RENDERER
================================= */

function MarkdownMessage({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table({ children }) {
          return (
            <div className="markdown-table-wrapper">
              <table className="markdown-table">
                {children}
              </table>
            </div>
          );
        },

        th({ children }) {
          return <th>{children}</th>;
        },

        td({ children }) {
          return <td>{children}</td>;
        },

        a({ children, href }) {
          return (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          );
        },

        pre({ children }) {
          return (
            <pre className="markdown-code-block">
              {children}
            </pre>
          );
        },

        code({ children, className }) {
          const isBlock = Boolean(className);

          return (
            <code
              className={
                isBlock
                  ? `markdown-code ${className}`
                  : "markdown-inline-code"
              }
            >
              {children}
            </code>
          );
        },
      }}
    >
      {content || ""}
    </ReactMarkdown>
  );
}

/* =================================
   AUTHENTICATION SCREEN
================================= */

function AuthScreen() {
  const { signIn, signUp } = useAuth();

  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();

    if (loading) return;

    setLoading(true);
    setError("");

    try {
      if (mode === "login") {
        await signIn(email, password);
      } else {
        await signUp(email, password);
      }
    } catch (err) {
      setError(err.message || "Authentication failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-glow auth-glow-one" />
      <div className="auth-glow auth-glow-two" />

      <section className="auth-card">
        <div className="brand auth-brand">
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

        <div className="auth-heading">
          <div className="auth-icon">
            <Sparkles size={22} />
          </div>

          <h1>
            {mode === "login"
              ? "Welcome back"
              : "Create your account"}
          </h1>

          <p>
            {mode === "login"
              ? "Your personal finances, all in one place."
              : "Start managing your money with Spendly AI."}
          </p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>Email address</label>

          <div className="auth-input-wrap">
            <Mail size={18} />

            <input
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </div>

          <label>Password</label>

          <div className="auth-input-wrap">
            <Lock size={18} />

            <input
              type={showPassword ? "text" : "password"}
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={
                mode === "login"
                  ? "current-password"
                  : "new-password"
              }
              minLength={8}
              maxLength={128}
              required
            />

            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? (
                <EyeOff size={18} />
              ) : (
                <Eye size={18} />
              )}
            </button>
          </div>

          {error && (
            <div className="auth-error">
              <X size={16} />
              {error}
            </div>
          )}

          <button
            className="auth-submit"
            type="submit"
            disabled={loading}
          >
            {loading ? (
              <LoaderCircle size={19} className="spinner" />
            ) : mode === "login" ? (
              "Sign in"
            ) : (
              "Create account"
            )}
          </button>
        </form>

        <div className="auth-switch">
          {mode === "login"
            ? "Don't have an account?"
            : "Already have an account?"}

          <button
            onClick={() => {
              setMode(
                mode === "login" ? "register" : "login"
              );
              setError("");
            }}
          >
            {mode === "login" ? "Create account" : "Sign in"}
          </button>
        </div>

        <div className="auth-security">
          <ShieldCheck size={16} />
          Your financial data is private and protected.
        </div>
      </section>

      <p className="auth-footer">
        SPENDLY AI · PERSONAL FINANCE, SIMPLIFIED
      </p>
    </main>
  );
}

/* =================================
   MAIN APP
================================= */

export default function App() {
  const { user, initializing } = useAuth();

  if (initializing) {
    return (
      <div className="app-loading">
        <div className="brand-icon">
          <Wallet size={24} />
        </div>

        <LoaderCircle className="spinner" size={23} />

        <p>Preparing your workspace...</p>
      </div>
    );
  }

  if (!user) {
    return <AuthScreen />;
  }

  return <DashboardApp user={user} />;
}

/* =================================
   DASHBOARD AND CHAT
================================= */

function DashboardApp({ user }) {
  const { signOut } = useAuth();

  // Separate browser-side chat history for each user.
  const storageKey = `spendly_chat_${user.id}`;

  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem(storageKey);

      return saved
        ? JSON.parse(saved)
        : [WELCOME_MESSAGE];
    } catch {
      return [WELCOME_MESSAGE];
    }
  });

  const [approval, setApproval] = useState(null);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [dashboard, setDashboard] = useState(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [dashboardError, setDashboardError] = useState("");

  // Persist chat messages.
  useEffect(() => {
    localStorage.setItem(
      storageKey,
      JSON.stringify(messages)
    );
  }, [messages, storageKey]);

  async function loadDashboard() {
    try {
      setDashboardError("");

      const data = await getDashboard();

      setDashboard(data);
    } catch (err) {
      setDashboardError(err.message);
    } finally {
      setDashboardLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, [user.id]);

  async function sendMessage(text = input) {
    const message = text.trim();

    if (!message || loading || approval) return;

    setMessages((previous) => [
      ...previous,
      {
        role: "user",
        content: message,
      },
    ]);

    setInput("");
    setLoading(true);
    setError("");

    try {
      // Backend automatically retrieves this user's conversation.
      const data = await sendChatMessage(message);

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content:
            data.response ||
            "Your request has been processed.",
        },
      ]);

      if (data.approval_required) {
        setApproval({
          request: data.approval_request,
        });
      }

      await loadDashboard();
    } catch (err) {
      setError(
        err.message || "Unable to send your message."
      );
    } finally {
      setLoading(false);
    }
  }

  async function respondToApproval(approved) {
    if (!approval || loading) return;

    setLoading(true);
    setError("");

    try {
      const data = await submitApproval(approved);

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content:
            data.response ||
            (approved
              ? "The action was approved."
              : "The action was rejected."),
        },
      ]);

      if (data.approval_required) {
        setApproval({
          request: data.approval_request,
        });
      } else {
        setApproval(null);
      }

      await loadDashboard();
    } catch (err) {
      setError(
        err.message || "Unable to submit your decision."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout() {
    if (loading) return;

    await signOut();
  }

  const transaction = approval?.request?.transaction;

  const approvalMessage =
    approval?.request?.message ||
    "Do you approve this transaction change?";

  return (
    <div className="app-shell">
      {/* SIDEBAR */}

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

        <div className="sidebar-label">
          YOUR WORKSPACE
        </div>

        <div className="sidebar-item active">
          <MessageCircle size={18} />
          AI Assistant
          <span className="online-dot" />
        </div>

        <div className="sidebar-bottom">
          <div className="user-card">
            <div className="user-avatar">
              <UserRound size={19} />
            </div>

            <div className="user-info">
              <strong>{user.email}</strong>
              <span>Personal account</span>
            </div>
          </div>

          <button
            className="logout-button"
            onClick={handleLogout}
          >
            <LogOut size={17} />
            Sign out
          </button>

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

      {/* MAIN PANEL */}

      <main className="main-panel">
        <header className="topbar">
          <div>
            <div className="eyebrow">
              YOUR PERSONAL FINANCE SPACE
            </div>

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
          {/* WELCOME */}

          <div className="welcome-banner">
            <div className="welcome-icon">
              <Sparkles size={24} />
            </div>

            <div>
              <h2>Your money, your way.</h2>

              <p>
                Track spending, understand your habits, and
                manage your finances through conversation.
              </p>
            </div>
          </div>

          {/* DASHBOARD */}

          <section className="dashboard-section">
            <div className="dashboard-heading">
              <div>
                <h2>Financial overview</h2>
                <p>Your personal finances at a glance</p>
              </div>
            </div>

            {dashboardLoading ? (
              <div className="dashboard-placeholder">
                <LoaderCircle
                  className="spinner"
                  size={20}
                />
                Loading financial overview...
              </div>
            ) : dashboardError ? (
              <div className="dashboard-error">
                {dashboardError}
              </div>
            ) : dashboard ? (
              <div className="dashboard-grid">
                <div className="dashboard-card">
                  <div className="stat-icon balance-icon">
                    <Wallet size={19} />
                  </div>

                  <span>Current balance</span>

                  <h3>₹{money(dashboard.balance)}</h3>

                  <p>Available balance</p>
                </div>

                <div className="dashboard-card">
                  <div className="stat-icon income-icon">
                    <TrendingUp size={19} />
                  </div>

                  <span>Monthly income</span>

                  <h3 className="income-value">
                    +₹{money(dashboard.monthly_income)}
                  </h3>

                  <p>This month</p>
                </div>

                <div className="dashboard-card">
                  <div className="stat-icon expense-icon">
                    <TrendingDown size={19} />
                  </div>

                  <span>Monthly expenses</span>

                  <h3 className="expense-value">
                    -₹{money(dashboard.monthly_expenses)}
                  </h3>

                  <p>This month</p>
                </div>

                <div className="dashboard-card">
                  <div className="stat-icon count-icon">
                    <MessageCircle size={19} />
                  </div>

                  <span>Transactions</span>

                  <h3>
                    {dashboard.monthly_transaction_count}
                  </h3>

                  <p>This month</p>
                </div>
              </div>
            ) : null}
          </section>

          {/* CHAT MESSAGES */}

          <div className="messages">
            {messages.map((message, index) => (
              <div
                className={`message-row ${message.role}`}
                key={`${index}-${message.role}`}
              >
                <div
                  className={`message-avatar ${message.role}`}
                >
                  {message.role === "assistant" ? (
                    <Bot size={19} />
                  ) : (
                    <span>You</span>
                  )}
                </div>

                <div className="message-content">
                  <div className="message-author">
                    {message.role === "assistant"
                      ? "Spendly AI"
                      : "You"}
                  </div>

                  <div className="message-bubble">
                    {message.role === "assistant" ? (
                      <MarkdownMessage
                        content={message.content}
                      />
                    ) : (
                      message.content
                    )}
                  </div>
                </div>
              </div>
            ))}

            {loading && (
              <div className="loading-message">
                <LoaderCircle
                  size={18}
                  className="spinner"
                />

                <span>
                  Thinking through your request...
                </span>
              </div>
            )}

            {/* APPROVAL */}

            {approval && (
              <div className="approval-card">
                <div className="approval-heading">
                  <div className="approval-icon">
                    <ShieldCheck size={22} />
                  </div>

                  <div>
                    <h3>Approval required</h3>
                    <p>
                      Review this action before it proceeds.
                    </p>
                  </div>
                </div>

                <p className="approval-message">
                  {approvalMessage}
                </p>

                {transaction && (
                  <div className="transaction-preview">
                    <div>
                      <span>TRANSACTION</span>

                      <strong>
                        {transaction.description ||
                          transaction.category}
                      </strong>
                    </div>

                    <div className="transaction-amount">
                      ₹{money(transaction.amount)}
                    </div>

                    <div className="transaction-meta">
                      {transaction.category} ·{" "}
                      {transaction.date}
                    </div>
                  </div>
                )}

                <div className="approval-actions">
                  <button
                    className="reject-button"
                    disabled={loading}
                    onClick={() =>
                      respondToApproval(false)
                    }
                  >
                    <X size={17} />
                    Reject
                  </button>

                  <button
                    className="approve-button"
                    disabled={loading}
                    onClick={() =>
                      respondToApproval(true)
                    }
                  >
                    <Check size={17} />
                    Approve action
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* ERROR */}

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

          {/* MESSAGE COMPOSER */}

          {!approval && (
            <div className="composer-area">
              <div className="suggestion-label">
                TRY ASKING
              </div>

              <div className="suggestions">
                {SUGGESTIONS.map((suggestion) => (
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
                  onChange={(event) =>
                    setInput(event.target.value)
                  }
                  placeholder="Ask anything about your expenses..."
                  rows={1}
                  disabled={loading || Boolean(approval)}
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey
                    ) {
                      event.preventDefault();
                      sendMessage();
                    }
                  }}
                />

                <button
                  type="submit"
                  className="send-button"
                  disabled={
                    !input.trim() ||
                    loading ||
                    Boolean(approval)
                  }
                  aria-label="Send message"
                >
                  {loading ? (
                    <LoaderCircle
                      size={19}
                      className="spinner"
                    />
                  ) : (
                    <Send size={19} />
                  )}
                </button>
              </form>

              <p className="composer-hint">
                Enter to send · Shift + Enter for a new line
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
