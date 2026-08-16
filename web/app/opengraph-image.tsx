import { ImageResponse } from "next/og";

// Social preview card (1200×630) shown when the site is shared in Slack,
// iMessage, Twitter/X, LinkedIn, etc. Flat, brand-consistent: near-black
// canvas, one blue accent, the validation mark — no gradient, no stock art.
export const runtime = "edge";
export const alt = "SimAPI — CI checks for engineering simulations";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#08090d",
          padding: "72px 80px",
          fontFamily: "sans-serif",
        }}
      >
        {/* Mark + wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 14,
              border: "2px solid rgba(255,255,255,0.14)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none">
              <path d="M6 12.4l3.6 3.7L18.5 8" stroke="#2563eb" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div style={{ fontSize: 34, fontWeight: 600, color: "#ffffff", letterSpacing: -0.5 }}>SimAPI</div>
        </div>

        {/* Headline */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ fontSize: 68, fontWeight: 700, color: "#ffffff", lineHeight: 1.05, letterSpacing: -1.5, maxWidth: 960 }}>
            Your solver won&apos;t tell you the run is wrong.
          </div>
          <div style={{ fontSize: 30, color: "rgba(255,255,255,0.55)", lineHeight: 1.3, maxWidth: 900 }}>
            Validate CFD, FEA, and robotics simulation output against physical law — before it reaches a decision or an ML pipeline.
          </div>
        </div>

        {/* Footer strip */}
        <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              border: "1px solid rgba(255,255,255,0.14)",
              background: "rgba(255,255,255,0.03)",
              borderRadius: 8,
              padding: "12px 18px",
              fontSize: 24,
              color: "#ffffff",
              fontFamily: "monospace",
            }}
          >
            npm install -g simapi-cli
          </div>
          <div style={{ fontSize: 22, color: "rgba(255,255,255,0.4)" }}>21 domains · deterministic · MIT</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
