import type { EndmemberRow } from "../types";

interface EditorProps {
  endmembers: EndmemberRow[];
  target: [string, string, string];
  errorsByField: Map<string, string>;
  onChange: (rows: EndmemberRow[]) => void;
  onTargetChange: (t: [string, string, string]) => void;
  onAudit: () => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
  loading: boolean;
  batchError?: string;
}

const TRACER_HEADERS = ["X", "Y", "Z"];

export function Editor({
  endmembers,
  target,
  errorsByField,
  onChange,
  onTargetChange,
  onAudit,
  onAdd,
  onRemove,
  loading,
  batchError,
}: EditorProps) {
  const update = (i: number, key: keyof EndmemberRow, value: string) => {
    const rows = endmembers.map((r, idx) => (idx === i ? { ...r, [key]: value } : r));
    onChange(rows);
  };

  const err = (field: string) => errorsByField.get(field);
  const cellCls = (field: string) => (err(field) ? "cell cell-err" : "cell");

  return (
    <section className="editor">
      <div className="editor-head">
        <h2>① 编辑喷发端元与目标</h2>
        <div className="head-actions">
          <button type="button" onClick={onAdd} disabled={endmembers.length >= 30}>
            ＋ 添加端元
          </button>
          <button type="button" className="primary" onClick={onAudit} disabled={loading}>
            {loading ? "审计中…" : "发起审计"}
          </button>
        </div>
      </div>

      {batchError && <div className="batch-error">{batchError}</div>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>标识</th>
              <th>示踪值 1</th>
              <th>示踪值 2</th>
              <th>示踪值 3</th>
              <th>复核代价</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {endmembers.map((row, i) => (
              <tr key={i}>
                <td>
                  <input
                    className={cellCls(`endmembers[${i}].id`)}
                    value={row.id}
                    onChange={(e) => update(i, "id", e.target.value)}
                    placeholder="A"
                  />
                </td>
                {(["t0", "t1", "t2"] as const).map((key, j) => (
                  <td key={key}>
                    <input
                      className={cellCls(`endmembers[${i}].${key}`)}
                      value={row[key]}
                      onChange={(e) => update(i, key, e.target.value)}
                      inputMode="decimal"
                      aria-label={`端元 ${row.id || i + 1} 示踪值 ${TRACER_HEADERS[j]}`}
                    />
                  </td>
                ))}
                <td>
                  <input
                    className={cellCls(`endmembers[${i}].cost`)}
                    value={row.cost}
                    onChange={(e) => update(i, "cost", e.target.value)}
                    inputMode="numeric"
                    aria-label={`端元 ${row.id || i + 1} 复核代价`}
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="del"
                    onClick={() => onRemove(i)}
                    disabled={endmembers.length <= 3}
                    title={endmembers.length <= 3 ? "至少保留 3 个端元" : "删除此行"}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="target-row">
        <span className="target-label-edit">目标三值（至多四位小数）：</span>
        {(["x", "y", "z"] as const).map((_, j) => (
          <input
            key={j}
            className={cellCls(`target[${j}]`)}
            value={target[j]}
            onChange={(e) => {
              const next = [...target] as [string, string, string];
              next[j] = e.target.value;
              onTargetChange(next);
            }}
            inputMode="decimal"
            aria-label={`目标示踪值 ${TRACER_HEADERS[j]}`}
          />
        ))}
      </div>

      <ErrorTray errorsByField={errorsByField} />
    </section>
  );
}

function ErrorTray({ errorsByField }: { errorsByField: Map<string, string> }) {
  if (errorsByField.size === 0) return null;
  return (
    <ul className="error-tray">
      {[...errorsByField.entries()].map(([field, message]) => (
        <li key={field}>
          <code>{field}</code>：{message}
        </li>
      ))}
    </ul>
  );
}
