import { Routes, Route } from "react-router-dom";
import Login from "./pages/Login";
import MlDashboard from "./pages/MlDashboard";

// SleepGPT ML dashboard (port 5175). Uses the SAME admin login and the SAME SGP-XXXXXX patient ids
// as the rest of the platform; it has no patient registration and creates no identities.
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<MlDashboard />} />
    </Routes>
  );
}
