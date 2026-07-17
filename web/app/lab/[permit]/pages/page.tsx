// TEMP workbench: kept plan pages as fast pre-rendered images (founder
// request — dense vector PDFs zoom slowly; PNGs pan/zoom instantly).
import Link from "next/link";
import { notFound } from "next/navigation";
import { projectName, SMOKE } from "@/lib/lab";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

export default async function KeptPages({ params }: { params: Promise<{ permit: string }> }) {
  const { permit } = await params;
  if (!/^[A-Za-z0-9-]+$/.test(permit)) return notFound();
  const dir = path.join(SMOKE, permit, "kept_pages");
  if (!fs.existsSync(dir)) return notFound();
  const pages = fs.readdirSync(dir).filter((f) => /^page_[0-9]{2}\.png$/.test(f)).sort();
  return (
    <div className="container">
      <div className="page-head">
        <h1>{projectName(permit)} — kept pages</h1>
        <p><Link href={`/lab/${permit}`}>← project</Link> · {pages.length} pages · click a page to open full size</p>
      </div>
      <div style={{ display: "grid", gap: 18, marginTop: 14 }}>
        {pages.map((f) => {
          const n = f.slice(5, 7);
          const src = `/api/lab/file?permit=${permit}&kind=keptimg&name=${n}`;
          return (
            <a key={f} href={src} target="_blank">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={src} alt={`page ${n}`} loading="lazy"
                   style={{ width: "100%", borderRadius: 8, border: "1px solid var(--line)" }} />
            </a>
          );
        })}
      </div>
    </div>
  );
}
