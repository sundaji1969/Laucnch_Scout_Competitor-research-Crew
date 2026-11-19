import { ImageResponse } from "next/og";

export const alt = "LaunchScout: competitor research for your next launch, in minutes";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background: "#0f1116",
          color: "#f2efe8",
          fontFamily: "Georgia, serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <svg width="56" height="56" viewBox="0 0 32 32">
            <rect width="32" height="32" rx="8" fill="#f2efe8" />
            <path d="M9 22.5 16 8l7 14.5-7-3.6-7 3.6Z" fill="#0f1116" />
            <circle cx="16" cy="15.2" r="2.1" fill="#eab454" />
          </svg>
          <span style={{ fontSize: 36, fontWeight: 600 }}>LaunchScout</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 76, lineHeight: 1.05, fontWeight: 600, letterSpacing: -2 }}>
            Know your competitors
          </div>
          <div style={{ fontSize: 76, lineHeight: 1.05, fontWeight: 600, letterSpacing: -2, color: "#eab454" }}>
            before you launch.
          </div>
        </div>
        <div style={{ display: "flex", fontSize: 28, color: "#a7aab5", fontFamily: "sans-serif" }}>
          Real competitors · Real prices · Real complaints · Every claim cited
        </div>
      </div>
    ),
    size,
  );
}
