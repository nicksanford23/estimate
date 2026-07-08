import Link from "next/link";
import { getFunnel, getCodeBreakdown } from "@/lib/queries";

export const dynamic = "force-dynamic";

const fmt = (n: number) => n.toLocaleString("en-US");

export default async function Home() {
  const [f, codes] = await Promise.all([getFunnel(), getCodeBreakdown()]);
  const stages = [
    { n: f.permitsTotal, l: "permits scraped", tint: "var(--scraped)" },
    { n: f.permitsWithDocs, l: "with document lists", tint: "var(--scraped)" },
    { n: f.downloaded, l: "PDFs downloaded", tint: "var(--downloaded)" },
    { n: f.renderedDocs, l: "docs rendered", tint: "var(--rendered)" },
    { n: f.labeledDocs, l: "docs labeled", tint: "var(--labeled)" },
  ];
  return (
    <main className="container">
      <div className="page-head">
        <div className="eyebrow">New Orleans · commercial building permits</div>
        <h1>Plan-set pipeline</h1>
        <p>
          Every permit, its documents, and which plan-set PDFs we&rsquo;ve pulled
          — browse and open the real files.
        </p>
      </div>

      <div className="funnel">
        {stages.map((s, i) => (
          <div
            className="stage"
            key={i}
            style={{ ["--tint" as string]: s.tint } as React.CSSProperties}
          >
            <div className="n">{fmt(s.n)}</div>
            <div className="l">{s.l}</div>
            <div className="bar" />
          </div>
        ))}
      </div>

      <div className="section-title">Downloaded by code type</div>
      <div className="code-grid">
        {codes.map((c) => (
          <Link key={c.code} className="code-card" href={`/permits?code=${c.code}`}>
            <div className="code">{c.code}</div>
            <div className="lbl">{c.label}</div>
            <div className="big">{fmt(c.downloadedDocs)}</div>
            <div className="sub">
              PDFs · {fmt(c.downloadedPermits)} permits w/ files · {fmt(c.permits)}{" "}
              total
            </div>
          </Link>
        ))}
      </div>

      <div style={{ margin: "28px 0 50px" }}>
        <Link className="btn primary" href="/permits">
          Browse all permits →
        </Link>
      </div>
    </main>
  );
}
