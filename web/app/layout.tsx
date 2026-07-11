import type { Metadata } from "next";
import { Public_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import GlobalNav from "@/components/GlobalNav";

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
        <GlobalNav />
        {children}
      </body>
    </html>
  );
}
