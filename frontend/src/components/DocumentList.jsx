import { useState } from "react";

const STATUS = {
  indexed: { label: "Indexed", cls: "badge-ok" },
  changed: { label: "Changed", cls: "badge-warn" },
  not_indexed: { label: "Not indexed", cls: "badge-warn" },
};

export const formatBytes = (n) =>
  n < 1024 * 1024
    ? `${Math.max(1, Math.round(n / 1024))} KB`
    : `${(n / 1048576).toFixed(1)} MB`;

export default function DocumentList({
  departments,
  onDelete,
  onDeleteFolder,
  disabled,
}) {
  const [busy, setBusy] = useState(null);

  const run = async (key, fn) => {
    setBusy(key);
    try {
      await fn();
    } finally {
      setBusy(null);
    }
  };

  if (departments.length === 0) {
    return (
      <div className="card empty">
        <h3>No documents yet</h3>
        <p className="muted">
          Create a folder and upload some PDFs to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="dept-list">
      {departments.map((dept) => (
        <div key={dept.name} className="card dept">
          <div className="dept-head">
            <h3>
              <span className="folder">📁</span> {dept.name}
            </h3>
            <span className="muted small">
              {dept.documents.length} document(s)
            </span>
            {dept.documents.length === 0 && (
              <button
                type="button"
                className="link danger"
                disabled={disabled || busy === dept.name}
                onClick={() => run(dept.name, () => onDeleteFolder(dept.name))}
              >
                Remove empty folder
              </button>
            )}
          </div>

          {dept.documents.map((doc) => {
            const s = STATUS[doc.status] ?? STATUS.not_indexed;
            const key = `${dept.name}/${doc.filename}`;
            return (
              <div key={key} className="doc-row">
                <div className="doc-main">
                  <span className="doc-name">{doc.filename}</span>
                  <span className="muted small">
                    {formatBytes(doc.size_bytes)}
                    {doc.chunk_count > 0 &&
                      ` · ${doc.chunk_count} chunks (fixed)`}
                  </span>
                </div>
                <span className={`badge ${s.cls}`}>{s.label}</span>
                <button
                  type="button"
                  className="icon-btn"
                  title="Delete document"
                  disabled={disabled || busy === key}
                  onClick={() => {
                    if (
                      window.confirm(
                        `Delete ${doc.filename}? The index stays as-is until you rebuild.`,
                      )
                    ) {
                      run(key, () => onDelete(dept.name, doc.filename));
                    }
                  }}
                >
                  🗑
                </button>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
