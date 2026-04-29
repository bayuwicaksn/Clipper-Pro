import { useEffect, useRef, useState } from "react";

export type SSEEvent<T = unknown> = {
  step?: string;
  message?: string;
  progress?: number;
  data?: T;
};

export function useSSE<T = unknown>(url?: string) {
  const [event, setEvent] = useState<SSEEvent<T> | null>(null);
  const [error, setError] = useState<Event | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!url) return;

    const source = new EventSource(url);
    sourceRef.current = source;

    source.onmessage = (message) => {
      try {
        setEvent(JSON.parse(message.data));
      } catch {
        setEvent({ message: message.data });
      }
    };
    source.onerror = (err) => setError(err);

    return () => {
      source.close();
      sourceRef.current = null;
    };
  }, [url]);

  return { event, error, close: () => sourceRef.current?.close() };
}
