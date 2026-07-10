// Server-rendered SVG line chart, no client JS required (native <title>
// gives a basic hover readout). Per the dataviz skill: one hue, 2px line,
// rounded data-end caps, direct label on the last point, recessive
// gridlines, a single series so no legend box is needed (the caption names
// it). Colorblind-safe by construction — only one series drawn.
type Point = { x: number; y: number; label?: string };

export default function LearningCurveChart({
  points,
  refBand,
  yFmt = (v: number) => v.toFixed(2),
  width = 640,
  height = 220,
}: {
  points: Point[];
  refBand?: [number, number];
  yFmt?: (v: number) => string;
  width?: number;
  height?: number;
}) {
  const pad = { l: 46, r: 46, t: 16, b: 30 };
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xMin = Math.min(...xs),
    xMax = Math.max(...xs);
  const yMax = Math.max(0.5, ...ys, ...(refBand ?? []));
  const yMin = 0;
  const X = (x: number) => pad.l + (xMax === xMin ? innerW / 2 : ((x - xMin) / (xMax - xMin)) * innerW);
  const Y = (y: number) => pad.t + innerH - ((y - yMin) / (yMax - yMin)) * innerH;

  const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${X(p.x).toFixed(1)} ${Y(p.y).toFixed(1)}`).join(" ");
  const gridYs = [0, 0.25, 0.5, 0.75, 1].filter((g) => g <= yMax + 0.001);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label="Segment PR-AUC vs training-permit count">
      {refBand && (
        <rect
          x={pad.l}
          y={Y(refBand[1])}
          width={innerW}
          height={Y(refBand[0]) - Y(refBand[1])}
          fill="var(--muted)"
          opacity={0.12}
        />
      )}
      {gridYs.map((g) => (
        <g key={g}>
          <line x1={pad.l} x2={width - pad.r} y1={Y(g)} y2={Y(g)} stroke="var(--line)" strokeWidth={1} />
          <text x={pad.l - 8} y={Y(g)} dy={4} textAnchor="end" fontSize={10.5} fill="var(--muted)" fontFamily="var(--font-mono)">
            {g.toFixed(2)}
          </text>
        </g>
      ))}
      {points.map((p) => (
        <text
          key={`xl-${p.x}`}
          x={X(p.x)}
          y={height - 8}
          textAnchor="middle"
          fontSize={10.5}
          fill="var(--muted)"
          fontFamily="var(--font-mono)"
        >
          {p.x}
        </text>
      ))}
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={X(p.x)} cy={Y(p.y)} r={4.5} fill="var(--surface)" stroke="var(--accent)" strokeWidth={2}>
            <title>{`${p.x} permits · PR-AUC ${yFmt(p.y)}`}</title>
          </circle>
          {i === points.length - 1 && (
            <text x={X(p.x) + 8} y={Y(p.y) - 8} fontSize={11.5} fontWeight={700} fill="var(--accent-ink)" fontFamily="var(--font-mono)">
              {yFmt(p.y)}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}
