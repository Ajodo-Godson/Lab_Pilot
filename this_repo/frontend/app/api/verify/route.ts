import { NextRequest, NextResponse } from "next/server";

const verificationPrompt = `You are verifying an RF probe positioning setup.
Objects in frame:
- Phone = the device under test (DUT)
- Pen = the RF probe

Requirements:
1. Phone is lying flat, screen visible
2. Pen tip is within 3cm of the phone surface
3. Pen is approximately perpendicular to phone face (90 degrees +/- 5 degrees)
4. No large metallic objects directly touching the phone

Respond ONLY in this JSON, no markdown or code blocks:
{
  "valid": true or false,
  "issues": [{"description": "text", "severity": "warning or error", "fix": "exact instruction"}],
  "message": "one-line summary"
}`;

function parseJsonObject(text: string) {
  const cleaned = text.replace(/```json|```/g, "").trim();
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start === -1 || end === -1) throw new Error("No JSON object");
  return JSON.parse(cleaned.slice(start, end + 1));
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
      valid: true,
      issues: [],
      message: "Demo verification passed. Set GEMINI_API_KEY for live frame analysis.",
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
    return NextResponse.json(parseJsonObject(text));
  } catch {
    return NextResponse.json({
      valid: false,
      issues: [],
      message: "Parse error",
    });
  }
}
