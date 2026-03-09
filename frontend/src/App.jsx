const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export default function App() {
  return (
    <main className="app-shell">
      <section className="hero-card">
        <p className="eyebrow">Strava Insights</p>
        <h1>New foundation stack is running.</h1>
        <p className="copy">
          Frontend, API, worker, PostgreSQL, and Redis are now scaffolded for
          the rebuild.
        </p>
        <p className="endpoint">
          Backend health endpoint: <code>{apiBaseUrl}/health</code>
        </p>
      </section>
    </main>
  );
}
