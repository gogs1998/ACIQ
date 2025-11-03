import { useCallback, useEffect, useState } from "react";

type HealthStatus = "idle" | "checking" | "ok" | "error";

interface HealthResponse {
  ok: boolean;
}

const HEALTH_ENDPOINT = "http://127.0.0.1:8000/health";

const statusCopy: Record<HealthStatus, string> = {
  idle: "Click check to test the connection",
  checking: "Checking...",
  ok: "Engine is responding",
  error: "Engine unavailable"
};

export default function App() {
  const [status, setStatus] = useState<HealthStatus>("idle");
  const [lastCheckedAt, setLastCheckedAt] = useState<string>("");

  const checkHealth = useCallback(async () => {
    setStatus("checking");
    try {
      const response = await fetch(HEALTH_ENDPOINT);
      if (!response.ok) {
        throw new Error(`Unexpected status ${response.status}`);
      }
      const payload = (await response.json()) as HealthResponse;
      if (payload.ok) {
        setStatus("ok");
      } else {
        setStatus("error");
      }
    } catch (error) {
      console.error("Health check failed", error);
      setStatus("error");
    } finally {
      setLastCheckedAt(new Date().toLocaleTimeString());
    }
  }, []);

  useEffect(() => {
    void checkHealth();
  }, [checkHealth]);

  const statusClassName = `status ${status === "ok" ? "ok" : status === "error" ? "error" : ""}`;

  return (
    <main>
      <h1>AccountantIQ Desktop Shell</h1>
      <p>
        The desktop client communicates with the local FastAPI engine. Start the engine
        with <code>poetry run uvicorn accountantiq_engine.main:app --reload</code> and use
        the button below to verify the connection.
      </p>
      <div className={statusClassName} data-testid="health-status">
        <strong>Status:</strong> {statusCopy[status]}
      </div>
      <div style={{ marginTop: "24px" }}>
        <button onClick={() => void checkHealth()} disabled={status === "checking"}>
          Check health
        </button>
      </div>
      {lastCheckedAt && (
        <p style={{ marginTop: "24px", color: "#475569" }}>Last checked: {lastCheckedAt}</p>
      )}
    </main>
  );
}
