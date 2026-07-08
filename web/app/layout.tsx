import type { Metadata } from "next";
import { Public_Sans, IBM_Plex_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const sans = Public_Sans({
  subsets: ["latin"],
  variable: "--font-public",
  display: "swap",
});
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Plan Sets — NOLA commercial permits",
  description:
    "Browse New Orleans commercial building permits and their downloaded plan-set PDFs.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <nav className="nav">
          <div className="container nav-in">
            <Link href="/" className="brand">
              <span className="dot" />
              PLAN&nbsp;SETS
            </Link>
            <Link href="/permits" className="link">
              Permits
            </Link>
            <span className="spacer" />
            <span className="link mono" style={{ fontSize: 12 }}>
              NOLA · commercial
            </span>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
