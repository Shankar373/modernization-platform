export default function History() {
  return (
    <div>
      <h1 style={{ marginBottom: 16 }}>Migration History</h1>
      <p className="text-muted" style={{ marginBottom: 32 }}>All past migrations will appear here.</p>
      <div className="card" style={{ textAlign: 'center', padding: 48 }}>
        <p style={{ fontSize: 40, marginBottom: 16 }}>📋</p>
        <p className="text-muted">No migrations yet. <a href="/new">Start your first migration →</a></p>
      </div>
    </div>
  );
}
