import { redirect } from "next/navigation";

// Site root lands on the V2 product surface (founder request 2026-07-17).
// Mission Control remains at /ops; legacy stats at /permits.
export default function Home() {
  redirect("/v2");
}
