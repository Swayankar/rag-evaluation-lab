import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Home from "./pages/Home.jsx";
import Playground from "./pages/Playground.jsx";
import Documents from "./pages/Documents.jsx";
import ComingSoon from "./pages/ComingSoon.jsx";

const NAV = [
  { to: "/", label: "Home", end: true },
  { to: "/playground", label: "Playground" },
  { to: "/documents", label: "Documents" },
  { to: "/evaluation", label: "Evaluation" },
  { to: "/experiments", label: "Experiments" },
];

export default function App() {
  return (
    <div className="shell">
      <nav className="topbar">
        <div className="brand">
          <span className="brand-mark">◈</span> RAG Evaluation Lab
        </div>
        <div className="nav-links">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `nav-link ${isActive ? "active" : ""}`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="content">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/playground" element={<Playground />} />
          <Route path="/documents" element={<Documents />} />
          <Route
            path="/evaluation"
            element={<ComingSoon title="Evaluation" step="10c" />}
          />
          <Route
            path="/experiments"
            element={<ComingSoon title="Experiments" step="10d" />}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
