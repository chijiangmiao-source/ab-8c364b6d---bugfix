import type { AuditResponse, SolutionOut } from "../types";

interface ResultsProps {
  result: AuditResponse;
  selectedTie: number;
  onSelectTie: (index: number) => void;
}

const CLASS_LABEL: Record<string, { text: string; cls: string }> = {
  always: { text: "所有", cls: "tag always" },
  partial: { text: "部分", cls: "tag partial" },
  never: { text: "从不", cls: "tag never" },
};

export function ResultsPanel({ result, selectedTie, onSelectTie }: ResultsProps) {
  const sol: SolutionOut | undefined =
    result.tied[selectedTie] ?? result.solution ?? undefined;

  return (
    <section className="results">
      <h2>② 最小端元解释</h2>
      {result.feasible && sol ? (
        <>
          <p className="summary">
            正权端元 <strong>{sol.ids.length}</strong> 个 · 复核代价和{" "}
            <strong>{sol.cost}</strong> · 两级同优解共{" "}
            <strong>{result.tie_count}</strong> 组
          </p>

          <table className="weight-table">
            <thead>
              <tr>
                <th>端元</th>
                <th>规范权重（精确分数）</th>
                <th>小数</th>
                <th>占比</th>
                <th>归类</th>
              </tr>
            </thead>
            <tbody>
              {sol.weights.map((w) => {
                const tag = CLASS_LABEL[result.classification[w.id] ?? "never"];
                return (
                  <tr key={w.id}>
                    <td className="mono">{w.id}</td>
                    <td className="mono frac">{w.fraction}</td>
                    <td className="mono">
                      {w.decimal.toFixed(w.denominator > 1 ? 6 : 0)}
                    </td>
                    <td>
                      <div className="bar-cell">
                        <div
                          className="bar"
                          style={{ width: `${Math.max(w.decimal * 100, 1.5)}%` }}
                        />
                        <span>{(w.decimal * 100).toFixed(2)}%</span>
                      </div>
                    </td>
                    <td>
                      <span className={tag.cls}>{tag.text}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {result.tie_count > 1 && (
            <div className="ties">
              <span>同优解：</span>
              {result.tied.map((s, i) => (
                <button
                  key={s.ids.join("|")}
                  type="button"
                  className={i === selectedTie ? "tie active" : "tie"}
                  onClick={() => onSelectTie(i)}
                >
                  {s.ids.join(" + ")}
                </button>
              ))}
            </div>
          )}
        </>
      ) : (
        !result.errors.length && (
          <div className="infeasible">
            <strong>凸包外无解。</strong>
            目标点不在任一端元凸组合的覆盖范围内，不存在非负权重和为 1 的精确表示。
            已保留当前编辑内容，可调整端元示踪值或目标后重新审计。
          </div>
        )
      )}
    </section>
  );
}
