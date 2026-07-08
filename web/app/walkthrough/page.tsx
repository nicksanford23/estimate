"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

const STAGES = [
  {
    img: "/walkthrough/A.jpg",
    n: "1 / 4",
    title: "The raw plan",
    body: "The architectural floor plan straight out of the PDF — bedrooms, baths, stairs, guest suites, with walls and dimensions. This is the input. Everything after is the software trying to understand it.",
  },
  {
    img: "/walkthrough/B.jpg",
    n: "2 / 4",
    title: "Every line in the file",
    body: "We ask the PDF for all of its vector lines — about 20,000 of them (drawn in blue): walls, furniture, text, dimension ticks, door swings… all mixed together. To a computer it's just a pile of line segments. Its first job is to figure out which of these ~20,000 lines are actually walls. That's the hard part — it's chaos.",
  },
  {
    img: "/walkthrough/C.jpg",
    n: "3 / 4",
    title: "The walls it found",
    body: "After filtering by thickness and alignment and stripping out hatching, it keeps only wall-like lines (green). Look how cleanly it traced the real walls — every bedroom, bath, stair and suite is legible. This step works. 'Seeing' the walls is basically solved.",
  },
  {
    img: "/walkthrough/D.jpg",
    n: "4 / 4",
    title: "Closing walls into rooms — where it breaks",
    body: "Now it tries to turn those walls into closed, measured rooms (green = a room it thinks it found, numbers = square feet). Instead of clean rooms it makes a green mess — rooms merge together, the courtyard fills in, even door-swing symbols become 'rooms.' Why? One missing or extra line breaks a whole room. This step is the unsolved problem — and exactly where machine learning comes in.",
  },
];

export default function Walkthrough() {
  const [open, setOpen] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);
  const stageRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; l: number; t: number } | null>(null);

  const openImg = (i: number) => {
    setZoom(1);
    setOpen(i);
    document.body.style.overflow = "hidden";
  };
  const close = () => {
    setOpen(null);
    document.body.style.overflow = "";
  };
  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    setZoom((z) => Math.min(8, Math.max(1, z * (e.deltaY < 0 ? 1.15 : 1 / 1.15))));
  };
  const onDown = (e: React.PointerEvent) => {
    const s = stageRef.current;
    if (!s) return;
    drag.current = { x: e.clientX, y: e.clientY, l: s.scrollLeft, t: s.scrollTop };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onMove = (e: React.PointerEvent) => {
    const s = stageRef.current;
    if (!s || !drag.current) return;
    s.scrollLeft = drag.current.l - (e.clientX - drag.current.x);
    s.scrollTop = drag.current.t - (e.clientY - drag.current.y);
  };
  const onUp = () => {
    drag.current = null;
  };

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  return (
    <main className="container wt">
      <Link href="/" className="back">
        ← home
      </Link>

      <div className="page-head">
        <div className="eyebrow">SF Walkthrough #1 · Henriette Delille Hotel · 2nd-floor plan</div>
        <h1>From a floor plan to square footage</h1>
        <p>
          How the software turns a real architectural drawing into measured rooms —
          and where it breaks. <b>Click any image to zoom in sharply.</b>
        </p>
      </div>

      <div className="wt-stages">
        {STAGES.map((s, i) => (
          <section className="wt-stage" key={i}>
            <div className="wt-meta">
              <span className="wt-n">{s.n}</span>
              <h2>{s.title}</h2>
              <p>{s.body}</p>
            </div>
            <button className="wt-imgbtn" onClick={() => openImg(i)} aria-label={`Zoom ${s.title}`}>
              <img src={s.img} alt={s.title} loading="lazy" />
              <span className="wt-zoomhint">🔍 click to zoom</span>
            </button>
          </section>
        ))}
      </div>

      <div className="wt-lesson">
        <div className="eyebrow">The lesson</div>
        <p>
          The software is great at <b>seeing</b> walls (step 3) and bad at{" "}
          <b>reasoning</b> them into correct rooms (step 4). Only ~11% of plans come
          out clean; ~61% blob like step 4. That step is our real bottleneck — and the
          question for a data scientist: a wall-vs-line classifier? image segmentation?
          something else?
        </p>
      </div>

      {open !== null && (
        <div className="wt-lb">
          <div className="wt-lb-bar">
            <span className="wt-lb-cap">
              {STAGES[open].n} · {STAGES[open].title}
            </span>
            <div className="wt-lb-tools">
              <button onClick={() => setZoom((z) => Math.max(1, z / 1.4))}>−</button>
              <button onClick={() => setZoom(1)}>fit</button>
              <button onClick={() => setZoom((z) => Math.min(8, z * 1.4))}>+</button>
              <button onClick={close}>✕ close</button>
            </div>
          </div>
          <div
            className="wt-lb-stage"
            ref={stageRef}
            onWheel={onWheel}
            onPointerDown={onDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            style={{ cursor: zoom > 1 ? "grab" : "zoom-in" }}
          >
            <img
              src={STAGES[open].img}
              alt={STAGES[open].title}
              draggable={false}
              style={{ width: `${zoom * 100}%`, maxWidth: "none", display: "block", margin: "0 auto" }}
            />
          </div>
          <div className="wt-lb-hint">scroll or ± to zoom · drag to pan · ✕ or Esc to close</div>
        </div>
      )}
    </main>
  );
}
