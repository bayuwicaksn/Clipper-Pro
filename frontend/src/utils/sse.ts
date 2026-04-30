/**
 * Type-safe wrapper for EventSource (Server-Sent Events).
 * Handles automatic cleanup, error handling, and JSON parsing.
 */

interface SSEOptions<T> {
  onProgress?: (data: T) => void;
  onDone?: (data: T) => void;
  onError?: (error: any) => void;
  onMessage?: (data: any) => void;
}

export function createSSEConnection<T = any>(
  url: string,
  options: SSEOptions<T>
): () => void {
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      
      if (options.onMessage) {
        options.onMessage(data);
      }

      if (data.step === 'done' || data.status === 'completed') {
        if (options.onDone) options.onDone(data);
        eventSource.close();
      } else if (data.step === 'error' || data.error) {
        if (options.onError) options.onError(data.error || 'Server error');
        eventSource.close();
      } else {
        if (options.onProgress) options.onProgress(data);
      }
    } catch (err) {
      console.error('[SSE] Failed to parse message', err);
      if (options.onError) options.onError('Invalid server response');
    }
  };

  eventSource.onerror = (err) => {
    console.error('[SSE] Connection error', err);
    if (options.onError) options.onError('Connection lost');
    eventSource.close();
  };

  // Return cleanup function
  return () => {
    if (eventSource.readyState !== 2) { // 2 = CLOSED
      eventSource.close();
    }
  };
}
