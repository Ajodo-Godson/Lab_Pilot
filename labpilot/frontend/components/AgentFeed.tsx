"use client";

import { useEffect, useRef, useState } from "react";

export type FeedEvent = {
  id: string;
  event: "agent_start" | "agent_complete" | "phase_complete" | "anomaly_detected" | "report_ready" | "device_profile";
  data: Record<string, unknown>;
};

const eventNames: FeedEvent["event"][] = [
  "agent_start",
  "agent_complete",
  "phase_complete",
  "anomaly_detected",
  "report_ready",
  "device_profile",
];

function eventTitle(event: FeedEvent) {
  if (event.event === "device_profile") return "device detected";
  const agent = typeof event.data.agent === "string" ? event.data.agent : "";
  const phase = typeof event.data.phase === "string" ? event.data.phase : "";
  if (agent) return agent.replaceAll("_", " ");
  if (phase) return `${phase} phase`;
  return event.event.replaceAll("_", " ");
}

function eventBody(event: FeedEvent) {
  const data = event.data;
  if (event.event === "device_profile") {
    const name = typeof data.device_name === "string" ? data.device_name : "Unknown";
    const ff = typeof data.form_factor === "string" ? data.form_factor : "unknown";
    const radioCount = Array.isArray(data.radios) ? data.radios.length : 0;
    return `${name} (${ff}) — ${radioCount} radio${radioCount !== 1 ? "s" : ""} detected`;
  }
  const value = data.message ?? data.output ?? data.summary ?? data.recommendation ?? data.download_url;
  if (typeof value === "string") return value.length > 120 ? `${value.slice(0, 120)}...` : value;
  return JSON.stringify(data);
}

export default function AgentFeed({
  projectId,
  onEvent,
  injectedEvents,
}: {
  projectId: string;
  onEvent?: (event: FeedEvent) => void;
  injectedEvents?: FeedEvent[];
}) {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  const isMock = projectId === "demo-project";
  const backend = isMock
    ? (process.env.NEXT_PUBLIC_MOCK_BACKEND_URL ?? "http://localhost:8003")
    : (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000");

  useEffect(() => {
    if (!projectId) return;
    const source = new EventSource(`${backend}/api/projects/${projectId}/events`);

    eventNames.forEach((name) => {
      source.addEventListener(name, (messageEvent) => {
        const event: FeedEvent = {
          id: `${name}-${Date.now()}-${Math.random()}`,
          event: name,
          data: JSON.parse(messageEvent.data),
        };
        setEvents((current) => [...current, event]);
        onEvent?.(event);
      });
    });

    return () => source.close();
  }, [projectId, onEvent, backend]);

  const allEvents = injectedEvents ? [...events, ...injectedEvents].sort((a, b) => {
    const ta = parseInt(a.id.split("-")[1] || "0", 10);
    const tb = parseInt(b.id.split("-")[1] || "0", 10);
    return ta - tb;
  }) : events;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [allEvents]);

  return (
    <div className="feed">
      {allEvents.length === 0 && <p className="muted">No agent events yet.</p>}
      {allEvents.map((event) => (
        <div key={event.id} className={`event ${event.event}`}>
          <div className="eventTop">
            <strong>{eventTitle(event)}</strong>
            <span>{event.event}</span>
          </div>
          <p>{eventBody(event)}</p>
          {event.event === "report_ready" && typeof event.data.download_url === "string" && (
            <a
              className="download"
              href={
                (event.data.download_url.startsWith("http")
                  ? event.data.download_url
                  : `${backend}${event.data.download_url}`) + "?media=pdf"
              }
              target="_blank"
              rel="noopener noreferrer"
            >
              Download report
            </a>
          )}
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
