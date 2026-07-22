"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import Link from "next/link";
import { TAXONOMY_V2 } from "@/lib/v2Taxonomy";
import type { V2PageRow } from "@/lib/v2Db";
import V2Tabs from "@/components/V2Tabs";
import { displayTitle, shortDescription, type ProjectDisplayInput } from "@/lib/projectDisplay";

// Page Review board — matches design_specs/page_review_APPROVED.png:
// collapsible per-doc sections of page-card grids + a fixed right side
// panel for the selected page (bottom sheet on mobile). Chip law and trust
// states per SCHEMA_V2.md §14: dashed border = machine-claimed only,
// solid green = human-confirmed (binding decision exists); status badge
// lives in the card corner, never inline with the label.

const KEEP_POLICY = new Set(["floor_plan", "finish_plan", "finish_schedule", "demo_plan"]);

// 8 flag toggles. Stored via claim='page_flags', value_json={flags:[...]}
// on the same append-only /api/v2/decide route used for page_category.
// Canonical 8 flags per SCHEMA_V2 §4 — do not invent alternates.
const FLAGS = [
  { key: "multiple_viewports", label: "multiple viewports" },
  { key: "contains_area_table", label: "contains area table" },
  { key: "scale_visible", label: "scale visible" },
  { key: "finish_codes_visible", label: "finish codes visible" },
  { key: "table_present", label: "table present" },
  { key: "room_labels_visible", label: "room labels visible" },
  { key: "dimensions_visible", label: "dimensions visible" },
  { key: "possible_duplicate", label: "possible duplicate" },
] as const;

type DocGroup = {
  document_id: number;
  onestop_doc_id: string;
  filename: string | null;
  filed_date: string | null;
  pages: V2PageRow[];
};

type PageState = {
  binding: string | null;
  decisionId: number | null;
  trusted: boolean;
  flags: string[];
};

function fmtDate(d: string | null) {
  if (!d) return null;
  try {
    return new Date(d).toLocaleDateString("en-US", { month: "2-digit", day: "2-digit", year: "numeric" });
  } catch {
    return d;
  }
}

function caption(page: V2PageRow, idx: number) {
  const title = page.sheet_title?.trim();
  return `${idx + 1}. ${title || `PDF p.${page.pdf_page_index}`}`;
}

