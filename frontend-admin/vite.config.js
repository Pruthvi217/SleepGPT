import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// SleepGPT ADMIN app — completely independent build from frontend-patient/.
// Runs on its own port and only talks to the backend over /api.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
