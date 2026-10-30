const BASE = "/api";
export const TOKEN_KEY = "sleepgpt_admin_token";

async function request(path, options = {}) {
  let res;
  try {
    const token = sessionStorage.getItem(TOKEN_KEY);
    res = await fetch(`${BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch (err) {
    throw new Error("Cannot reach the SleepGPT server. Is the backend running?");
  }

  let body = null;
  try {
    body = await res.json();
  } catch {
    // no JSON body
  }

  if (!res.ok) {
    if (res.status === 401 && path !== "/admin/login") {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem("sleepgpt_admin_session");
      window.location.assign("/login");
    }
    const detail = body?.detail;
    const message = (typeof detail === "string" ? detail : detail?.message) || body?.message || `Request failed (${res.status}).`;
    throw new Error(message);
  }
  return body;
}

export async function adminLogin(username, password) {
  const data = await request("/admin/login", { method: "POST", body: JSON.stringify({ username, password }) });
  if (data.token) sessionStorage.setItem(TOKEN_KEY, data.token);
  return data;
}

export function getMlSummary() {
  return request("/ml/admin/summary");
}

export function listPatients() {
  return request("/admin/patients");
}

export function getPatientDetail(patientId) {
  return request(`/admin/patient/${encodeURIComponent(patientId)}`);
}

export function releaseResults(patientId) {
  return request(`/admin/patient/${encodeURIComponent(patientId)}/release-results`, { method: "POST" });
}
