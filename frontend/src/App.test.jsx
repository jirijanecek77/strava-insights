import { render, screen } from "@testing-library/react";

import App from "./App";


describe("App", () => {
  it("renders the foundation message", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /new foundation stack is running/i }),
    ).toBeInTheDocument();
  });
});
