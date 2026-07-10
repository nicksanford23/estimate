import Link from "next/link";
import { buildPermitRows, type PermitRow } from "@/lib/opsData";
import { q } from "@/lib/db";

export const dynamic = "force-dynamic";

const fmt = (n: number) => n.toLocaleString("en-US");

type SP = Promise<{ [k: string]: string | string[] | undefined }>;
function one(v: string | string[] | undefined): string {
  return Array.isArray(v) ? v[0] ?? "" : v ?? "";
}

const PAGE_SIZE = 40;

async function discoveredStageRows(qstr: string, page: number) {
  const where = qstr ? `WHERE permit_num ILIKE $1` : "";
  const args = qstr ? [`%${qstr}%`] : [];
  const [{ total }] = await q<{ total: number }>(
    `SELECT COUNT(DISTINCT permit_num)::int total FROM estimate.discovered_docs ${where}`,
    args
  );
  const rows = await q<{ permit_num: string; n_docs: number; first_seen: string }>(
    `SELECT permit_num, COUNT(*)::int n_docs, MIN(discovered_at)::text first_seen
     FROM estimate.discovered_docs ${where}
     GROUP BY permit_num ORDER BY permit_num
     LIMIT ${PAGE_SIZE} OFFSET ${(page - 1) * PAGE_SIZE}`,
    args
  );
  return { total, rows };
}

