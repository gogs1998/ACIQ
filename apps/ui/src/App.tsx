import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";

type HealthStatus = "idle" | "checking" | "ok" | "error";

interface HealthResponse {
  ok: boolean;
}

interface BankTxn {
  id: string;
  date: string;
  amount: number;
  direction: "debit" | "credit";
  description_raw: string;
  description_clean: string;
  account_id: string;
}

interface Suggestion {
  txn_id: string;
  nominal_suggested: string | null;
  tax_code_suggested: string | null;
  confidence: number;
  explanations: string[];
}

interface ReviewItem {
  txn: BankTxn;
  suggestion: Suggestion;
  status: "pending" | "approved" | "overridden";
  nominal_final: string | null;
  tax_code_final: string | null;
  notes: string[];
  created_at: string;
  updated_at: string;
}

interface ReviewImportResponse {
  items: ReviewItem[];
}

interface ExportResponse {
  exported_path: string;
  row_count: number;
}

const HEALTH_ENDPOINT = "http://127.0.0.1:8000/health";
const REVIEW_BASE = (clientSlug: string) => `http://127.0.0.1:8000/review/${clientSlug}`;
const REVIEW_IMPORT_ENDPOINT = "http://127.0.0.1:8000/review/import";

const statusCopy: Record<HealthStatus, string> = {
  idle: "Click check to test the connection",
  checking: "Checking...",
  ok: "Engine is responding",
  error: "Engine unavailable"
};

const formatConfidence = (confidence: number): string => `${Math.round(confidence * 100)}%`;
const formatCurrency = (value: number): string => value.toLocaleString("en-GB", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
});

const readFileAsText = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read file"));
    reader.readAsText(file);
  });

