import { NextRequest, NextResponse } from "next/server";

type VisionIssue = {
  description: string;
  severity: "warning" | "error";
  fix: string;
};

type VisionResult = {
  valid: boolean;
  issues: VisionIssue[];
  message: string;
  setup_estimate?: SetupEstimate;
};

export type SetupEstimate = {
  probe_distance_cm: number;
  probe_angle_deg: number;
  antenna_x: number;
  antenna_y: number;
  setup_quality: "good" | "acceptable" | "poor";
  notes: string;
};

const verificationPrompt = `You are verifying an RF probe positioning setup for a live hackathon demo.
Objects in frame:
- Phone = the device under test (DUT)
- Pen = the RF probe

Pass the setup when the phone and pen/probe are both visible and the probe is near the phone.
Be demo-tolerant: a tilted probe, imperfect perpendicular angle, hand in frame, or approximate distance should be a warning, not a failure.
Only return valid=false when no phone is visible, no probe/pen is visible, the frame is unusable, or a large metallic object is directly touching the phone.
Return at most one issue. Prefer concise coaching.
When valid=true, estimate setup parameters for the synthetic SAR simulator:
- probe_distance_cm: approximate pen/probe tip distance from phone surface
- probe_angle_deg: approximate probe angle relative to phone face where 90 is perpendicular
- antenna_x: estimated left/right probe offset on the phone, from -4 to 4
- antenna_y: simulator antenna distance scalar, from 0.5 to 4.0. Smaller means closer to phone.
- setup_quality: good, acceptable, or poor

Respond ONLY in this JSON, no markdown or code blocks:
{
  "valid": true or false,
  "issues": [{"description": "text", "severity": "warning or error", "fix": "exact instruction"}],
  "message": "one-line summary",
  "setup_estimate": {
    "probe_distance_cm": number,
    "probe_angle_deg": number,
    "antenna_x": number,
    "antenna_y": number,
    "setup_quality": "good" or "acceptable" or "poor",
    "notes": "one short sentence"
  }
}`;

function parseJsonObject(text: string) {
  const cleaned = text.replace(/```json|```/g, "").trim();
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start === -1 || end === -1) throw new Error("No JSON object");
  return JSON.parse(cleaned.slice(start, end + 1));
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function setupEstimateFrom(result: VisionResult): SetupEstimate {
  const estimate: Partial<SetupEstimate> = result.setup_estimate ?? {};
  const probeDistance = Number(estimate.probe_distance_cm);
  const probeAngle = Number(estimate.probe_angle_deg);
  const antennaX = Number(estimate.antenna_x);
  const antennaY = Number(estimate.antenna_y);
  const quality = estimate.setup_quality;

  return {
    probe_distance_cm: Number.isFinite(probeDistance) ? clamp(probeDistance, 0.5, 12) : 3,
    probe_angle_deg: Number.isFinite(probeAngle) ? clamp(probeAngle, 0, 180) : 90,
    antenna_x: Number.isFinite(antennaX) ? clamp(antennaX, -4, 4) : 0,
    antenna_y: Number.isFinite(antennaY) ? clamp(antennaY, 0.5, 4) : 1.5,
    setup_quality: quality === "good" || quality === "acceptable" || quality === "poor" ? quality : "acceptable",
    notes: typeof estimate.notes === "string" ? estimate.notes.slice(0, 100) : "Estimated from accepted setup frame.",
  };
}

function normalizeForDemo(result: VisionResult): VisionResult {
  const issues = Array.isArray(result.issues) ? result.issues : [];
  const isValid = result.valid === true;

  if (!isValid) {
    return {
      valid: false,
      issues,
      message: result.message || "Setup is not usable yet.",
    };
  }

  return {
    valid: true,
    issues,
    message: result.message || "Setup accepted and locked for simulation.",
    setup_estimate: setupEstimateFrom(result),
  };
}

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const frame = typeof body.frame === "string" ? body.frame : "";

  if (!frame) {
    return NextResponse.json({
      valid: false,
      issues: [{ description: "No frame received", severity: "error", fix: "Enable camera or use manual override." }],
      message: "No webcam frame available.",
    });
  }

  const apiKey = process.env.GEMINI_API_KEY ?? process.env.GOOGLE_API_KEY;
  if (!apiKey) {
    return NextResponse.json({
      valid: false,
      issues: [{ description: "Vision model is not configured", severity: "error", fix: "Set GEMINI_API_KEY before locking a setup-driven simulation." }],
      message: "Cannot estimate setup without Gemini vision.",
    });
  }

  const model = process.env.GEMINI_MODEL ?? "gemini-3.5-flash";

  try {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents: [
            {
              role: "user",
              parts: [
                { text: verificationPrompt },
                { inline_data: { mime_type: "image/jpeg", data: frame } },
              ],
            },
          ],
          generationConfig: { temperature: 0.1, response_mime_type: "application/json" },
        }),
      },
    );

    if (!response.ok) throw new Error(`Gemini request failed: ${response.status}`);
    const payload = await response.json();
    const text = payload?.candidates?.[0]?.content?.parts?.map((part: { text?: string }) => part.text ?? "").join("") ?? "";
    return NextResponse.json(normalizeForDemo(parseJsonObject(text) as VisionResult));
  } catch {
    return NextResponse.json({
      valid: false,
      issues: [{ description: "Vision response was unavailable", severity: "error", fix: "Retry with a clear phone and probe frame." }],
      message: "Cannot estimate setup from this frame.",
    });
  }
}
