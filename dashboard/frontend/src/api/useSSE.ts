import { useEffect, useRef, useState, useCallback } from 'react';

export interface SSELogLine {
  text: string;
  id: number;
}

export interface SSEState {
  logs: SSELogLine[];
  status: 'idle' | 'running' | 'completed' | 'failed' | 'stopped';
  phase: string | null;
  startedAt: string | null;
  progress: number;
  connected: boolean;
}

export function useSSE() {
  const [state, setState] = useState<SSEState>({
    logs: [],
    status: 'idle',
    phase: null,
    startedAt: null,
    progress: 0,
    connected: false,
  });
  const eventSourceRef = useRef<EventSource | null>(null);
  const counterRef = useRef(0);

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource('/api/run/stream');
    eventSourceRef.current = es;

    es.onopen = () => {
      setState(prev => ({ ...prev, connected: true }));
    };

    es.addEventListener('clear', () => {
      counterRef.current = 0;
      setState(prev => ({ ...prev, logs: [], progress: 0 }));
    });

    es.addEventListener('log', (e: MessageEvent) => {
      const text = e.data;
      setState(prev => ({
        ...prev,
        logs: [...prev.logs.slice(-199), { text, id: counterRef.current++ }],
      }));
    });

    es.addEventListener('status', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setState(prev => ({
        ...prev,
        status: data.status,
        phase: data.phase ?? prev.phase,
        startedAt: data.started_at ?? prev.startedAt,
      }));
    });

    es.addEventListener('progress', (e: MessageEvent) => {
      const pct = parseInt(e.data, 10);
      setState(prev => ({ ...prev, progress: isNaN(pct) ? 0 : pct }));
    });

    es.onerror = () => {
      setState(prev => ({ ...prev, connected: false }));
      es.close();
      eventSourceRef.current = null;
    };
  }, []);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setState({
      logs: [],
      status: 'idle',
      phase: null,
      startedAt: null,
      progress: 0,
      connected: false,
    });
  }, []);

  const clearLogs = useCallback(() => {
    setState(prev => ({ ...prev, logs: [], progress: 0 }));
  }, []);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return { state, connect, disconnect, clearLogs };
}
