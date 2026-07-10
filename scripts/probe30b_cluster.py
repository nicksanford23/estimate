#!/usr/bin/env python3
"""Probe 30b -- firm clustering of the 79 roster permits.

Evidence sources:
  (a) wall-layer naming signature (roster wall_sig, normalized)
  (b) title-block architect name (data/probe30b/architects.csv, hand/regex
      extracted from pagetext_cache -- optional until built)
  (c) near-duplicate geometry (closeability_full.csv best-page metrics)

Union-find merge -> data/probe30b/clusters.csv + printed histogram.
"""
import csv, os, json, re, itertools, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROSTER = os.path.join(ROOT, "data", "probe30", "roster.csv")
CLOSE = os.path.join(ROOT, "data", "triage", "closeability_full.csv")
ARCH = os.path.join(ROOT, "data", "probe30b", "architects.csv")
OUT = os.path.join(ROOT, "data", "probe30b", "clusters.csv")


def norm_sig(sig):
    """Normalize a wall_sig so trivially-equivalent firm dialects merge:
    uppercase, strip floor-number prefixes (1-A-WALL == 2-A-WALL), sort."""
    toks = []
    for t in sig.split("|"):
        t = t.strip().upper()
        t = re.sub(r"^\d+(-\d+)?-", "", t)   # floor prefixes 1-, 2-5-
        t = re.sub(r"\s+", " ", t)
        toks.append(t)
    return "|".join(sorted(set(toks)))


def load_roster():
    return list(csv.DictReader(open(ROSTER)))


def load_geometry(rows):
    """Best-page metrics per permit from closeability_full.csv.
    Prefer the exact roster (doc,page) row; else the max-cov_mid row."""
    by_permit = collections.defaultdict(list)
    for r in csv.DictReader(open(CLOSE)):
        by_permit[r["permit"]].append(r)
    geo = {}
    for r in rows:
        cands = by_permit.get(r["permit"], [])
        exact = [c for c in cands if c["doc_id"] == r["doc_id"] and c["page"] == r["page"]]
        pool = exact or cands
        if not pool:
            geo[r["permit"]] = None
            continue
        best = max(pool, key=lambda c: float(c["cov_mid"] or 0))
        geo[r["permit"]] = dict(
            doc_id=best["doc_id"], page=best["page"],
            n_mid=int(float(best["n_mid"] or 0)),
            cov_mid=float(best["cov_mid"] or 0),
            largest_frac=float(best["largest_frac"] or 0),
            n_wall_segs=int(float(best["n_wall_segs"] or 0)),
            exact=bool(exact))
    return geo


def geo_near(a, b):
    if not a or not b:
        return False
    if a["n_mid"] == 0 or b["n_mid"] == 0:
        return False
    def rel(x, y):
        return abs(x - y) / max(abs(x), abs(y), 1e-9)
    return (rel(a["n_mid"], b["n_mid"]) < 0.02
            and rel(a["cov_mid"], b["cov_mid"]) < 0.02
            and rel(a["largest_frac"], b["largest_frac"]) < 0.05
            and rel(a["n_wall_segs"], b["n_wall_segs"]) < 0.02)


class UF:
    def __init__(self, keys):
        self.p = {k: k for k in keys}
    def find(self, k):
        while self.p[k] != k:
            self.p[k] = self.p[self.p[k]]
            k = self.p[k]
        return k
    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


GENERIC_SIGS = {"A-WALL", "WALL|WALLS", "A-WALL|WALLS", "(NONE-MATCHED)",
                # demoted after architect adjudication: A-WALL|A-WALL-PATT
                # merged SPEC_DESIGNS with JOHN_C_WILLIAMS (proven different
                # firms) -- 2-token AIA-standard sigs are not firm evidence
                "A-WALL|A-WALL-PATT", "A-WALL|I-WALL"}


def main():
    rows = load_roster()
    permits = [r["permit"] for r in rows]
    geo = load_geometry(rows)
    arch = {}
    if os.path.exists(ARCH):
        for r in csv.DictReader(open(ARCH)):
            if r.get("architect") and r["architect"] not in ("", "UNKNOWN"):
                arch[r["permit"]] = r["architect"].strip().upper()

    uf = UF(permits)
    evidence = collections.defaultdict(list)

    # (a) identical normalized wall signature -- skip hyper-generic sigs
    # (A-WALL alone is the AIA default, not firm evidence)
    by_sig = collections.defaultdict(list)
    for r in rows:
        s = norm_sig(r["wall_sig"])
        if s not in GENERIC_SIGS:
            by_sig[s].append(r["permit"])
    for s, ps in by_sig.items():
        for a, b in zip(ps, ps[1:]):
            # block sig merges contradicted by known-different architects
            if a in arch and b in arch and arch[a] != arch[b]:
                continue
            uf.union(a, b)
            evidence[(a, b)].append(f"sig:{s}")

    # (b) same architect
    by_arch = collections.defaultdict(list)
    for p, a in arch.items():
        by_arch[a].append(p)
    for a, ps in by_arch.items():
        for x, y in zip(ps, ps[1:]):
            uf.union(x, y)
            evidence[(x, y)].append(f"arch:{a}")

    # (c) near-duplicate geometry
    geo_pairs = []
    for a, b in itertools.combinations(permits, 2):
        if geo_near(geo.get(a), geo.get(b)):
            uf.union(a, b)
            geo_pairs.append((a, b))
            evidence[(a, b)].append("geo")

    clusters = collections.defaultdict(list)
    for p in permits:
        clusters[uf.find(p)].append(p)
    # stable cluster ids ordered by size desc
    ordered = sorted(clusters.values(), key=lambda c: (-len(c), c[0]))
    row_by_p = {r["permit"]: r for r in rows}
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cluster_id", "permit", "split", "wall_sig_norm", "architect",
                    "n_mid", "cov_mid", "largest_frac"])
        for i, c in enumerate(ordered):
            for p in sorted(c):
                g = geo.get(p) or {}
                w.writerow([f"C{i:02d}", p, row_by_p[p]["split"],
                            norm_sig(row_by_p[p]["wall_sig"]), arch.get(p, ""),
                            g.get("n_mid", ""), g.get("cov_mid", ""), g.get("largest_frac", "")])

    sizes = sorted((len(c) for c in ordered), reverse=True)
    print(f"permits: {len(permits)}  clusters: {len(ordered)}")
    print("size histogram:", collections.Counter(sizes))
    print("\nclusters of size>=2:")
    for i, c in enumerate(ordered):
        if len(c) >= 2:
            print(f"  C{i:02d} (n={len(c)}): {sorted(c)}")
            print(f"        sig={norm_sig(row_by_p[c[0]]['wall_sig'])}")
    print("\ngeo near-dup pairs:", len(geo_pairs))
    for a, b in geo_pairs:
        print(f"  {a} ~ {b}  {geo[a]} | {geo[b]}")
    print(f"\narchitects loaded: {len(arch)}")


if __name__ == "__main__":
    main()