export default function App() {
  const [status, setStatus] = useState<HealthStatus>("idle");
  const [lastCheckedAt, setLastCheckedAt] = useState<string>("");
  const [clientSlug, setClientSlug] = useState<string>("sample_client");
  const [bankCsv, setBankCsv] = useState<string>("");
  const [historyCsv, setHistoryCsv] = useState<string>("");
  const [bankFileName, setBankFileName] = useState<string>("");
  const [historyFileName, setHistoryFileName] = useState<string>("");
  const [queueItems, setQueueItems] = useState<ReviewItem[]>([]);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [ruleMessage, setRuleMessage] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    setStatus("checking");
    try {
      const response = await fetch(HEALTH_ENDPOINT);
      if (!response.ok) {
        throw new Error(`Unexpected status ${response.status}`);
      }
      const payload = (await response.json()) as HealthResponse;
      setStatus(payload.ok ? "ok" : "error");
    } catch (error_) {
      console.error("Health check failed", error_);
      setStatus("error");
    } finally {
      setLastCheckedAt(new Date().toLocaleTimeString());
    }
  }, []);

  const fetchQueue = useCallback(
    async (slug: string = clientSlug) => {
      try {
        const response = await fetch(`${REVIEW_BASE(slug)}/queue`);
        if (!response.ok) {
          throw new Error(`Failed to fetch queue (${response.status})`);
        }
        const payload = (await response.json()) as ReviewImportResponse;
        setQueueItems(payload.items);
      } catch (error_) {
        console.error("Unable to load review queue", error_);
        setError("Unable to load review queue");
      }
    },
    [clientSlug]
  );

  useEffect(() => {
    void checkHealth();
    void fetchQueue();
  }, [checkHealth, fetchQueue]);

  const handleFileChange = useCallback(
    async (event: ChangeEvent<HTMLInputElement>, kind: "bank" | "history") => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      try {
        const contents = await readFileAsText(file);
        if (kind === "bank") {
          setBankCsv(contents);
          setBankFileName(file.name);
        } else {
          setHistoryCsv(contents);
          setHistoryFileName(file.name);
        }
        setError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
      }
    },
    []
  );

  const runSuggestions = useCallback(
    async (options?: { reset?: boolean }) => {
      if (!bankCsv || !historyCsv) {
        setError("Please provide both bank and history CSV files.");
        return;
      }

      setIsSubmitting(true);
      setError(null);
      setExportMessage(null);
      setRuleMessage(null);
      try {
        const response = await fetch(REVIEW_IMPORT_ENDPOINT, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            client_slug: clientSlug,
            bank_csv: bankCsv,
            history_csv: historyCsv,
            reset: options?.reset ?? true
          })
        });

        if (!response.ok) {
          throw new Error(`Suggestion request failed (${response.status})`);
        }

        const payload = (await response.json()) as ReviewImportResponse;
        setQueueItems(payload.items);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
      } finally {
        setIsSubmitting(false);
      }
    },
    [bankCsv, clientSlug, historyCsv]
  );

  const approveItem = useCallback(
    async (item: ReviewItem) => {
      try {
        const response = await fetch(`${REVIEW_BASE(clientSlug)}/items/${item.txn.id}/approve`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({})
        });
        if (!response.ok) {
          throw new Error(`Approve failed (${response.status})`);
        }
        const updated = (await response.json()) as ReviewItem;
        setQueueItems((previous) =>
          previous.map((entry) => (entry.txn.id === updated.txn.id ? updated : entry))
        );
      } catch (error_) {
        const message = error_ instanceof Error ? error_.message : String(error_);
        setError(message);
      }
    },
    [clientSlug]
  );

  const overrideItem = useCallback(
    async (item: ReviewItem) => {
      const defaultNominal = item.nominal_final ?? item.suggestion.nominal_suggested ?? "";
      const defaultTax = item.tax_code_final ?? item.suggestion.tax_code_suggested ?? "";
      const nominal = window.prompt("Nominal code", defaultNominal);
      if (nominal === null) {
        return;
      }
      const taxCode = window.prompt("Tax code", defaultTax);
      if (taxCode === null) {
        return;
      }

      try {
        const response = await fetch(`${REVIEW_BASE(clientSlug)}/items/${item.txn.id}/override`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            nominal_code: nominal,
            tax_code: taxCode,
            note: "Set via UI override"
          })
        });
        if (!response.ok) {
          throw new Error(`Override failed (${response.status})`);
        }
        const updated = (await response.json()) as ReviewItem;
        setQueueItems((previous) =>
          previous.map((entry) => (entry.txn.id === updated.txn.id ? updated : entry))
        );
      } catch (error_) {
        const message = error_ instanceof Error ? error_.message : String(error_);
        setError(message);
      }
    },
    [clientSlug]
  );

  const createRuleFromItem = useCallback(
    async (item: ReviewItem) => {
      const pattern = window.prompt(
        "Rule pattern (regex)",
        item.txn.description_clean || item.txn.description_raw
      );
      if (!pattern) {
        return;
      }
      const nominal = window.prompt(
        "Nominal code",
        item.nominal_final ?? item.suggestion.nominal_suggested ?? ""
      );
      if (!nominal) {
        return;
      }
      const taxCode = window.prompt(
        "Tax code",
        item.tax_code_final ?? item.suggestion.tax_code_suggested ?? ""
      );
      if (!taxCode) {
        return;
      }

      try {
        const response = await fetch(`${REVIEW_BASE(clientSlug)}/rules`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            name: item.suggestion.txn_id.slice(0, 8),
            pattern,
            nominal,
            tax_code: taxCode
          })
        });
        if (!response.ok) {
          throw new Error(`Rule creation failed (${response.status})`);
        }
        setRuleMessage(`Rule added and applied for pattern: ${pattern}`);
        await runSuggestions({ reset: true });
      } catch (error_) {
        const message = error_ instanceof Error ? error_.message : String(error_);
        setError(message);
      }
    },
    [clientSlug, runSuggestions]
  );

  const handleExport = useCallback(async () => {
    try {
      const response = await fetch(`${REVIEW_BASE(clientSlug)}/export`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ profile_name: "default" })
      });
      if (!response.ok) {
        throw new Error(`Export failed (${response.status})`);
      }
      const payload = (await response.json()) as ExportResponse;
      setExportMessage(`Exported ${payload.row_count} rows to ${payload.exported_path}`);
    } catch (error_) {
      const message = error_ instanceof Error ? error_.message : String(error_);
      setError(message);
    }
  }, [clientSlug]);

  const suggestionRows = useMemo(() => queueItems, [queueItems]);
  const bankPreview = useMemo(() => bankCsv.split(/\r?\n/).slice(0, 6).join("\n"), [bankCsv]);
  const historyPreview = useMemo(
    () => historyCsv.split(/\r?\n/).slice(0, 6).join("\n"),
    [historyCsv]
  );

  const statusClassName = `status ${
    status === "ok" ? "ok" : status === "error" ? "error" : ""
  }`;

  return (
    <main>
      <div className="hero">
        <div>
          <h1>AccountantIQ Desktop Shell</h1>
          <p>
            Load a bank CSV and a Sage history export, then let the local engine build a review queue.
            Approve suggestions, override codes, and capture rules without leaving your desktop.
          </p>
        </div>
        <div className={statusClassName} data-testid="health-status">
          <strong>Status:</strong> {statusCopy[status]}
        </div>
      </div>

      <section className="inputs">
        <div className="input-group">
          <label htmlFor="client-slug">Client slug</label>
          <input
            id="client-slug"
            value={clientSlug}
            onChange={(event) => setClientSlug(event.target.value.trim())}
            placeholder="sample_client"
          />
        </div>
        <div className="file-picker">
          <label htmlFor="bank-upload">Bank transactions CSV</label>
          <input
            id="bank-upload"
            type="file"
            accept=".csv"
            onChange={(event) => void handleFileChange(event, "bank")}
          />
          {bankFileName && <span className="file-name">Loaded: {bankFileName}</span>}
          {bankPreview && (
            <textarea value={bankPreview} readOnly aria-label="Bank CSV preview" />
          )}
        </div>

        <div className="file-picker">
          <label htmlFor="history-upload">Sage export CSV</label>
          <input
            id="history-upload"
            type="file"
            accept=".csv"
            onChange={(event) => void handleFileChange(event, "history")}
          />
          {historyFileName && <span className="file-name">Loaded: {historyFileName}</span>}
          {historyPreview && (
            <textarea value={historyPreview} readOnly aria-label="History CSV preview" />
          )}
        </div>
      </section>

      <section className="run">
        <button
          onClick={() => void runSuggestions()}
          disabled={isSubmitting || !bankCsv || !historyCsv}
        >
          {isSubmitting ? "Running..." : "Run suggestions"}
        </button>
        <button onClick={() => void fetchQueue()} disabled={isSubmitting}>
          Refresh queue
        </button>
        <button onClick={() => void handleExport()} disabled={suggestionRows.length === 0}>
          Export approved items
        </button>
        <button onClick={() => void checkHealth()} disabled={status === "checking"}>
          Re-check engine health
        </button>
        {lastCheckedAt && (
          <p className="timestamp">Last health check: {lastCheckedAt}</p>
        )}
        {error && <p className="error">{error}</p>}
        {exportMessage && <p className="info">{exportMessage}</p>}
        {ruleMessage && <p className="info">{ruleMessage}</p>}
      </section>

      {suggestionRows.length > 0 && (
        <section className="results">
          <div className="results-header">
            <h2>Review queue</h2>
            <span className="queue-summary">
              Pending: {suggestionRows.filter((item) => item.status === "pending").length} ·
              Approved: {suggestionRows.filter((item) => item.status === "approved").length} ·
              Overridden: {suggestionRows.filter((item) => item.status === "overridden").length}
            </span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th>Amount</th>
                <th>Suggestion</th>
                <th>Final</th>
                <th>Confidence</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {suggestionRows.map((item) => (
                <tr key={item.txn.id}>
                  <td>{new Date(item.txn.date).toLocaleDateString()}</td>
                  <td>
                    <div className="description">
                      <span>{item.txn.description_raw}</span>
                      <small>{item.txn.account_id}</small>
                    </div>
                  </td>
                  <td className="mono">{formatCurrency(item.txn.amount)}</td>
                  <td>
                    <div className="code-block">
                      <span>{item.suggestion.nominal_suggested ?? "—"}</span>
                      <small>{item.suggestion.tax_code_suggested ?? "—"}</small>
                      <ul>
                        {item.suggestion.explanations.map((reason, index) => (
                          <li key={index}>{reason}</li>
                        ))}
                      </ul>
                    </div>
                  </td>
                  <td>
                    <div className="code-block">
                      <span>{item.nominal_final ?? "—"}</span>
                      <small>{item.tax_code_final ?? "—"}</small>
                      {item.notes.length > 0 && (
                        <ul>
                          {item.notes.map((note, index) => (
                            <li key={index}>{note}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </td>
                  <td>
                    <span className="confidence">{formatConfidence(item.suggestion.confidence)}</span>
                  </td>
                  <td>
                    <span className={`status-pill ${item.status}`}>{item.status}</span>
                  </td>
                  <td>
                    <div className="action-buttons">
                      <button
                        onClick={() => void approveItem(item)}
                        disabled={item.status !== "pending"}
                      >
                        Approve
                      </button>
                      <button onClick={() => void overrideItem(item)}>Override</button>
                      <button onClick={() => void createRuleFromItem(item)}>Create rule</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
