import { NextRequest, NextResponse } from "next/server";

const IDENTIFY_PROMPT = `
Analyze this image and identify the electronic device.

1. What device is this? (make, model if visible)
2. What wireless technologies does it likely have?
   (WiFi bands, Bluetooth version, 5G/LTE if applicable)
3. How is it being held/positioned?

Respond ONLY in this JSON format, no markdown or code blocks:
{
  "device_name": "device brand and model name",
  "confidence": "high" | "medium" | "low",
  "chips": [
    { "chip": "name of chip or standard", "type": "WiFi" | "BLE" | "BT" | "5G" | "LTE", "freq_mhz": number, "power_dbm": number }
  ],
  "form_factor": "handset" | "tablet" | "wearable" | "laptop" | "iot" | "speaker" | "gateway" | "other",
  "held_to_head": true or false,
  "body_worn": true or false,
  "notes": "one line about the device and its FCC ID if searchable"
}
`;

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
    return NextResponse.json(
      { error: "No frame received" },
      { status: 400 }
    );
  }

  const apiKey = process.env.GEMINI_API_KEY ?? process.env.GOOGLE_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "Vision model is not configured" },
      { status: 500 }
    );
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
                { text: IDENTIFY_PROMPT },
                { inline_data: { mime_type: "image/jpeg", data: frame } },
              ],
            },
          ],
          tools: [
            {
              google_search: {},
            },
          ],
          generationConfig: {
            temperature: 0.2,
            response_mime_type: "application/json",
          },
        }),
      },
    );

    if (!response.ok) {
      throw new Error(`Gemini request failed: ${response.status}`);
    }

    const payload = await response.json();
    const text =
      payload?.candidates?.[0]?.content?.parts
        ?.map((part: { text?: string }) => part.text ?? "")
        .join("") ?? "";

    const result = parseJsonObject(text);
    return NextResponse.json(result);
  } catch (error: any) {
    console.error("Device identification error:", error);
    return NextResponse.json(
      { error: "Failed to identify device" },
      { status: 500 }
    );
  }
}
