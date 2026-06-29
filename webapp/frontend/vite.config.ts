import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend (FastAPI) port — override with VITE_API_PORT if 8765 is taken.
const apiPort = process.env.VITE_API_PORT || "8765";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": `http://127.0.0.1:${apiPort}` } },
});
