import Link from "next/link";
import { notFound } from "next/navigation";
import LabProofGallery from "@/components/LabProofGallery";
import { loadTeachingRoom } from "@/lib/teachingRooms";

export const dynamic = "force-dynamic";

function fileUrl(permit: string, kind: string, name: string): string {
  return `/api/lab/file?permit=${encodeURIComponent(permit)}&kind=${encodeURIComponent(kind)}&name=${encodeURIComponent(name)}`;
}

function meaningLabel(value: string): string {
  return value.replaceAll("_", " ");
}

export default async function TeachingRoomPage({
  params,
}: {
  params: Promise<{ permit: string; room: string }>;
}) {
  const { permit, room } = await params;
  const teaching = loadTeachingRoom(permit, room);
  if (!teaching) return notFound();

  return (
    <main className="container teaching-room">
      <header className="teaching-head">
        <div>
          <span className="eyebrow">Start here · teaching room</span>
          <h1>Room {teaching.room.code}: {teaching.room.name}</h1>
          <p>{teaching.address} · sheet {teaching.room.sheet}</p>
        </div>
        <Link className="btn" href={`/lab/${permit}`}>Back to project</Link>
      </header>

      <section className="teaching-alert">
        <strong>This room is not approved.</strong>
        <p>{teaching.status_explanation}</p>
        <p>No decision is being requested from you on this page. Its job is to make the unfinished work understandable.</p>
      </section>

      <section className="teaching-section">
        <span className="teaching-step">1</span>
        <div className="teaching-section-body">
          <h2>What are we trying to measure?</h2>
          <p>{teaching.plain_goal}</p>
          <div className="teaching-definition">
            <strong>The colored rectangle is not a wall.</strong>
            <span>It is the machine&apos;s first guess for the border of the garage flooring area.</span>
          </div>
          {room === "107" && (
            <figure className="teaching-generated-visual">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/teaching/room-107-flooring-boundary-v1.png"
                alt="Beginner explanation of the Room 107 flooring area, wall face, doorway opening, and separate areas"
              />
              <figcaption>
                Beginner teaching visual generated from the original plan. It explains the concepts; it does not declare an approved boundary.
              </figcaption>
            </figure>
          )}
        </div>
      </section>

      <section className="teaching-section">
        <span className="teaching-step">2</span>
        <div className="teaching-section-body">
          <h2>Original plan versus the machine&apos;s draft</h2>
          <p>Start with the untouched architect drawing. Then compare it with the draft. Click either image for full-screen inspection.</p>
          <div className="teaching-image-grid">
            <figure>
              <figcaption><strong>Original plan</strong><span>No AI outline. This is the evidence.</span></figcaption>
              <LabProofGallery
                primary={[{ src: fileUrl(permit, "crop", teaching.room.code), label: `Original plan crop for room ${room}` }]}
              />
            </figure>
            <figure>
              <figcaption><strong>First machine draft</strong><span>The bright outline is a proposal, not truth.</span></figcaption>
              <LabProofGallery
                primary={[{ src: fileUrl(permit, "overlay", teaching.room.code), label: `First machine draft for room ${room}` }]}
              />
            </figure>
          </div>
        </div>
      </section>

      <section className="teaching-section">
        <span className="teaching-step">3</span>
        <div className="teaching-section-body">
          <h2>What must be explained for every side?</h2>
          <p>
            A side is only ready when the system explains what physical event makes the flooring stop or continue there.
            A nearby black PDF line is not enough.
          </p>
          <div className="teaching-side-grid">
            {teaching.boundary_sides.map((side) => (
              <article key={side.id} className="teaching-side-card">
                <header>
                  <span>{side.id}</span>
                  <div><strong>{side.human_name}</strong><small>Draft meaning: {meaningLabel(side.draft_meaning)}</small></div>
                </header>
                <div className="teaching-side-status">Not approved</div>
                <p><strong>What the draft claims:</strong> {side.draft_claim}</p>
                <p><strong>What the number says:</strong> The current machine candidate is {side.measurement_in.toFixed(1)} real-building inches from the draft.</p>
                <p><strong>Why that is not enough:</strong> {side.why_not_confirmed}</p>
                <p><strong>Current conclusion:</strong> {side.current_conclusion}</p>
                <div className="teaching-next-action"><strong>Next action</strong><span>{side.next_action}</span></div>
                <details>
                  <summary>Optional measurement math</summary>
                  <p>{side.measurement_math}</p>
                </details>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="teaching-section">
        <span className="teaching-step">4</span>
        <div className="teaching-section-body">
          <h2>Why we are resetting instead of trusting the colors</h2>
          <p>Different machine passes reached different conclusions about the same unchanged garage.</p>
          <div className="teaching-history">
            {teaching.machine_history.map((item, index) => (
              <div key={item.stage}>
                <span>{index + 1}</span>
                <p><strong>{item.stage}</strong>{item.result}</p>
              </div>
            ))}
          </div>
          <div className="teaching-definition danger">
            <strong>Machine disagreement is a blocker.</strong>
            <span>We do not average these opinions or promote the most confident one to truth.</span>
          </div>
        </div>
      </section>

      <section className="teaching-section">
        <span className="teaching-step">5</span>
        <div className="teaching-section-body">
          <h2>What happens next?</h2>
          <ol className="teaching-next-list">
            {teaching.required_next_steps.map((step) => <li key={step}>{step}</li>)}
          </ol>
          <p className="teaching-training-status">
            <strong>Training eligibility:</strong> No. Room 107 stays excluded until corrected geometry and qualified review exist.
          </p>
        </div>
      </section>

      <details className="teaching-technical">
        <summary>Optional technical evidence from the failed workflow</summary>
        <p>This is retained for engineering diagnosis. It is not the founder/customer decision screen.</p>
        <LabProofGallery
          primary={[{ src: fileUrl(permit, "proof", teaching.source_images.measurement_diagnostic), label: `Legacy measurement diagnostic for room ${room}` }]}
          details={teaching.boundary_sides.map((side) => ({
            src: fileUrl(permit, "proof", `proof_${room}_${side.id}.png`),
            label: `${side.human_name} technical evidence`,
          }))}
        />
      </details>
    </main>
  );
}
