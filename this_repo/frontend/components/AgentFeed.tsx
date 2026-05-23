"use client";

import { useEffect, useState } from "react";

type FeedEvent = {
  id: string;
  event: string;
  data: Record<string, unknown>;
};

export default function AgentFeed({ projectId }: { projectId: string }) {
  const [events, setEvents] = useState<FeedEvent[]>([]);

  useEffect(() => {
    if (!projectId) return;
    const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
    const source = new EventSource(`${backend}/api/projects/${projectId}/events`);
    const names = ["agent_start", "agent_complete", "phase_complete", "anomaly_detected", "report_ready"];

    names.forEach((name) => {
      source.addEventListener(name, (event) => {
        setEvents((current) => [
          ...current,
          { id: `${name}-${Date.now()}-${Math.random()}`, event: name, data: JSON.parse(event.data) },
        ]);
      });
    });

    return () => source.close();
  }, [projectId]);

  return (
    <div className="feed">
      {events.length === 0 && <p className="muted">No agent events yet.</p>}
      {events.map((event) => (
        <div key={event.id} className={`event ${event.event}`}>
          <strong>{event.event}</strong>
          <pre>{JSON.stringify(event.data, null, 2)}</pre>
        </div>
      ))}
    </div>
  );
}
