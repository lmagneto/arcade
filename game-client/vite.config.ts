
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? "1.0.3"),
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/mouse-bridge": {
        target: "http://127.0.0.1:8765",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/mouse-bridge/, ""),
      },
    },
  },
});
