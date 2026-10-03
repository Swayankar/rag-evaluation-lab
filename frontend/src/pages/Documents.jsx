import { useCallback, useEffect, useState } from "react";
import DocumentList from "../components/DocumentList.jsx";
import UploadForm from "../components/UploadForm.jsx";
import RebuildPanel from "../components/RebuildPanel.jsx";
import { api } from "../services/api.js";
import { useJob } from "../hooks/useJob.js";

export default function Documents() {
  const [library, setLibrary] = useState(null);
  const [error, setError] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [starting, setStarting] = useState(false);
  const [folderName, setFolderName] = useState("");
  const [actionError, setActionError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const lib = await api.library();
      setLibrary(lib);
      setError(null);
      return lib;
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    refresh().then(async (lib) => {
      if (lib?.rebuild_running) {
        const { jobs } = await api.jobs("rebuild");
        const active = jobs.find(
          (j) => j.status === "queued" || j.status === "running",
        );
        if (active) setJobId(active.id);
      }
    });
  }, [refresh]);

  const job = useJob(jobId, () => refresh());
  const rebuilding =
    job && (job.status === "queued" || job.status === "running");

  const guard = async (fn) => {
    setActionError(null);
    try {
      return await fn();
    } catch (err) {
      setActionError(err.message);
      throw err;
    }
  };

  const startRebuild = async (chunking) => {
    setStarting(true);
    try {
      const j = await guard(() => api.rebuild(chunking));
      setJobId(j.id);
    } catch {
      /* shown via actionError */
    } finally {
      setStarting(false);
    }
  };

  const upload = async (dept, files) => {
    const res = await api.upload(dept, files);
    await refresh();
    return res;
  };

  const addFolder = async (e) => {
    e.preventDefault();
    if (!folderName.trim()) return;
    try {
      await guard(() => api.createFolder(folderName.trim()));
      setFolderName("");
      await refresh();
    } catch {
      /* shown via actionError */
    }
  };

  if (error && !library) {
    return (
      <div className="page">
        <h1>Documents</h1>
        <div className="notice notice-error">{error}</div>
      </div>
    );
  }
  if (!library) {
    return (
      <div className="page">
        <h1>Documents</h1>
        <div className="run-bar">
          <span className="spinner" />{" "}
          <span className="muted">Loading library…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1>Documents</h1>
        <p className="muted">
          {library.total_documents} document(s) across{" "}
          {library.departments.length} folder(s). Changes here edit the files on
          disk; rebuild the index to make them searchable.
        </p>
      </header>

      {actionError && <div className="notice notice-error">{actionError}</div>}

      <RebuildPanel
        index={library.index}
        job={job}
        onStart={startRebuild}
        starting={starting}
      />

      <div className="two-col">
        <div className="col">
          <form className="folder-form" onSubmit={addFolder}>
            <input
              className="text-input"
              placeholder="Add a folder, e.g. finance"
              value={folderName}
              onChange={(e) => setFolderName(e.target.value)}
              disabled={rebuilding}
            />
            <button
              type="submit"
              className="btn btn-secondary"
              disabled={rebuilding || !folderName.trim()}
            >
              Add folder
            </button>
          </form>
          <DocumentList
            departments={library.departments}
            disabled={rebuilding}
            onDelete={async (dept, file) => {
              await guard(() => api.deleteDocument(dept, file)).catch(() => {});
              await refresh();
            }}
            onDeleteFolder={async (name) => {
              await guard(() => api.deleteFolder(name)).catch(() => {});
              await refresh();
            }}
          />
        </div>
        <div className="col">
          <UploadForm
            departments={library.departments}
            onUpload={upload}
            disabled={rebuilding}
          />
        </div>
      </div>
    </div>
  );
}