export default function V2ReviewBoard({ permit, building, docs, identity }: { permit: string; building: { building_name: string } | null; docs: DocGroup[]; identity: ProjectDisplayInput | null }) {
  const flat = useMemo(() => docs.flatMap((d) => d.pages), [docs]);
  const [state, setState] = useState<Map<number, PageState>>(
    () => new Map(flat.map((p) => [p.page_id, { binding: p.binding_category, decisionId: p.binding_decision_id, trusted: p.trusted, flags: p.flags }]))
  );
  const [selectedId, setSelectedId] = useState<number | null>(flat[0]?.page_id ?? null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const selectedPage = flat.find((p) => p.page_id === selectedId) ?? null;
  const selectedState = selectedId ? state.get(selectedId) : undefined;
  const [draftCategory, setDraftCategory] = useState<string>("");

  useEffect(() => {
    queueMicrotask(() => {
      setDraftCategory(selectedState?.binding ?? selectedPage?.claude_label?.category ?? "");
      setErr(null);
    });
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Prefetch the neighbouring pages' full panel images so stepping through the
  // set is instant instead of waiting on a fresh round-trip each time (the
  // Codespaces proxy adds real latency per uncached image).
  useEffect(() => {
    const idx = flat.findIndex((p) => p.page_id === selectedId);
    for (const p of [flat[idx + 1], flat[idx - 1], flat[idx + 2]]) {
      if (!p) continue;
      const img = new window.Image();
      img.src = `/api/opspage/${p.onestop_doc_id}/${p.pdf_page_index}?w=1100`;
    }
  }, [selectedId, flat]);

  const confirmedCount = Array.from(state.values()).filter((s) => s.binding).length;
  const trustedCount = Array.from(state.values()).filter((s) => !s.binding && s.trusted).length;
  const totalCount = flat.length;
  const disagreementsLeft = flat.filter(
    (p) => p.machine_state === "disagree" && !state.get(p.page_id)?.binding && !state.get(p.page_id)?.trusted
  ).length;

  async function postDecide(page_id: number, body: Record<string, unknown>) {
    const res = await fetch("/api/v2/decide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ page_id, ...body }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error ?? "decide failed");
    return data;
  }

  async function confirmCategory() {
    if (!selectedPage || !draftCategory) return;
    setBusy(true);
    setErr(null);
    try {
      const data = await postDecide(selectedPage.page_id, { category: draftCategory });
      setState((prev) => {
        const next = new Map(prev);
        const cur = next.get(selectedPage.page_id)!;
        next.set(selectedPage.page_id, { ...cur, binding: draftCategory, decisionId: data.decision_id });
        return next;
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "error");
    } finally {
      setBusy(false);
    }
  }

  async function toggleFlag(flagKey: string) {
    if (!selectedPage || !selectedState) return;
    const current = selectedState.flags;
    const next = current.includes(flagKey) ? current.filter((f) => f !== flagKey) : [...current, flagKey];
    // optimistic
    setState((prev) => {
      const m = new Map(prev);
      m.set(selectedPage.page_id, { ...m.get(selectedPage.page_id)!, flags: next });
      return m;
    });
    try {
      await postDecide(selectedPage.page_id, { claim: "page_flags", value_json: { flags: next } });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "flag save failed");
    }
  }

  // A page is "acted on" once it is confirmed (binding truth) OR trusted
  // (non-binding breadcrumb). Both nav buttons skip acted-on pages.
  const goNext = useCallback(
    (pred: (page: V2PageRow, s: PageState | undefined) => boolean) => {
      const idx = flat.findIndex((p) => p.page_id === selectedId);
      for (let i = idx + 1; i < flat.length; i++) {
        const s = state.get(flat[i].page_id);
        if (!s?.binding && !s?.trusted && pred(flat[i], s)) {
          setSelectedId(flat[i].page_id);
          return true;
        }
      }
      return false;
    },
    [flat, selectedId, state]
  );
  const goNextUnreviewed = useCallback(() => goNext(() => true), [goNext]);
  const goNextDisagreement = useCallback(() => goNext((p) => p.machine_state === "disagree"), [goNext]);

  // "Trust the machine" — record a NON-binding breadcrumb (never truth) and
  // advance. Reversible in spirit: opening the page later and Confirming writes
  // real truth that overrides this in the UI.
  async function trustCurrent() {
    if (!selectedPage) return;
    setBusy(true);
    setErr(null);
    try {
      await postDecide(selectedPage.page_id, { claim: "page_review_status", binding: false, value_json: { status: "trusted" } });
      setState((prev) => {
        const m = new Map(prev);
        m.set(selectedPage.page_id, { ...m.get(selectedPage.page_id)!, trusted: true });
        return m;
      });
      goNextUnreviewed();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "trust failed");
    } finally {
      setBusy(false);
    }
  }

  // Bulk: trust every machine-agreement page not already acted on, so the human
  // is left with only the disagreements. Agreements = both vendors matched
  // (machine_state match|audit).
  const agreementTargets = flat.filter(
    (p) => (p.machine_state === "match" || p.machine_state === "audit") && !state.get(p.page_id)?.binding && !state.get(p.page_id)?.trusted
  );
  async function trustAllAgreements() {
    if (!agreementTargets.length) return;
    setBusy(true);
    setErr(null);
    try {
      await Promise.all(
        agreementTargets.map((p) => postDecide(p.page_id, { claim: "page_review_status", binding: false, value_json: { status: "trusted" } }))
      );
      setState((prev) => {
        const m = new Map(prev);
        agreementTargets.forEach((p) => m.set(p.page_id, { ...m.get(p.page_id)!, trusted: true }));
        return m;
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "bulk trust failed");
    } finally {
      setBusy(false);
    }
  }

  const moveSelection = useCallback(
    (delta: number) => {
      const idx = flat.findIndex((p) => p.page_id === selectedId);
      const next = flat[idx + delta];
      if (next) setSelectedId(next.page_id);
    },
    [flat, selectedId]
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); moveSelection(1); }
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); moveSelection(-1); }
      else if (e.key === "Enter") { e.preventDefault(); confirmCategory(); }
      else if (e.key === "t" || e.key === "T") { e.preventDefault(); trustCurrent(); }
      else if (e.key === "d" || e.key === "D") { e.preventDefault(); goNextDisagreement(); }
      else if (e.key === "f" || e.key === "F") { e.preventDefault(); goNextUnreviewed(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }); // re-bind every render so closures see latest draftCategory/selection

  return (
    <div className="v2board">
      <div className="v2board-main">
        <div className="page-head" style={{ marginBottom: 0 }}>
          <Link href="/v2" style={{ fontSize: 13 }}>&larr; Projects</Link>
          <h1 style={{ margin: "6px 0 2px" }}>{identity ? displayTitle(identity) : building?.building_name ?? permit}</h1>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            {identity && shortDescription(identity.city_description) && (
              <span style={{ color: "var(--muted)", fontSize: 13 }}>{shortDescription(identity.city_description)}</span>
            )}
            <span className="proj-permit" style={{ fontSize: 12 }}>Permit {permit}</span>
          </div>
        </div>
        <V2Tabs permit={permit} active="planset" />

        <p style={{ color: "var(--muted)", fontSize: 13, margin: "0 0 4px" }}>
          Sheets in the active plan set, grouped by document. Confirm each page&rsquo;s role, then see the full{" "}
          <Link href={`/v2/b/${permit}/docs`} style={{ color: "var(--accent-ink)" }}>document list</Link>.
        </p>

        {docs.map((doc) => {
          const confirmed = doc.pages.filter((p) => state.get(p.page_id)?.binding).length;
          return (
            <details key={doc.document_id} className="v2doc" open>
              <summary className="v2doc-summary">
                <span>Arch Set {fmtDate(doc.filed_date) ? `(${fmtDate(doc.filed_date)})` : ""} — {doc.pages.length} pages · doc {doc.onestop_doc_id}</span>
                <span style={{ color: "var(--muted)", fontSize: 12, fontFamily: "var(--font-mono)" }}>{confirmed}/{doc.pages.length} confirmed</span>
              </summary>
              <div className="v2grid">
                {doc.pages.map((page, i) => {
                  const s = state.get(page.page_id)!;
                  const isSelected = page.page_id === selectedId;
                  const thumbSrc = `/api/opspage/${page.onestop_doc_id}/${page.pdf_page_index}?w=560`;
                  const statusLabel = s.binding ? "confirmed" : s.trusted ? "trusted" : page.machine_state;
                  const machineFlags = page.machine_state === "match" || page.machine_state === "audit" ? page.claude_label?.flags ?? [] : [];
                  const displayFlags = s.flags.length ? s.flags : machineFlags;
                  const shownFlags = displayFlags.slice(0, 2);
                  const overflow = displayFlags.length - shownFlags.length;
                  const displayCategory = s.binding ?? ((page.machine_state === "match" || page.machine_state === "audit") ? page.claude_label?.category : null);
                  const hover = s.binding
                    ? `Human confirmed: ${s.binding}`
                    : page.claude_label && page.codex_label
                      ? `Claude: ${page.claude_label.category} · Codex: ${page.codex_label.category}`
                      : "No pilot label run yet";
                  return (
                    <button
                      key={page.page_id}
                      type="button"
                      className={`v2card${isSelected ? " v2card-selected" : ""}`}
                      onClick={() => setSelectedId(page.page_id)}
                    >
                      <div className="v2card-thumbwrap">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={thumbSrc} alt={caption(page, i)} loading="lazy" className="v2card-thumb" />
                        <span className={`v2card-status v2card-status-${statusLabel}`} title={hover}>{statusLabel}</span>
                      </div>
                      <div className="v2card-cap">{caption(page, i)}</div>
                      <div className="v2card-chips">
                        <span
                          className="chip"
                          style={
                            s.binding
                              ? { borderStyle: "solid", borderColor: "var(--good)", color: "var(--good)" }
                              : s.trusted
                                ? { borderStyle: "solid", borderColor: "var(--muted)", color: "var(--muted)" }
                                : { borderStyle: "dashed" }
                          }
                        >
                          {displayCategory ?? (page.machine_state === "disagree" ? "review disagreement" : "unlabeled")}
                        </span>
                        {shownFlags.map((f) => (
                          <span key={f} className="chip">{FLAGS.find((x) => x.key === f)?.label ?? f}</span>
                        ))}
                        {overflow > 0 && <span className="chip">+{overflow}</span>}
                      </div>
                    </button>
                  );
                })}
              </div>
            </details>
          );
        })}
        {docs.length === 0 && <p style={{ color: "var(--muted)" }}>No documents backfilled for this permit.</p>}

        <div className="v2progress">
          <span>{confirmedCount} confirmed · {trustedCount} trusted · {totalCount} pages</span>
          <div className="v2progress-bar"><div className="v2progress-fill" style={{ width: totalCount ? `${(100 * (confirmedCount + trustedCount)) / totalCount}%` : "0%" }} /></div>
          <div className="v2progress-actions">
            {disagreementsLeft > 0 && (
              <button
                type="button"
                className="btn"
                onClick={() => { if (!goNextDisagreement()) goNext(() => true); }}
              >
                Go to next disagreement ({disagreementsLeft}) &rarr;
              </button>
            )}
            {agreementTargets.length > 0 && (
              <button type="button" className="btn" disabled={busy} onClick={trustAllAgreements}>
                Trust all {agreementTargets.length} machine agreement{agreementTargets.length === 1 ? "" : "s"}
              </button>
            )}
          </div>
        </div>
      </div>

      {selectedPage && (
      <aside className="v2panel">
          <div className="v2panel-nav">
            <span>Page {flat.findIndex((p) => p.page_id === selectedId) + 1} of {flat.length}</span>
            <button type="button" className="btn v2panel-close" onClick={() => setSelectedId(null)}>Back to pages</button>
          </div>
          {(
          <>
            <div className="v2panel-img">
              <a
                href={`/api/opspage/${selectedPage.onestop_doc_id}/${selectedPage.pdf_page_index}`}
                target="_blank"
                rel="noopener noreferrer"
                className="v2img-open"
                title="Open the full-resolution page in a new tab (pinch to zoom)"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/api/opspage/${selectedPage.onestop_doc_id}/${selectedPage.pdf_page_index}?w=1100`} alt="selected page" />
                <span className="v2img-openbtn">&#x26F6; Open full image</span>
              </a>
            </div>
            <div className="v2panel-body">
              <div className="eyebrow" style={{ marginBottom: 6 }}>Machine comparison</div>
              {selectedPage.claude_label && selectedPage.codex_label ? (
                (() => {
                  const claude = selectedPage.claude_label;
                  const codex = selectedPage.codex_label;
                  const catAgree = claude.category === codex.category;
                  const flagLabel = (k: string) => FLAGS.find((x) => x.key === k)?.label ?? k;
                  const vendorRow = (name: "Claude" | "Codex", self: typeof claude, peer: typeof claude) => (
                    <div className={`v2vendor v2vendor-${name.toLowerCase()}`}>
                      <div className="v2vendor-head">
                        <strong className="v2vendor-name">{name}</strong>
                        <span className={catAgree ? "" : "v2disagree"}>{self.category}</span>
                        <small>{Math.round((self.confidence ?? 0) * 100)}%{name === "Codex" ? ` · ${self.reasoning_effort ?? "configured"}` : ""}</small>
                      </div>
                      <div className="v2vendor-flags">
                        {self.flags.length === 0 ? (
                          <span className="v2flagchip v2flagchip-none">no flags</span>
                        ) : (
                          self.flags.map((k) => {
                            const shared = peer.flags.includes(k);
                            return (
                              <span
                                key={k}
                                className={`v2flagchip${shared ? "" : " v2flagchip-diff"}`}
                                title={shared ? undefined : `only ${name} flagged this`}
                              >
                                {flagLabel(k)}
                              </span>
                            );
                          })
                        )}
                      </div>
                    </div>
                  );
                  return (
                    <div className="v2compare">
                      {vendorRow("Claude", claude, codex)}
                      {vendorRow("Codex", codex, claude)}
                      <div className="v2micro">{selectedPage.machine_state === "audit" ? "machine match · selected for your audit" : selectedPage.machine_state === "match" ? "exact machine match · not human truth" : "machine disagreement · your review required"}</div>
                    </div>
                  );
                })()
              ) : (
                <div className="v2empty-machine">No pilot label run yet. Legacy suggestions are quarantined and hidden.</div>
              )}

              <div className="eyebrow" style={{ marginBottom: 6 }}>Category (choose one)</div>
              <div className="v2panel-catgrid">
                {TAXONOMY_V2.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    className="btn"
                    style={draftCategory === cat ? { background: "var(--accent)", color: "#fff", borderColor: "var(--accent)" } : undefined}
                    onClick={() => setDraftCategory(cat)}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              <div className="eyebrow" style={{ margin: "14px 0 6px" }}>Flags (select all that apply)</div>
              <div className="v2panel-flags">
                {FLAGS.map((f) => {
                  const on = selectedState?.flags.includes(f.key);
                  return (
                    <label key={f.key} className="v2flag">
                      <span className={`v2toggle${on ? " v2toggle-on" : ""}`} onClick={() => toggleFlag(f.key)} />
                      <span>{f.label}</span>
                    </label>
                  );
                })}
              </div>

              <div className="v2keepline">
                <span aria-hidden>&#128274;</span>
                {KEEP_POLICY.has(draftCategory)
                  ? `KEEP — used for takeoff (${draftCategory})`
                  : "not in keep policy (site plan, detail, etc. are never used for takeoff)"}
              </div>

              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <button type="button" className="btn primary" disabled={!draftCategory || busy} onClick={confirmCategory}>
                  {busy ? "Confirming…" : "Confirm (Enter)"}
                </button>
                <button type="button" className="btn" disabled={busy} onClick={trustCurrent} title="Defer to the machine here (not saved as truth) and move on">
                  {selectedState?.trusted ? "Trusted ✓" : "Trust machine (T)"}
                </button>
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                <button type="button" className="btn" onClick={goNextDisagreement}>Next disagreement (D) &rarr;</button>
                <button type="button" className="btn" onClick={goNextUnreviewed}>Next unreviewed (F) &rarr;</button>
              </div>
              {err && <div style={{ color: "var(--bad)", fontSize: 12, marginTop: 6 }}>{err}</div>}
              <div className="v2micro">Confirm = your truth. Trust = deferred to the machine, not truth — revisit anytime.</div>
            </div>
          </>
          )}
      </aside>
      )}
    </div>
  );
}
