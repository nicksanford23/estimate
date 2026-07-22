"use client";

import { useMemo, useState } from "react";
import type { GeometryReviewData } from "@/lib/v2Db";

// Geometry Review — matches design_specs/geometry_review_APPROVED.png:
// run card (left) + region/run verdict rows, center canvas, right issues
// queue. HONEST DEVIATION from the mockup: the backfilled legacy runs
// (data/takeoff/*/run.json) carry per-room area_sf/product_action/flags but
// NO full vector polygon rings — only a pre-baked overlay JPEG (overlay_path)
// with colors already burned in. New project runs retain polygon bounds, but
// the current canvas does not yet use them as an editable mask/ring. So the
// canvas is still the fused raster, issue cards still show the full overlay,
// and toggle pills remain disabled per the "nothing fake-works" rule.

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

  // "Green" is EARNED, not self-declared: a room is verified only if its
  // measured SF matches the finish-schedule answer key (grade='match'). Rooms
  // the engine called auto_quantity but that DISAGREE with the schedule are the
  // most important thing to review — they are NOT verified.
  const matched = run ? run.polys.filter((p) => p.grade === "match") : [];
  const issues = useMemo(
    () =>
      run
        ? run.polys
            .filter((p) => p.grade !== "match")
            // disagreements-with-schedule first (worst error at top), then the rest
            .sort((a, b) => {
              const rank = (g: string) => (g === "off" ? 0 : 1);
              if (rank(a.grade) !== rank(b.grade)) return rank(a.grade) - rank(b.grade);
              return Math.abs(b.error_pct ?? 0) - Math.abs(a.error_pct ?? 0);
            })
        : [],
    [run]
  );
  const bulkAcceptable = run?.schedule_reference_state === "eligible" ? matched : [];
  const unverifiedAuto = bulkAcceptable.filter((p) => !polyVerdict.get(p.polygon_prediction_id));

  if (!runs.length) {
    return (
      <div className="v2board">
        <div className="v2board-main">
          <div className="page-head"><a href={`/v2/b/${data?.permit}`} style={{ fontSize: 13 }}>&larr; {data?.building?.building_name ?? data?.permit}</a></div>
          <h1>{data?.building?.building_name ?? data?.permit}</h1>
          <div className="legacy-banner">
            Internal / legacy geometry diagnostic — not part of normal navigation. The product path is now{" "}
            <a href={`/v2/b/${data?.permit}/floor-areas`}>Floor Areas</a>.
          </div>
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
  const recommendation = !run
    ? ""
    : run.schedule_reference_state === "legacy_unverified"
      ? "Diagnostic only — the schedule reference is legacy/unverified."
      : run.schedule_reference_state === "none"
        ? "Diagnostic only — no eligible area schedule is available for comparison."
        : issues.length > 0
          ? `Do not approve — ${issues.length} polygon${issues.length === 1 ? "" : "s"} disagree or cannot be checked.`
          : !run.training_eligible && !run.evaluation_eligible && !run.demo_eligible
            ? "Diagnostic only — this run has no evidence eligibility approval."
            : "Candidate for human approval — all comparable polygons match the qualified schedule reference.";

  function verdictDisabled(verdict: string) {
    if (!run || !curRegionVerdict || busy === "run") return true;
    if (verdict === "approved_training") return !run.training_eligible || issues.length > 0;
    if (verdict === "approved_eval") return !run.evaluation_eligible || issues.length > 0;
    return false;
  }

  function verdictTitle(verdict: string) {
    if (!curRegionVerdict) return "set a region verdict first (SCHEMA_V2 §14)";
    if (verdict === "approved_training" && !run?.training_eligible) return "blocked: run is not eligible for boundary training";
    if (verdict === "approved_eval" && !run?.evaluation_eligible) return "blocked: run is not eligible for SF evaluation";
    if ((verdict === "approved_training" || verdict === "approved_eval") && issues.length > 0) return "blocked: unresolved schedule disagreements or unidentified polygons";
    return undefined;
  }

  return (
    <div className="grv-wrap">
      <div className="page-head" style={{ padding: "0 18px" }}>
        <a href={`/v2/b/${data!.permit}`} style={{ fontSize: 13 }}>&larr; {data!.building?.building_name ?? data!.permit}</a>
      </div>
      <div className="page-head" style={{ padding: "0 18px" }}>
        <h1 style={{ marginBottom: 2 }}>{data!.building?.building_name ?? data!.permit}</h1>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--muted)" }}>{data!.permit}</span>
      </div>
      <div style={{ padding: "0 18px" }}>
        <div className="legacy-banner">
          Internal / legacy geometry diagnostic — schedule-area agreement here never approves geometry. The product
          path is now <a href={`/v2/b/${data!.permit}/floor-areas`}>Floor Areas</a>.
        </div>
      </div>

      {runs.length > 1 && (
        <div style={{ padding: "8px 18px", display: "flex", gap: 6 }}>
          {runs.map((r, i) => (
            <button key={r.run_id} className={`btn${i === runIdx ? " primary" : ""}`} onClick={() => setRunIdx(i)}>
              {r.sheet_title ?? `page ${r.pdf_page_index ?? "?"}`} · {r.engine_label} · run {r.run_no}
            </button>
          ))}
        </div>
      )}

      <div className="grv-cols">
        <div className="grv-runcard">
          <div className="eyebrow">Run {run!.run_no} &middot; region: {run!.sheet_title ?? "plan viewport"}</div>
          <div className="grv-kv"><span>Engine</span><b>{run!.engine_label}</b></div>
          <div className="grv-kv"><span>Scale</span><b>{run!.scale_text ?? "—"}</b></div>
          <div className="grv-kv"><span>Rooms proposed</span><b>{run!.polys.length}</b></div>
          <div className="grv-kv"><span title="measured SF within ±10% of the schedule reference">{run!.schedule_reference_state === "eligible" ? "Verified vs schedule" : "Matches reference"}</span><b style={{ color: matched.length ? "var(--good)" : "var(--muted)" }}>{matched.length}</b></div>
          <div className="grv-kv"><span title="measured, but disagrees with the schedule or has no schedule row to check">Need review</span><b style={{ color: issues.length ? "var(--bad)" : "var(--muted)" }}>{issues.length}</b></div>
          <div className="grv-kv"><span>Evidence state</span><b style={{ color: run!.schedule_reference_state === "eligible" ? "var(--good)" : "var(--warn)" }}>{run!.schedule_reference_state.replaceAll("_", " ")}</b></div>

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
                disabled={verdictDisabled(v)}
                title={verdictTitle(v)}
                onClick={() => setRunV(v)}
              >
                {RUN_VERDICT_LABEL[v]}
              </button>
            ))}
          </div>
          <p style={{ fontSize: 11.5, color: issues.length || run!.schedule_reference_state !== "eligible" ? "var(--warn)" : "var(--muted)", marginTop: 10 }}>
            {recommendation}
          </p>
          {err && <div style={{ color: "var(--bad)", fontSize: 12, marginTop: 6 }}>{err}</div>}
        </div>

        <div className="grv-canvas">
          <div className="grv-togglepills">
            <span className="chip" style={{ borderStyle: "solid", borderColor: "var(--accent)" }}>source + polygons (baked)</span>
            <span className="chip" style={{ opacity: 0.5 }} title="coming in v1 — needs vector geom_json">labels only</span>
            <span className="chip" style={{ opacity: 0.5 }} title="coming in v1 — needs vector geom_json">previous run</span>
          </div>
          <p style={{ margin: "4px 8px 8px", color: "var(--warn)", fontSize: 11.5 }}>
            Baked overlay colors show the legacy engine&apos;s confidence, not current verification. Use the reference comparison at right.
          </p>
          {overlaySrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={overlaySrc} alt="plan overlay" className="grv-canvas-img" />
          ) : (
            <p style={{ color: "var(--muted)" }}>No render available for this run.</p>
          )}
        </div>

        <div className="grv-issues">
          <div className="eyebrow">Need review ({issues.length}) — measured but unverified vs schedule</div>
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
                    {i + 1}. {p.room ? `room ${p.room}` : "unlabeled shape"}
                    {p.grade === "off" && <span className="chip" style={{ marginLeft: 6, borderColor: "var(--bad)", color: "var(--bad)" }}>disagrees w/ schedule</span>}
                    {p.grade === "none" && p.room && <span className="chip" style={{ marginLeft: 6 }}>no schedule row</span>}
                    {p.grade === "none" && !p.room && <span className="chip" style={{ marginLeft: 6 }}>unlabeled</span>}
                  </div>
                  {p.answer_key_sf != null ? (
                    <div style={{ fontSize: 11.5, marginTop: 2 }}>
                      measured <b>{p.area_sf} SF</b> vs schedule <b>{p.answer_key_sf} SF</b>{" "}
                      <span style={{ color: "var(--bad)", fontWeight: 700 }}>({p.error_pct! > 0 ? "+" : ""}{p.error_pct}%)</span>
                    </div>
                  ) : (
                    <div style={{ fontSize: 11.5, color: "var(--muted)" }}>
                      {p.area_sf != null ? `${p.area_sf} SF measured` : "—"} {p.flags.length ? `· ${p.flags.join(", ")}` : ""}
                    </div>
                  )}
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
              {run!.schedule_reference_state === "eligible"
                ? `${matched.length} rooms match the qualified schedule (±10%) — ${issues.length} disagree or can't be checked`
                : `${matched.length} rooms match an unqualified reference (±10%) — bulk acceptance is disabled`}
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
