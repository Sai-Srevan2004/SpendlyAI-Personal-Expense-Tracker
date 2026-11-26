
const API_URL = "http://localhost:8000";

let accessToken = null;
let refreshPromise = null;

export function setAccessToken(token) {
  accessToken = token;
}

async function request(path, options = {}, retry = true) {
  const headers = {
    ...options.headers,
  };

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (response.status === 401 && retry && path !== "/auth/refresh") {
    const refreshed = await refreshSession();

    if (refreshed) {
      return request(path, options, false);
    }
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Request failed."
    );
  }

  return data;
}

export async function refreshSession() {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });

      if (!response.ok) {
        accessToken = null;
        return false;
      }

      const data = await response.json();
      accessToken = data.access_token;

      return true;
    } catch {
      accessToken = null;
      return false;
    }
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

export async function login(email, password) {
  const data = await request(
    "/auth/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    },
    false
  );

  setAccessToken(data.access_token);
  return getMe();
}

export async function register(email, password) {
  await request(
    "/auth/register",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    },
    false
  );

  return login(email, password);
}

export async function getMe() {
  return request("/auth/me", {}, false);
}

export async function logout() {
  try {
    await request("/auth/logout", { method: "POST" }, false);
  } finally {
    accessToken = null;
  }
}

export function getDashboard() {
  return request("/dashboard/summary");
}

export function sendChatMessage(message) {
  return request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
}

export function submitApproval(approved) {
  return request("/approval", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved }),
  });
}
