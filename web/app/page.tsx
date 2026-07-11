import { redirect } from "next/navigation";

// Old Model-1 stats homepage — superseded by Mission Control (/ops). Kept
// in place (not deleted) but the site root now redirects there. The old
// content is still reachable at /permits (nav-renamed to "Legacy").
export default function Home() {
  redirect("/ops");
}
