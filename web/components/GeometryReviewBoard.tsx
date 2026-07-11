"use client";

import { useMemo, useState } from "react";
import V2Tabs from "@/components/V2Tabs";
import type { GeometryReviewData } from "@/lib/v2Db";

// Geometry Review — matches design_specs/geometry_review_APPROVED.png:
// run card (left) + region/run verdict rows, center canvas, right issues
// queue. HONEST DEVIATION from the mockup: the backfilled legacy runs
// (data/takeoff/*/run.json) carry per-room area_sf/product_action/flags but
// NO vector polygon coordinates — only a pre-baked overlay JPEG
// (overlay_path) with colors already burned in. So the canvas here is that
// raster image (source+polygons already fused, can't be toggled
// independently) instead of a live SVG overlay, and issue-card "crops" are
// the same full overlay image (no bbox to crop to) rather than real
// per-room crops. Toggle pills are stubbed disabled to be honest about
// this, per the "visible verb set, nothing fake-works" rule.

type Props = { data: GeometryReviewData };

const REGION_VERDICTS = ["usable", "partial", "unusable", "wrong_viewport", "wrong_scale"] as const;
const RUN_VERDICTS = ["approved_training", "approved_eval", "diagnostic", "rejected"] as const;
const RUN_VERDICT_LABEL: Record<string, string> = {
  approved_training: "approved for training",
  approved_eval: "approved for eval",
  diagnostic: "diagnostic only",
  rejected: "rejected",
};

// context-aware verdict buttons per product_action (SCHEMA_V2 §14)
function verdictOptionsFor(productAction: string | null): string[] {
  if (productAction === "open_zone_split") return ["open_zone", "split", "merged", "boundary_fix", "fake"];
  return ["correct", "missed", "merged", "split", "fake", "wrong_label", "boundary_fix"];
}

