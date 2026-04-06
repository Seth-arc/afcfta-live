import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  envDir: path.resolve(__dirname),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("proxyReq", (proxyReq, req) => {
            // Ensure custom headers survive the proxy hop
            const apiKey = req.headers["x-api-key"];
            if (apiKey) {
              proxyReq.setHeader("X-API-Key", apiKey as string);
            }
            console.log(
              `[proxy] ${req.method} ${req.url} → X-API-Key: ${apiKey ? "present" : "MISSING"}`
            );
          });
        },
      },
    },
  },
});