export default async function OpsPermitsPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const stage = one(sp.stage);
  const tier = one(sp.tier);
  const verdict = one(sp.verdict);
  const search = one(sp.q).trim();
  const sort = one(sp.sort) || "permit";
  const dir = one(sp.dir) === "desc" ? "desc" : "asc";
  const page = Math.max(1, parseInt(one(sp.page) || "1", 10) || 1);

  const qs = (patch: Record<string, string>) => {
    const p = new URLSearchParams();
    if (stage) p.set("stage", stage);
    if (tier) p.set("tier", tier);
    if (verdict) p.set("verdict", verdict);
    if (search) p.set("q", search);
    if (sort) p.set("sort", sort);
    if (dir === "desc") p.set("dir", "desc");
    for (const [k, v] of Object.entries(patch)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    const s = p.toString();
    return s ? `?${s}` : "";
  };

  const stageLabel: Record<string, string> = {
    discovered: "Discovered — document lists fetched from the city portal",
    downloaded: "Downloaded — at least one plan-set PDF in hand",
    harvested: "Harvested — plans carry named wall layers",
    gate_passed: "Gate-passed — wall geometry closes into rooms",
    confirmed: "Eyeball-confirmed — a human confirmed a real floor plan",
    tiered: "Roster tiers — sorted into a training/answer-key tier",
  };

  // ---- Neon-backed "discovered" stage: too large to enrich in-memory ----
  if (stage === "discovered") {
    const { total, rows } = await discoveredStageRows(search, page);
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    return (
      <main>
        <StageHeader stage={stage} label={stageLabel[stage]} total={total} search={search} />
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead>
              <tr>
                <th>Building</th>
                <th>Documents in list</th>
                <th>First discovered</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.permit_num} className="rowlink">
                  <td>
                    <Link href={`/ops/permits/${encodeURIComponent(r.permit_num)}`}>{r.permit_num}</Link>
                  </td>
                  <td className="mono-num">{fmt(r.n_docs)}</td>
                  <td className="mono-num">{r.first_seen?.slice(0, 19).replace("T", " ") ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pager page={page} pages={pages} qs={qs} />
      </main>
    );
  }

  // ---- everything else: in-memory joined universe ----
  let rows = [...buildPermitRows().values()];
  if (stage === "downloaded") {
    // download log is per-batch; the harvested/gate-passed/confirmed sets
    // are supersets of what's downloaded, so approximate "downloaded" as
    // any permit present in the pipeline universe with a harvest attempt.
    rows = rows.filter((r) => r.inHarvested || r.tier || r.verdict);
  } else if (stage === "harvested") {
    rows = rows.filter((r) => r.inHarvested);
  } else if (stage === "gate_passed") {
    rows = rows.filter((r) => r.inGatePassed);
  } else if (stage === "confirmed") {
    rows = rows.filter((r) => r.verdict === "CONFIRMED");
  } else if (stage === "tiered") {
    rows = rows.filter((r) => r.tier);
  }
  if (tier) rows = rows.filter((r) => (r.tier ?? "").includes(tier));
  if (verdict) rows = rows.filter((r) => r.verdict === verdict);
  if (search) rows = rows.filter((r) => r.permit.toLowerCase().includes(search.toLowerCase()));

  const dirMul = dir === "desc" ? -1 : 1;
  const key = (r: PermitRow): string | number => {
    switch (sort) {
      case "tier":
        return r.tier ?? "";
      case "verdict":
        return r.verdict ?? "";
      case "cluster":
        return r.cluster ?? "";
      case "updated":
        return r.updated ?? "";
      default:
        return r.permit;
    }
  };
  rows.sort((a, b) => {
    const ka = key(a),
      kb = key(b);
    if (ka < kb) return -1 * dirMul;
    if (ka > kb) return 1 * dirMul;
    return a.permit.localeCompare(b.permit);
  });

  const total = rows.length;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const th = (col: string, label: string) => (
    <th>
      <Link href={qs({ sort: col, dir: sort === col && dir === "asc" ? "desc" : "asc", page: "" })} className={sort === col ? "sorted" : ""}>
        {label}
        {sort === col ? (dir === "asc" ? " ▲" : " ▼") : ""}
      </Link>
    </th>
  );

  return (
    <main>
      <StageHeader stage={stage} label={stage ? stageLabel[stage] : undefined} total={total} search={search} />

      <div className="filters" style={{ marginTop: 0 }}>
        <div className="seg">
          {["", "CONFIRMED", "FALSE_PASS", "UNCLEAR"].map((v) => (
            <Link key={v || "all"} className={v === verdict ? "on" : ""} href={qs({ verdict: v, page: "" })}>
              {v || "All verdicts"}
            </Link>
          ))}
        </div>
      </div>

      <div className="ops-table-wrap">
        <table className="ops-table">
          <thead>
            <tr>
              {th("permit", "Building")}
              {th("tier", "Tier")}
              {th("verdict", "Verdict")}
              {th("cluster", "Firm cluster")}
              <th>Metrics</th>
              {th("updated", "Updated")}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((r) => (
              <tr key={r.permit} className="rowlink">
                <td>
                  <Link href={`/ops/permits/${encodeURIComponent(r.permit)}`}>{r.permit}</Link>
                </td>
                <td className="wrap">{r.tier ?? <span className="dash">—</span>}</td>
                <td>
                  {r.verdict ? <span className={`status-pill ${r.verdict}`}>{r.verdict}</span> : <span className="dash">—</span>}
                </td>
                <td>
                  {r.cluster ? (
                    <span className="chip" title={r.architect ?? ""}>
                      {r.cluster}
                    </span>
                  ) : (
                    <span className="dash">—</span>
                  )}
                </td>
                <td className="mono-num wrap">{r.metrics}</td>
                <td className="mono-num">{r.updated ? r.updated.slice(0, 19).replace("T", " ") : <span className="dash">—</span>}</td>
              </tr>
            ))}
            {pageRows.length === 0 && (
              <tr>
                <td colSpan={6} className="empty">
                  No buildings match.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <Pager page={page} pages={pages} qs={qs} />
    </main>
  );
}

function StageHeader({
  stage,
  label,
  total,
  search,
}: {
  stage: string;
  label?: string;
  total: number;
  search: string;
}) {
  return (
    <>
      <div className="page-head" style={{ padding: "8px 0" }}>
        <div className="eyebrow">{fmt(total)} buildings</div>
        <h1 style={{ fontSize: 20 }}>{label ?? "All buildings"}</h1>
        {stage && (
          <p>
            <Link href="/ops/permits" className="back" style={{ margin: 0 }}>
              ← clear stage filter
            </Link>
          </p>
        )}
      </div>
      <form className="filters" action="/ops/permits" method="get">
        {stage && <input type="hidden" name="stage" value={stage} />}
        <input type="search" name="q" defaultValue={search} placeholder="Search permit number…" />
      </form>
    </>
  );
}

function Pager({ page, pages, qs }: { page: number; pages: number; qs: (p: Record<string, string>) => string }) {
  if (pages <= 1) return null;
  return (
    <div className="pager">
      <Link className={page <= 1 ? "disabled" : ""} href={qs({ page: String(page - 1) })}>
        ← prev
      </Link>
      <span className="cur">
        {page} / {pages}
      </span>
      <Link className={page >= pages ? "disabled" : ""} href={qs({ page: String(page + 1) })}>
        next →
      </Link>
    </div>
  );
}
