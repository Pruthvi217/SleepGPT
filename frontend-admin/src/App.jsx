import { Routes, Route } from "react-router-dom";
import AdminLogin from "./pages/AdminLogin";
import AdminDashboard from "./pages/AdminDashboard";

// SleepGPT ADMIN app. This app has no knowledge of the patient app —
// no patient registration/assessment routes, no patient components. It
// only talks to the backend over the /api/admin endpoints.
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AdminLogin />} />
      <Route path="/" element={<AdminDashboard />} />
    </Routes>
  );
}
