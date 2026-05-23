import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const hasFrame = typeof body.frame === "string" && body.frame.length > 0;

  // Placeholder: replace with Gemini multimodal frame verification.
  return NextResponse.json({
    valid: hasFrame,
    issues: hasFrame
      ? []
      : [{ description: "No frame received", severity: "error", fix: "Enable camera or use manual override." }],
    message: hasFrame ? "Placeholder setup verification passed." : "No webcam frame available.",
  });
}
