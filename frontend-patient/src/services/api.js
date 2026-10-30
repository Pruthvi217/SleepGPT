const BASE = "/api";
const TOKEN_KEY = "sleepgpt_patient_token";

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}) {
  let res;
  try {
    const token = localStorage.getItem(TOKEN_KEY);
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
    const detail = body?.detail;
    const message = (typeof detail === "string" ? detail : detail?.message) || body?.message || `Request failed (${res.status}).`;
    throw new Error(message);
  }
  return body;
}

export function registerPatient(username) {
  return request("/patient/register", { method: "POST", body: JSON.stringify({ username }) });
}

export async function loginPatient(patientId) {
  const data = await request("/patient/login", { method: "POST", body: JSON.stringify({ patient_id: patientId }) });
  if (data.token) localStorage.setItem(TOKEN_KEY, data.token);
  return data;
}

// ML / sleep analysis — always the logged-in patient's own SGP-XXXXXX id.
export function getMlLatest(patientId) {
  return request(`/ml/patients/${encodeURIComponent(patientId)}/latest`);
}

export function getMlHistory(patientId) {
  return request(`/ml/patients/${encodeURIComponent(patientId)}/history?limit=10`);
}

export function askChat(patientId, message) {
  return request("/chat", { method: "POST", body: JSON.stringify({ message, patient_id: patientId }) });
}

export function startAssessment(patientId) {
  return request(`/assessment/start?patient_id=${encodeURIComponent(patientId)}`);
}

export function submitAnswer(patientId, questionId, value) {
  return request("/assessment/answer", {
    method: "POST",
    body: JSON.stringify({ patient_id: patientId, question_id: questionId, value }),
  });
}

export function getResults(patientId) {
  return request(`/assessment/results?patient_id=${encodeURIComponent(patientId)}`);
}
