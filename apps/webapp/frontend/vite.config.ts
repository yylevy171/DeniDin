import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// react-native-web: alias the RN import and prefer .web.* files.
export default defineConfig({
  plugins: [react()],
  define: {
    global: "window",
    __DEV__: JSON.stringify(true),
    "process.env": {},
  },
  resolve: {
    alias: { "react-native": "react-native-web" },
    extensions: [".web.tsx", ".web.ts", ".web.jsx", ".web.js", ".tsx", ".ts", ".jsx", ".js"],
  },
  optimizeDeps: {
    esbuildOptions: { resolveExtensions: [".web.js", ".js", ".ts", ".tsx"], loader: { ".js": "jsx" } },
  },
  server: {
    port: 5173,
    proxy: {
      // dev: talk to the backend without CORS fuss; VITE_API_BASE overrides for other setups
      "/api": { target: process.env.VITE_API_TARGET || "http://127.0.0.1:8100", changeOrigin: true },
    },
  },
});
