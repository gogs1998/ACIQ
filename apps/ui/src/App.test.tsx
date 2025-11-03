import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    );
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
