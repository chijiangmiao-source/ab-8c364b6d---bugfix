import { useMemo } from "react";

export interface PlotPoint {
  id: string;
  xyz: [number, number, number];
  weight: number; // 0 if not in the active solution
  klass: "always" | "partial" | "never" | null;
  inSolution: boolean;
}

interface ProjectionProps {
  title: string;
  axisLabels: [string, string];
  // Maps a 3D point to the two projected coordinates.
  project: (p: [number, number, number]) => [number, number];
  points: PlotPoint[];
  target: [number, number, number] | null;
  supportEdges: [string, string][];
  hoverId: string | null;
  onHover: (id: string | null) => void;
}

const COLORS: Record<NonNullable<PlotPoint["klass"]>, string> = {
  always: "#16a34a",
  partial: "#d97706",
  never: "#9ca3af",
};

export function Projection({
  title,
  axisLabels,
  project,
  points,
  target,
  supportEdges,
  hoverId,
  onHover,
}: ProjectionProps) {
  const W = 360;
  const H = 300;
  const PAD = 42;

  const geometry = useMemo(() => {
    const projected = points.map((p) => ({ p, uv: project(p.xyz) }));
    const tuv = target ? project(target) : null;
    const all = [...projected.map((q) => q.uv), ...(tuv ? [tuv] : [])];
    if (all.length === 0) return null;
    const minU = Math.min(...all.map((q) => q[0]));
    const maxU = Math.max(...all.map((q) => q[0]));
    const minV = Math.min(...all.map((q) => q[1]));
    const maxV = Math.max(...all.map((q) => q[1]));
    const spanU = Math.max(maxU - minU, 1e-9);
    const spanV = Math.max(maxV - minV, 1e-9);
    const scale = Math.min((W - 2 * PAD) / spanU, (H - 2 * PAD) / spanV);
    // keep aspect ratio 1:1 for faithful geometry
    const toScreen = (uv: [number, number]): [number, number] => [
      PAD + (uv[0] - minU) * scale + ((W - 2 * PAD) - spanU * scale) / 2,
      H - PAD - (uv[1] - minV) * scale - ((H - 2 * PAD) - spanV * scale) / 2,
    ];
    const byId = new Map(projected.map((q) => [q.p.id, toScreen(q.uv)]));
    return {
      nodes: projected.map((q) => ({ p: q.p, xy: toScreen(q.uv) })),
      targetXY: tuv ? toScreen(tuv) : null,
      byId,
    };
  }, [points, target, project]);

  return (
    <div className="projection">
      <h3>{title}</h3>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
        <rect x="0" y="0" width={W} height={H} rx="8" className="plot-bg" />
        {/* axes */}
        <line x1={PAD} y1={H - PAD} x2={W - 12} y2={H - PAD} className="axis" />
        <line x1={PAD} y1={H - PAD} x2={PAD} y2={12} className="axis" />
        <text x={W - 14} y={H - PAD - 6} className="axis-label">
          {axisLabels[0]}
        </text>
        <text x={PAD + 6} y={16} className="axis-label">
          {axisLabels[1]}
        </text>

        {geometry &&
          supportEdges.map(([a, b], i) => {
            const pa = geometry.byId.get(a);
            const pb = geometry.byId.get(b);
            if (!pa || !pb) return null;
            return (
              <line
                key={i}
                x1={pa[0]}
                y1={pa[1]}
                x2={pb[0]}
                y2={pb[1]}
                className="support-edge"
              />
            );
          })}

        {geometry?.targetXY && (
          <g>
            <line
              x1={geometry.targetXY[0] - 8}
              y1={geometry.targetXY[1] - 8}
              x2={geometry.targetXY[0] + 8}
              y2={geometry.targetXY[1] + 8}
              className="target-mark"
            />
            <line
              x1={geometry.targetXY[0] - 8}
              y1={geometry.targetXY[1] + 8}
              x2={geometry.targetXY[0] + 8}
              y2={geometry.targetXY[1] - 8}
              className="target-mark"
            />
            <text
              x={geometry.targetXY[0] + 10}
              y={geometry.targetXY[1] - 8}
              className="target-label"
            >
              目标
            </text>
          </g>
        )}

        {geometry?.nodes.map(({ p, xy }) => {
          const color = p.klass ? COLORS[p.klass] : "#cbd5e1";
          const r = p.inSolution ? 6 + 12 * p.weight : 4;
          const dim = hoverId !== null && hoverId !== p.id;
          return (
            <g
              key={p.id}
              transform={`translate(${xy[0]},${xy[1]})`}
              className="point-g"
              opacity={dim ? 0.3 : 1}
              onMouseEnter={() => onHover(p.id)}
              onMouseLeave={() => onHover(null)}
            >
              <circle r={r + 3} className="point-ring" />
              <circle r={r} fill={color} stroke="#1f2937" strokeWidth={1.2} />
              <text x={r + 4} y={4} className="point-label">
                {p.id}
                {p.inSolution && p.weight > 0 ? ` ${(p.weight * 100).toFixed(1)}%` : ""}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
