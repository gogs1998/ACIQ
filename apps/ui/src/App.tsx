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

interface CsvSuggestionResponse {
  transactions: BankTxn[];
  suggestions: Suggestion[];
}

const HEALTH_ENDPOINT = "http://127.0.0.1:8000/health";
const CSV_SUGGEST_ENDPOINT = "http://127.0.0.1:8000/suggest/from-csv";

const statusCopy: Record<HealthStatus, string> = {
  idle: "Click check to test the connection",
  checking: "Checking...",
  ok: "Engine is responding",
  error: "Engine unavailable"
};

const readFileAsText = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read file"));
    reader.readAsText(file);
  });

const formatConfidence = (confidence: number): string => `${Math.round(confidence * 100)}%`;

export default function App() {
  const [status, setStatus] = useState<HealthStatus>("idle");
  const [lastCheckedAt, setLastCheckedAt] = useState<string>("");
  const [bankCsv, setBankCsv] = useState<string>("");
  const [historyCsv, setHistoryCsv] = useState<string>("");
  const [bankFileName, setBankFileName] = useState<string>("");
  const [historyFileName, setHistoryFileName] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CsvSuggestionResponse | null>(null);

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

  useEffect(() => {
    void checkHealth();
  }, [checkHealth]);

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

  const runSuggestions = useCallback(async () => {
    if (!bankCsv || !historyCsv) {
      setError("Please provide both bank and history CSV files.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const response = await fetch(CSV_SUGGEST_ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          bank_csv: bankCsv,
          history_csv: historyCsv
        })
      });

      if (!response.ok) {
        throw new Error(`Suggestion request failed (${response.status})`);
      }

      const payload = (await response.json()) as CsvSuggestionResponse;
      setResult(payload);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }, [bankCsv, historyCsv]);

  const suggestionRows = useMemo(() => {
    if (!result) {
      return [];
    }
    const transactionMap = new Map(result.transactions.map((txn) => [txn.id, txn]));
    return result.suggestions
      .map((suggestion) => ({
        suggestion,
        txn: transactionMap.get(suggestion.txn_id)
      }))
      .filter((row): row is { suggestion: Suggestion; txn: BankTxn } => Boolean(row.txn));
  }, [result]);

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
            Load a bank CSV and a Sage history export, then let the local engine propose nominal
            and tax codes. Everything stays on your machine.
          </p>
        </div>
        <div className={statusClassName} data-testid="health-status">
          <strong>Status:</strong> {statusCopy[status]}
        </div>
      </div>

      <section className="actions">
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
        <button onClick={() => void checkHealth()} disabled={status === "checking"}>
          Re-check engine health
        </button>
        {lastCheckedAt && (
          <p className="timestamp">Last health check: {lastCheckedAt}</p>
        )}
        {error && <p className="error">{error}</p>}
      </section>

      {suggestionRows.length > 0 && (
        <section className="results">
          <h2>Suggested codes</h2>
          <table>
            <thead>
              <tr>
                <th style={{ width: "20%" }}>Date</th>
                <th style={{ width: "30%" }}>Description</th>
                <th>Direction</th>
                <th>Amount</th>
                <th>Nominal</th>
                <th>Tax code</th>
                <th>Confidence</th>
                <th>Why</th>
              </tr>
            </thead>
            <tbody>
              {suggestionRows.map(({ suggestion, txn }) => (
                <tr key={suggestion.txn_id}>
                  <td>{new Date(txn.date).toLocaleDateString()}</td>
                  <td>
                    <div className="description">
                      <span>{txn.description_raw}</span>
                      <small>{txn.account_id}</small>
                    </div>
                  </td>
                  <td className="mono">{txn.direction}</td>
                  <td className="mono">{txn.amount.toFixed(2)}</td>
                  <td className="mono">{suggestion.nominal_suggested ?? "—"}</td>
                  <td className="mono">{suggestion.tax_code_suggested ?? "—"}</td>
                  <td>
                    <span className="confidence">{formatConfidence(suggestion.confidence)}</span>
                  </td>
                  <td>
                    <ul>
                      {suggestion.explanations.map((reason, index) => (
                        <li key={index}>{reason}</li>
                      ))}
                    </ul>
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
