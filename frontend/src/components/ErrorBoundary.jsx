import { Component } from "react";

export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Page crashed:", error, info?.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="page" role="alert">
        <h1>Something went wrong on this page</h1>
        <div className="notice notice-error">
          <div>{String(error?.message ?? error)}</div>
          <div className="small muted" style={{ marginTop: 6 }}>
            Open the browser console (F12) for details. Your data is untouched;
            this is a display error.
          </div>
        </div>
        <div className="run-bar">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => window.location.reload()}
          >
            Reload the app
          </button>
        </div>
      </div>
    );
  }
}
