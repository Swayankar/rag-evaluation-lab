import { useWorkspace } from "../context/WorkspaceContext.jsx";

export default function ReadOnly({ children, className = "" }) {
  const { readOnly } = useWorkspace();
  return (
    <fieldset
      className={`ro-fieldset ${readOnly ? "is-readonly" : ""} ${className}`}
      disabled={readOnly}
    >
      {children}
    </fieldset>
  );
}
