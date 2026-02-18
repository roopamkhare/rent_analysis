import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RE ROI Analyzer — McKinney TX 75071",
  description: "Investment property analysis with S&P 500 comparison",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          crossOrigin=""
        />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
