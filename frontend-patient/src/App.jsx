import { Routes, Route } from "react-router-dom";
import Welcome from "./pages/Welcome";
import PatientDashboard from "./pages/PatientDashboard";

// SleepGPT PATIENT app. This app has no knowledge of the admin app —
// no admin routes, no admin components, no shared login state. It only
// talks to the backend over the public /api/patient and /api/assessment
// endpoints.
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Welcome />} />
      <Route path="/assessment" element={<PatientDashboard />} />
    </Routes>
  );
}
