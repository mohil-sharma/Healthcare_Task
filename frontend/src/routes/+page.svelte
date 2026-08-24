<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchHealth, type HealthResponse } from '$lib/api';

  let health: HealthResponse | null = null;
  let error: string | null = null;
  let loading = true;

  onMount(async () => {
    try {
      health = await fetchHealth();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>Healthcare Appointment Platform</title>
</svelte:head>

<main>
  <h1>🏥 Healthcare Appointment Platform</h1>
  <p class="subtitle">Full-stack skeleton — ready for feature development</p>

  <section class="card">
    <h2>API Health Check</h2>

    {#if loading}
      <p class="status loading">Checking API…</p>
    {:else if error}
      <p class="status error">❌ {error}</p>
    {:else if health}
      <p class="status ok">✅ API is reachable</p>
      <table>
        <tbody>
          <tr><td>Status</td><td><code>{health.status}</code></td></tr>
          <tr><td>Database</td><td><code>{health.db}</code></td></tr>
          <tr><td>Latency</td><td><code>{health.latency_ms} ms</code></td></tr>
        </tbody>
      </table>
    {/if}
  </section>

  <section class="card links">
    <h2>Quick Links</h2>
    <ul>
      <li><a href="/api/docs" target="_blank">Swagger UI (FastAPI)</a></li>
      <li><a href="/api/redoc" target="_blank">ReDoc</a></li>
    </ul>
  </section>
</main>

<style>
  :global(*, *::before, *::after) { box-sizing: border-box; margin: 0; padding: 0; }
  :global(body) {
    font-family: system-ui, sans-serif;
    background: #f0f4f8;
    color: #1a202c;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  main {
    max-width: 560px;
    width: 100%;
    padding: 2rem;
  }

  h1 { font-size: 1.75rem; margin-bottom: 0.25rem; }
  .subtitle { color: #718096; margin-bottom: 2rem; }

  .card {
    background: #fff;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,.08);
    margin-bottom: 1.25rem;
  }

  h2 { font-size: 1.1rem; margin-bottom: 1rem; color: #2d3748; }

  .status { font-weight: 600; margin-bottom: 0.75rem; }
  .status.loading { color: #718096; }
  .status.ok      { color: #38a169; }
  .status.error   { color: #e53e3e; }

  table { width: 100%; border-collapse: collapse; }
  td { padding: 0.4rem 0.5rem; border-bottom: 1px solid #e2e8f0; font-size: 0.9rem; }
  td:first-child { color: #718096; width: 40%; }
  code { background: #edf2f7; padding: 0.1rem 0.4rem; border-radius: 4px; }

  ul { list-style: none; }
  li + li { margin-top: 0.5rem; }
  a { color: #3182ce; text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
