import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NutriTrack",
  description: "AI 기반 식사 영양 트래커",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
