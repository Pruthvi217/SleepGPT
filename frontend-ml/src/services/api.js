const BASE = "/api";
const TOKEN_KEY = "sleepgpt_ml_admin_token";

export const hasSession = () => Boolean(sessionStorage.getItem(TOKEN_KEY));
export const clearSession = () => sessionStorage.removeItem(TOKEN_KEY);

async function request(path, options = {}) {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const isForm = options.body instanceof FormData;
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...options,
      headers: {
        ...(isForm ? {} : { "Content-Type": "application/json" }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch {
    throw new Error("Cannot reach the SleepGPT server. Is the backend running?");
  }
  let body = null;
  try { body = await res.json(); } catch { /* no JSON */ }
  if (!res.ok) {
    if (res.status === 401 && path !== "/admin/login") {
      clearSession();
      window.location.assign("/login");
    }
    const d = body?.detail;
    const err = new Error((typeof d === "string" ? d : d?.message) || body?.message || `Request failed (${res.status}).`);
    err.details = typeof d === "object" ? d?.details : undefined;
    throw err;
  }
  return body;
}

export async function adminLogin(username, password) {
  const d = await request("/admin/login", { method: "POST", body: JSON.stringify({ username, password }) });
  sessionStorage.setItem(TOKEN_KEY, d.token);
  return d;
}
// Patients come ONLY from the existing SleepGPT store - this app never creates patient IDs.
export const listPatients = () => request("/admin/patients");
export const getHealth = () => request("/ml/health");
export const getHistory = (pid) => request(`/ml/patients/${encodeURIComponent(pid)}/history?limit=50&include_failed=true`);

const csvForm = (file) => { const f = new FormData(); f.append("file", file); return f; };
const P = (pid) => `/ml/patients/${encodeURIComponent(pid)}`;
export const previewManual = (pid, file) => request(`${P(pid)}/manual/preview`, { method: "POST", body: csvForm(file) });
export const runManual = (pid, file) => request(`${P(pid)}/manual`, { method: "POST", body: csvForm(file) });
export const previewUbidots = (pid, body) => request(`${P(pid)}/ubidots/preview`, { method: "POST", body: JSON.stringify(body) });
export const runUbidots = (pid, body) => request(`${P(pid)}/ubidots`, { method: "POST", body: JSON.stringify(body) });
export const getSensorData = (pid, start, end, device) =>
  request(`${P(pid)}/sensor-data?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}${device ? `&device_label=${encodeURIComponent(device)}` : ""}`);
