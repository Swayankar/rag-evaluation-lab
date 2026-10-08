import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import BackendGate from "./components/BackendGate.jsx";
import { WorkspaceProvider } from "./context/WorkspaceContext.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <BackendGate>
        <WorkspaceProvider>
          <App />
        </WorkspaceProvider>
      </BackendGate>
    </BrowserRouter>
  </React.StrictMode>,
);
