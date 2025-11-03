import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  beforeEach(() => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ok: true }) })
      .mockResolvedValue({ ok: true, json: async () => ({ items: [] }) });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders health status", async () => {
    render(<App />);

    const element = await screen.findByTestId("health-status");
    await waitFor(() => expect(element.textContent).toContain("Engine is responding"));
  });
});
