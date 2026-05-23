"use client";

import { useEffect, useRef, useState } from "react";

export type FeedEvent = {
  id: string;
  event: "agent_start" | "agent_complete" | "phase_complete" | "anomaly_detected" | "report_ready";
  data: Record<string, unknown>;
};

const eventNames: FeedEvent["event"][] = [
  "agent_start",
  "agent_complete",
  "phase_complete",
  "anomaly_detected",
  "report_ready",
];

function eventTitle(event: FeedEvent) {
  const agent = typeof event.data.agent === "string" ? event.data.agent : "";
  const phase = typeof event.data.phase === "string" ? event.data.phase : "";
  if (agent) return agent.replaceAll("_", " ");
  if (phase) return `${phase} phase`;
  return event.event.replaceAll("_", " ");
}

function eventBody(event: FeedEvent) {
  const data = event.data;
  const value = data.message ?? data.output ?? data.summary ?? data.recommendation ?? data.download_url;
  if (typeof value === "string") return value.length > 120 ? `${value.slice(0, 120)}...` : value;
  return JSON.stringify(data);
}

export default function AgentFeed({
  projectId,
  onEvent,
}: {
  projectId: string;
  onEvent?: (event: FeedEvent) => void;
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

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [events]);

  return (
    <div className="feed">
      {events.length === 0 && <p className="muted">No agent events yet.</p>}
      {events.map((event) => (
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
