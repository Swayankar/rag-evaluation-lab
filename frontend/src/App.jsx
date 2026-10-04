import { Suspense, lazy, useEffect } from "react";
import {
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import Home from "./pages/Home.jsx";
import Playground from "./pages/Playground.jsx";
import Documents from "./pages/Documents.jsx";
const Evaluation = lazy(() => import("./pages/Evaluation.jsx"));
const Experiments = lazy(() => import("./pages/Experiments.jsx"));
import { ConfigBadge } from "./components/ConfigPanel.jsx";

const NAV = [
  { to: "/", label: "Home", end: true },
  { to: "/playground", label: "Playground" },
  { to: "/documents", label: "Documents" },
  { to: "/evaluation", label: "Evaluation" },
  { to: "/experiments", label: "Experiments" },
];

const TITLES = {
  "/": "Home",
  "/playground": "Playground",
  "/documents": "Documents",
  "/evaluation": "Evaluation",
  "/experiments": "Experiments",
};

export default function App() {
  const { pathname } = useLocation();
  useEffect(() => {
    const page = TITLES[pathname];
    document.title =
      page && pathname !== "/"
        ? `${page} · RAG Evaluation Lab`
        : "RAG Evaluation Lab";
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className="shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <nav className="topbar" aria-label="Main">
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
        <ConfigBadge />
      </nav>
      <main className="content" id="main" tabIndex={-1}>
        <ErrorBoundary key={pathname}>
          <Suspense fallback={<div className="muted">Loading…</div>}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/playground" element={<Playground />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/evaluation" element={<Evaluation />} />
              <Route path="/experiments" element={<Experiments />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </main>
    </div>
  );
}
