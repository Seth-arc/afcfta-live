import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./index.css";

if (!import.meta.env.VITE_API_KEY) {
  console.warn("[AIS] VITE_API_KEY is not set — API calls will fail with 401.");
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
