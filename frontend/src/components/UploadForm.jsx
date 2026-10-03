import { useRef, useState } from "react";

const NEW = "__new__";

export default function UploadForm({ departments, onUpload, disabled }) {
  const names = departments.map((d) => d.name);
  const [dept, setDept] = useState(names[0] ?? NEW);
  const [newDept, setNewDept] = useState("");
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [outcome, setOutcome] = useState(null);
  const inputRef = useRef(null);

  const target = dept === NEW || !names.includes(dept) ? newDept : dept;
  const canUpload =
    files.length > 0 && target.trim() && !uploading && !disabled;

  const addFiles = (list) => {
    const pdfs = Array.from(list).filter((f) =>
      f.name.toLowerCase().endsWith(".pdf"),
    );
    setFiles((prev) => [
      ...prev,
      ...pdfs.filter((f) => !prev.some((p) => p.name === f.name)),
    ]);
  };

  const submit = async () => {
    setUploading(true);
    setOutcome(null);
    try {
      const res = await onUpload(target.trim(), files);
      setOutcome({ saved: res.saved, rejected: res.rejected });
      setFiles([]);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      let rejected = [{ filename: "", reason: err.message }];
      try {
        const parsed = JSON.parse(err.message);
        if (parsed.rejected) rejected = parsed.rejected;
      } catch {
        /* plain message */
      }
      setOutcome({ saved: [], rejected });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="card">
      <div className="field-label">Upload PDFs</div>

      <div className="upload-row">
        <label className="muted small">
          Folder
          <select
            value={dept}
            onChange={(e) => setDept(e.target.value)}
            disabled={disabled || uploading}
          >
            {names.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
            <option value={NEW}>+ New folder…</option>
          </select>
        </label>
        {(dept === NEW || names.length === 0) && (
          <input
            className="text-input"
            placeholder="new folder name, e.g. finance"
            value={newDept}
            onChange={(e) => setNewDept(e.target.value)}
            disabled={disabled || uploading}
          />
        )}
      </div>

      <div
        className={`dropzone ${dragging ? "dropzone-on" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          addFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          hidden
          onChange={(e) => addFiles(e.target.files)}
        />
        <div className="drop-icon">⬆</div>
        <div>Drop PDFs here or click to choose</div>
        <div className="muted small">
          Max 25 MB each · the file name becomes the document id, so it must be
          unique
        </div>
      </div>

      {files.length > 0 && (
        <div className="file-chips">
          {files.map((f) => (
            <span key={f.name} className="chip">
              {f.name}
              <button
                type="button"
                className="chip-x"
                onClick={() => setFiles((fs) => fs.filter((x) => x !== f))}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="run-bar" style={{ marginTop: 12 }}>
        <button
          type="button"
          className="btn btn-primary"
          onClick={submit}
          disabled={!canUpload}
        >
          {uploading
            ? "Uploading…"
            : `Upload ${files.length || ""} file${files.length === 1 ? "" : "s"}`}
        </button>
        {uploading && <span className="spinner" aria-hidden />}
      </div>

      {outcome && (
        <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
          {outcome.saved.length > 0 && (
            <div className="notice notice-ok">
              Uploaded {outcome.saved.length} file(s). Rebuild the index to make
              them searchable.
            </div>
          )}
          {outcome.rejected.map((r, i) => (
            <div key={i} className="notice notice-error">
              {r.filename && <b>{r.filename}: </b>}
              {r.reason}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
