import { Link } from "react-router-dom";

export default function Home() {
  return (
    <div className="page">
      <header className="hero">
        <h1>Compare RAG strategies, with evidence.</h1>
        <p className="muted">
          Ask questions over an enterprise document set, switch chunking and
          retrieval strategies, and measure which combination actually answers
          best.
        </p>
        <Link to="/playground" className="btn btn-primary">
          Open the Playground →
        </Link>
      </header>
    </div>
  );
}
