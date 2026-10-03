import { EXAMPLE_QUESTIONS } from "../constants/strategies.js";

export default function QuestionInput({
  value,
  onChange,
  topK,
  onTopKChange,
  onSubmit,
  disabled,
}) {
  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !disabled) onSubmit();
  };

  return (
    <div className="card question-input">
      <label className="field-label" htmlFor="question">
        Your question
      </label>
      <textarea
        id="question"
        rows={3}
        value={value}
        placeholder="Ask something about the company documents…"
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      <div className="question-footer">
        <div className="examples">
          <span className="muted small">Try:</span>
          {EXAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              className="chip chip-ghost"
              onClick={() => onChange(q)}
              disabled={disabled}
            >
              {q.length > 44 ? q.slice(0, 44) + "…" : q}
            </button>
          ))}
        </div>
        <label className="topk">
          <span className="muted small">Top-K</span>
          <select
            value={topK}
            onChange={(e) => onTopKChange(Number(e.target.value))}
            disabled={disabled}
          >
            {[1, 3, 5, 8, 10, 15, 20].map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}
