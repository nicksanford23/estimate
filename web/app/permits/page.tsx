import Link from "next/link";
import { listPermits, CODE_LABEL } from "@/lib/queries";

export const dynamic = "force-dynamic";

const fmt = (n: number) => n.toLocaleString("en-US");

type SP = Promise<{ [k: string]: string | string[] | undefined }>;

function one(v: string | string[] | undefined): string {
  return Array.isArray(v) ? v[0] ?? "" : v ?? "";
}

export default async function PermitsPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const code = one(sp.code);
  const search = one(sp.q);
  const labeled = one(sp.labeled) === "1";
  const page = Math.max(1, parseInt(one(sp.page) || "1", 10) || 1);

  const { rows, total, pages } = await listPermits({
    code: code || undefined,
    search: search || undefined,
    onlyLabeled: labeled,
    page,
  });

  const codes = ["", "NEWC", "RNVS", "RNVN"];
  const qs = (patch: Record<string, string>) => {
    const p = new URLSearchParams();
    if (code) p.set("code", code);
    if (search) p.set("q", search);
    if (labeled) p.set("labeled", "1");
    for (const [k, v] of Object.entries(patch)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    const s = p.toString();
    return s ? `?${s}` : "";
  };

  return (
    <main className="container">
      <div className="page-head">
        <div className="eyebrow">{fmt(total)} permits</div>
        <h1>Permits</h1>
      </div>

      <form className="filters" action="/permits" method="get">
        {code && <input type="hidden" name="code" value={code} />}
        {labeled && <input type="hidden" name="labeled" value="1" />}
        <input
          type="search"
          name="q"
          defaultValue={search}
          placeholder="Search permit number, address, description, contractor…"
        />
        <div className="seg">
          {codes.map((c) => (
            <Link
              key={c || "all"}
              className={c === code ? "on" : ""}
              href={`/permits${qs({ code: c, page: "" })}`}
            >
              {c || "All"}
            </Link>
          ))}
        </div>
        <Link
          className={`ftog ${labeled ? "on" : ""}`}
          href={`/permits${qs({ labeled: labeled ? "" : "1", page: "" })}`}
        >
          <span className="bx">{labeled ? "☑" : "☐"}</span> Labeled only
        </Link>
      </form>

      {rows.length === 0 ? (
        <div className="empty">No permits match.</div>
      ) : (
        <div className="permit-grid">
          {rows.map((r) => (
            <Link
              key={r.permit_num}
              className="permit-card"
              href={`/permits/${encodeURIComponent(r.permit_num)}`}
            >
              <div className="top">
                <span className="pnum">{r.permit_num}</span>
                {r.code && (
                  <span className="chip code" title={CODE_LABEL[r.code] ?? r.code}>
                    {r.code}
                  </span>
                )}
              </div>
              <div className="desc">{r.description || "—"}</div>
              {r.address && <div className="addr">{r.address}</div>}
              <div className="foot">
                <span className="chip">{fmt(r.doc_count ?? 0)} docs</span>
                {r.downloaded > 0 ? (
                  <span className="badge downloaded">
                    {fmt(r.downloaded)} downloaded
                  </span>
                ) : (
                  <span className="badge none">none downloaded</span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}

      {pages > 1 && (
        <div className="pager">
          <Link
            className={page <= 1 ? "disabled" : ""}
            href={`/permits${qs({ page: String(page - 1) })}`}
          >
            ← prev
          </Link>
          <span className="cur">
            {page} / {pages}
          </span>
          <Link
            className={page >= pages ? "disabled" : ""}
            href={`/permits${qs({ page: String(page + 1) })}`}
          >
            next →
          </Link>
        </div>
      )}
    </main>
  );
}