async function postDecide(body: Record<string, unknown>) {
  const res = await fetch("/api/v2/decide", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const d = await res.json();
  if (!res.ok) throw new Error(d.error ?? "decide failed");
  return d as { decision_id: number };
}

export default function GeometryReviewBoard({ data }: Props) {
  const runs = data?.runs ?? [];
  const [runIdx, setRunIdx] = useState(0);
  const run = runs[runIdx] ?? null;

  const [regionVerdict, setRegionVerdict] = useState<Map<number, string>>(
    () => new Map(runs.map((r) => [r.region_id, r.region_verdict ?? ""] as const).filter(([, v]) => v))
  );
  const [runVerdict, setRunVerdict] = useState<Map<number, string>>(
    () => new Map(runs.map((r) => [r.run_id, r.run_verdict ?? ""] as const).filter(([, v]) => v))
  );
  const [polyVerdict, setPolyVerdict] = useState<Map<number, string>>(
    () => new Map(runs.flatMap((r) => r.polys.map((p) => [p.polygon_prediction_id, p.verdict ?? ""] as const)).filter(([, v]) => v))
  );
  const [selectedPoly, setSelectedPoly] = useState<number | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lastDecisionIds, setLastDecisionIds] = useState<Record<string, number>>({});

  const issues = useMemo(
    () => (run ? run.polys.filter((p) => p.product_action !== "auto_quantity" || !!p.flags.length) : []),
    [run]
  );
  const autoVerified = run ? run.polys.filter((p) => p.product_action === "auto_quantity") : [];
  const unverifiedAuto = autoVerified.filter((p) => !polyVerdict.get(p.polygon_prediction_id));

  if (!runs.length) {
    return (
      <div className="v2board">
        <div className="v2board-main">
          <div className="page-head"><a href={`/v2/b/${data?.permit}`} style={{ fontSize: 13 }}>&larr; {data?.building?.building_name ?? data?.permit}</a></div>
          <h1>{data?.building?.building_name ?? data?.permit}</h1>
          <V2Tabs permit={data?.permit ?? ""} active="geometry" />
          <p style={{ color: "var(--muted)", marginTop: 24 }}>No geometry runs yet for this building.</p>
        </div>
      </div>
    );
  }

  async function setRegionV(v: string) {
    if (!run) return;
    setBusy("region"); setErr(null);
    try {
      const d = await postDecide({ target_type: "region", target_id: run.region_id, claim: "region_geometry_verdict", value_json: { verdict: v } });
      setRegionVerdict((m) => new Map(m).set(run.region_id, v));
      setLastDecisionIds((s) => ({ ...s, region: d.decision_id }));
    } catch (e) { setErr(e instanceof Error ? e.message : "error"); } finally { setBusy(null); }
  }

  async function setRunV(v: string) {
    if (!run) return;
    setBusy("run"); setErr(null);
    try {
      const d = await postDecide({ target_type: "geometry_run", target_id: run.run_id, claim: "run_verdict", value_json: { verdict: v } });
      setRunVerdict((m) => new Map(m).set(run.run_id, v));
      setLastDecisionIds((s) => ({ ...s, run: d.decision_id }));
    } catch (e) { setErr(e instanceof Error ? e.message : "error"); } finally { setBusy(null); }
  }

  async function setPolyV(polyId: number, v: string) {
    setBusy(`poly-${polyId}`); setErr(null);
    try {
      const d = await postDecide({ target_type: "polygon_prediction", target_id: polyId, claim: "room_verdict", value_json: { verdict: v } });
      setPolyVerdict((m) => new Map(m).set(polyId, v));
      setLastDecisionIds((s) => ({ ...s, [`poly-${polyId}`]: d.decision_id }));
    } catch (e) { setErr(e instanceof Error ? e.message : "error"); } finally { setBusy(null); }
  }

  async function acceptAllAuto() {
    setBusy("acceptall");
    for (const p of unverifiedAuto) {
      // eslint-disable-next-line no-await-in-loop
      await setPolyV(p.polygon_prediction_id, "correct");
    }
    setBusy(null);
  }

  const curRegionVerdict = run ? regionVerdict.get(run.region_id) ?? null : null;
  const curRunVerdict = run ? runVerdict.get(run.run_id) ?? null : null;
  const overlaySrc = run?.overlay_path ? `/api/v2/geomoverlay?path=${encodeURIComponent(run.overlay_path)}` : null;

  return (
    <div className="grv-wrap">
      <div className="page-head" style={{ padding: "0 18px" }}>
        <a href={`/v2/b/${data!.permit}`} style={{ fontSize: 13 }}>&larr; {data!.building?.building_name ?? data!.permit}</a>
      </div>
      <div className="page-head" style={{ padding: "0 18px" }}>
        <h1 style={{ marginBottom: 2 }}>{data!.building?.building_name ?? data!.permit}</h1>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--muted)" }}>{data!.permit}</span>
      </div>
      <div style={{ padding: "0 18px" }}><V2Tabs permit={data!.permit} active="geometry" /></div>

      {runs.length > 1 && (
        <div style={{ padding: "8px 18px", display: "flex", gap: 6 }}>
          {runs.map((r, i) => (
            <button key={r.run_id} className={`btn${i === runIdx ? " primary" : ""}`} onClick={() => setRunIdx(i)}>
              Run {r.run_no}
            </button>
          ))}
        </div>
      )}

      <div className="grv-cols">
        <div className="grv-runcard">
          <div className="eyebrow">Run {run!.run_no} &middot; region: {run!.sheet_title ?? "plan viewport"}</div>
          <div className="grv-kv"><span>Engine</span><b>legacy dual (rules-v4 + wall_model_v?)</b></div>
          <div className="grv-kv"><span>Scale</span><b>{run!.scale_text ?? "—"}</b></div>
          <div className="grv-kv"><span>Rooms proposed</span><b>{run!.polys.length}</b></div>
          <div className="grv-kv"><span>Anchored to labels</span><b>{autoVerified.length}</b></div>
          <div className="grv-kv"><span>Flagged</span><b>{issues.length}</b></div>

          <div className="eyebrow" style={{ marginTop: 14 }}>Region verdict</div>
          <div className="grv-btnrow">
            {REGION_VERDICTS.map((v) => (
              <button key={v} className={`btn${curRegionVerdict === v ? " primary" : ""}`} disabled={busy === "region"} onClick={() => setRegionV(v)}>
                {v.replace("_", " ")}
              </button>
            ))}
          </div>

          <div className="eyebrow" style={{ marginTop: 14 }}>Run verdict</div>
          <div className="grv-btnrow">
            {RUN_VERDICTS.map((v) => (
              <button
                key={v}
                className={`btn${curRunVerdict === v ? " primary" : ""}${v === "rejected" ? " grv-danger" : ""}`}
                disabled={!curRegionVerdict || busy === "run"}
                title={!curRegionVerdict ? "set a region verdict first (SCHEMA_V2 §14)" : undefined}
                onClick={() => setRunV(v)}
              >
                {RUN_VERDICT_LABEL[v]}
              </button>
            ))}
          </div>
          {run!.summary && (
            <p style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 10 }}>
              Recommend: {run!.summary.n_open ? "eval" : "training"} — {run!.summary.n_open ?? 0} unresolved open zone{(run!.summary.n_open ?? 0) === 1 ? "" : "s"}
            </p>
          )}
          {err && <div style={{ color: "var(--bad)", fontSize: 12, marginTop: 6 }}>{err}</div>}
        </div>

        <div className="grv-canvas">
          <div className="grv-togglepills">
            <span className="chip" style={{ borderStyle: "solid", borderColor: "var(--accent)" }}>source + polygons (baked)</span>
            <span className="chip" style={{ opacity: 0.5 }} title="coming in v1 — needs vector geom_json">labels only</span>
            <span className="chip" style={{ opacity: 0.5 }} title="coming in v1 — needs vector geom_json">previous run</span>
          </div>
          {overlaySrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={overlaySrc} alt="plan overlay" className="grv-canvas-img" />
          ) : (
            <p style={{ color: "var(--muted)" }}>No render available for this run.</p>
          )}
        </div>

        <div className="grv-issues">
          <div className="eyebrow">Issues ({issues.length})</div>
          {issues.map((p, i) => {
            const v = polyVerdict.get(p.polygon_prediction_id);
            return (
              <div
                key={p.polygon_prediction_id}
                className={`grv-issue${selectedPoly === p.polygon_prediction_id ? " grv-issue-selected" : ""}`}
                onClick={() => setSelectedPoly(p.polygon_prediction_id)}
              >
                <div className="grv-issue-thumbwrap">
                  {overlaySrc && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={overlaySrc} alt="" className="grv-issue-thumb" />
                  )}
                </div>
                <div className="grv-issue-body">
                  <div style={{ fontWeight: 600, fontSize: 12.5 }}>
                    {i + 1}. {p.room ? `room ${p.room}` : "unlabeled shape"} — {p.product_action ?? "flagged"}
                  </div>
                  <div style={{ fontSize: 11.5, color: "var(--muted)" }}>
                    {p.area_sf != null ? `${p.area_sf} SF` : "—"} {p.flags.length ? `· ${p.flags.join(", ")}` : ""}
                  </div>
                  <div className="grv-btnrow" style={{ marginTop: 6 }}>
                    {verdictOptionsFor(p.product_action).map((opt) => (
                      <button
                        key={opt}
                        className={`btn${v === opt ? " primary" : ""}`}
                        disabled={busy === `poly-${p.polygon_prediction_id}`}
                        onClick={(e) => { e.stopPropagation(); setPolyV(p.polygon_prediction_id, opt); }}
                      >
                        {opt.replace("_", " ")}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
          {!issues.length && <p style={{ color: "var(--muted)", fontSize: 13 }}>No flagged rooms in this run.</p>}

          <div className="grv-bulk">
            <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 6 }}>
              {autoVerified.length} rooms auto-verified — review only the {issues.length} flagged above
            </div>
            <button className="btn primary" style={{ width: "100%" }} disabled={busy === "acceptall" || unverifiedAuto.length === 0} onClick={acceptAllAuto}>
              {busy === "acceptall" ? "Accepting…" : `Accept all (${unverifiedAuto.length})`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
