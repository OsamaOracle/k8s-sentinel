import React, { useState, useEffect, useCallback, useRef } from "react";

const BASE_URL = "http://localhost:8000";

// ── CSS keyframes injected once ───────────────────────────────────────────────
const GLOBAL_CSS = `
  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0d1117; }
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: #161b22; }
  ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
`;

// ── Helpers ───────────────────────────────────────────────────────────────────

function calcHealthScore(pods, resources) {
  let score = 100;
  for (const pod of pods) {
    const r = pod.reason || "";
    if (r === "CrashLoopBackOff") score -= 15;
    else if (pod.phase !== "Running" && pod.phase !== "Succeeded") score -= 8;
    if (pod.restart_count >= 10) score -= 10;
    else if (pod.restart_count >= 3) score -= 5;
  }
  for (const node of resources.nodes || []) {
    if (!node.ready) score -= 20;
  }
  return Math.max(0, Math.min(100, score));
}

function detectAnomalies(pods, events, resources) {
  const result = [];
  const seen = new Set();

  const addAnomaly = (key, sev, label, detail, namespace) => {
    if (seen.has(key)) return;
    seen.add(key);
    result.push({ sev, label, detail, namespace });
  };

  for (const pod of pods) {
    const k = `${pod.namespace}/${pod.name}`;
    if ((pod.reason || "").includes("CrashLoopBackOff"))
      addAnomaly(`crash/${k}`, "high", "CrashLoopBackOff",
        `Pod ${pod.name} is in CrashLoopBackOff`, pod.namespace);
    if (pod.restart_count >= 3)
      addAnomaly(`restart/${k}`, "high", "HighRestartCount",
        `Pod ${pod.name} has restarted ${pod.restart_count} times`, pod.namespace);
    if ((pod.reason || "").includes("OOMKilled"))
      addAnomaly(`oom/${k}`, "high", "OOMKilled",
        `Pod ${pod.name} was OOMKilled`, pod.namespace);
  }

  for (const node of resources.nodes || []) {
    if (!node.ready)
      addAnomaly(`node/${node.name}`, "high", "NodeNotReady",
        `Node ${node.name} is NotReady`, "");
  }

  const rules = [
    { substr: "FailedMount", sev: "high" },
    { substr: "OOMKilling", sev: "high" },
    { substr: "BackOff",    sev: "med"  },
    { substr: "CPUThrottling", sev: "med" },
  ];
  for (const ev of events) {
    if (ev.type !== "Warning") continue;
    for (const rule of rules) {
      if ((ev.reason || "").includes(rule.substr)) {
        const obj = ev.involved_object?.name || "";
        addAnomaly(`ev/${ev.namespace}/${obj}/${rule.substr}`, rule.sev, rule.substr,
          (ev.message || "").slice(0, 150), ev.namespace);
      }
    }
  }

  return result.sort((a, b) => (a.sev === "high" && b.sev !== "high" ? -1 : 1));
}

function fmtTime(ts) {
  if (!ts) return "—";
  try { return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
  catch { return String(ts); }
}

function scoreColor(s) {
  return s >= 80 ? "#22c55e" : s >= 50 ? "#f59e0b" : "#ef4444";
}
function scoreLabel(s) {
  return s >= 80 ? "Healthy" : s >= 50 ? "Degraded" : "Critical";
}

// ── Styles ────────────────────────────────────────────────────────────────────

const C = {
  // layout
  root:   { background: "#0d1117", minHeight: "100vh", color: "#e6edf3",
            fontFamily: "'Inter', system-ui, -apple-system, sans-serif" },
  header: { background: "#161b22", borderBottom: "1px solid #30363d",
            padding: "14px 28px", display: "flex", alignItems: "center", gap: "14px" },
  logo:   { width: 28, height: 28 },
  title:  { fontSize: "17px", fontWeight: 700, color: "#e6edf3", letterSpacing: "-0.2px" },
  badge:  { fontSize: "11px", background: "#1f6feb", color: "#fff",
            padding: "2px 9px", borderRadius: "12px", fontWeight: 600 },
  liveIndicator: { marginLeft: "auto", display: "flex", alignItems: "center", gap: "6px",
                   fontSize: "12px", color: "#8b949e" },
  liveDot: (live) => ({ width: 8, height: 8, borderRadius: "50%",
                        background: live ? "#22c55e" : "#6e7681",
                        boxShadow: live ? "0 0 6px #22c55e" : "none" }),
  main:   { padding: "24px 28px", maxWidth: "1440px", margin: "0 auto" },
  topGrid: { display: "grid", gridTemplateColumns: "260px 1fr", gap: "18px", marginBottom: "18px" },
  card:   { background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "18px 20px" },
  cardTitle: { fontSize: "11px", fontWeight: 700, color: "#8b949e",
               textTransform: "uppercase", letterSpacing: "0.6px", marginBottom: "14px" },
  // stats row
  statRow: { display: "flex", gap: "12px", flexWrap: "wrap" },
  statCard: { flex: 1, minWidth: 110, background: "#0d1117", border: "1px solid #30363d",
              borderRadius: "8px", padding: "14px 16px" },
  statVal: { fontSize: "28px", fontWeight: 800, lineHeight: 1 },
  statLbl: { fontSize: "12px", color: "#8b949e", marginTop: "4px" },
  // tabs
  tabBar: { display: "flex", gap: 0, borderBottom: "1px solid #30363d", marginBottom: "18px" },
  tab: (active) => ({
    padding: "10px 20px", fontSize: "13px", fontWeight: active ? 600 : 400,
    color: active ? "#58a6ff" : "#8b949e",
    borderBottom: `2px solid ${active ? "#58a6ff" : "transparent"}`,
    cursor: "pointer", background: "none", border: "none",
    borderBottom: `2px solid ${active ? "#58a6ff" : "transparent"}`,
    transition: "color 0.15s",
  }),
  // table
  tbl:  { width: "100%", borderCollapse: "collapse", fontSize: "13px" },
  th:   { padding: "8px 14px", textAlign: "left", color: "#8b949e", fontWeight: 600,
          borderBottom: "1px solid #30363d", fontSize: "11px", textTransform: "uppercase",
          letterSpacing: "0.4px", whiteSpace: "nowrap" },
  td:   { padding: "10px 14px", borderBottom: "1px solid #21262d", verticalAlign: "middle" },
  tdMono: { padding: "10px 14px", borderBottom: "1px solid #21262d", verticalAlign: "middle",
            fontFamily: "monospace", fontSize: "12px" },
  trHover: { transition: "background 0.1s" },
  // pill badges
  pill: (bg, fg) => ({ display: "inline-flex", alignItems: "center", padding: "2px 9px",
                       borderRadius: "12px", fontSize: "11px", fontWeight: 600,
                       background: bg, color: fg, whiteSpace: "nowrap" }),
  // anomaly banner
  anomalyWrap: { marginBottom: "18px", animation: "fadeIn 0.3s ease" },
  anomalyRow: (sev) => ({
    display: "flex", alignItems: "flex-start", gap: "10px",
    padding: "9px 14px", borderRadius: "7px", marginBottom: "6px",
    background: sev === "high" ? "rgba(239,68,68,0.08)" : "rgba(245,158,11,0.08)",
    border: `1px solid ${sev === "high" ? "rgba(239,68,68,0.2)" : "rgba(245,158,11,0.2)"}`,
  }),
  anomalyIcon: (sev) => ({ fontSize: "14px", marginTop: "1px",
                           color: sev === "high" ? "#ef4444" : "#f59e0b" }),
  // error banner
  errBanner: { display: "flex", alignItems: "center", justifyContent: "space-between",
               gap: "12px", background: "rgba(239,68,68,0.08)",
               border: "1px solid rgba(239,68,68,0.25)", borderRadius: "8px",
               padding: "12px 16px", marginBottom: "18px", animation: "fadeIn 0.2s ease" },
  errMsg: { fontSize: "13px", color: "#fca5a5" },
  retryBtn: { padding: "6px 14px", borderRadius: "6px", border: "1px solid rgba(239,68,68,0.4)",
              background: "rgba(239,68,68,0.12)", color: "#fca5a5", cursor: "pointer",
              fontSize: "12px", fontWeight: 600, whiteSpace: "nowrap" },
  // loading
  loadWrap: { display: "flex", flexDirection: "column", alignItems: "center",
              justifyContent: "center", minHeight: "100vh", gap: "18px",
              background: "#0d1117", color: "#8b949e" },
  spinner: { width: 40, height: 40, border: "3px solid #21262d",
             borderTop: "3px solid #58a6ff", borderRadius: "50%",
             animation: "spin 0.9s linear infinite" },
  loadTxt: { fontSize: "14px", color: "#8b949e" },
  // diagnosis
  diagWrap: { display: "flex", flexDirection: "column", gap: "14px" },
  diagInput: { width: "100%", background: "#0d1117", border: "1px solid #30363d",
               borderRadius: "7px", padding: "10px 14px", color: "#e6edf3",
               fontSize: "13px", outline: "none", resize: "vertical",
               fontFamily: "inherit" },
  diagBtn: (disabled) => ({
    padding: "9px 22px", borderRadius: "7px", border: "none", cursor: disabled ? "not-allowed" : "pointer",
    background: disabled ? "#21262d" : "#1f6feb", color: disabled ? "#8b949e" : "#fff",
    fontWeight: 600, fontSize: "13px", transition: "background 0.15s",
    display: "inline-flex", alignItems: "center", gap: "8px",
  }),
  diagResultCard: { background: "#0d1117", border: "1px solid #30363d", borderRadius: "8px",
                    padding: "16px 18px", animation: "fadeIn 0.3s ease" },
  diagSection: { marginBottom: "14px" },
  diagSectionTitle: { fontSize: "11px", fontWeight: 700, color: "#8b949e",
                      textTransform: "uppercase", letterSpacing: "0.6px", marginBottom: "8px" },
  diagText: { fontSize: "13px", color: "#c9d1d9", lineHeight: 1.6 },
  cmdLine: { background: "#161b22", border: "1px solid #30363d", borderRadius: "6px",
             padding: "8px 12px", fontFamily: "monospace", fontSize: "12px",
             color: "#79c0ff", marginBottom: "6px" },
};

// ── Sub-components ────────────────────────────────────────────────────────────

function HealthGauge({ score }) {
  const r = 68, cx = 88, cy = 88;
  const circ = Math.PI * r;
  const dash = (score / 100) * circ;
  const col = scoreColor(score);
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <svg width="176" height="104" viewBox="0 0 176 104">
        <path d={`M ${cx-r} ${cy} A ${r} ${r} 0 0 1 ${cx+r} ${cy}`}
          fill="none" stroke="#21262d" strokeWidth="11" strokeLinecap="round" />
        <path d={`M ${cx-r} ${cy} A ${r} ${r} 0 0 1 ${cx+r} ${cy}`}
          fill="none" stroke={col} strokeWidth="11" strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`} style={{ transition: "stroke-dasharray 0.6s ease" }} />
        <text x={cx} y={cy - 10} textAnchor="middle" fill={col}
          fontSize="32" fontWeight="800" fontFamily="Inter, system-ui, sans-serif">{score}</text>
        <text x={cx} y={cy + 14} textAnchor="middle" fill="#8b949e"
          fontSize="12" fontFamily="Inter, system-ui, sans-serif">{scoreLabel(score)}</text>
      </svg>
      <div style={{ fontSize: "11px", color: "#6e7681", letterSpacing: "0.4px", marginTop: "-4px" }}>HEALTH SCORE</div>
    </div>
  );
}

function PhasePill({ phase, reason }) {
  const val = (reason && reason !== phase && reason !== "Running") ? reason : phase;
  const [bg, fg] =
    val === "Running"          ? ["rgba(34,197,94,0.15)",  "#22c55e"] :
    val === "Succeeded"        ? ["rgba(88,166,255,0.15)", "#58a6ff"] :
    val === "Pending"          ? ["rgba(245,158,11,0.15)", "#f59e0b"] :
    val === "CrashLoopBackOff" ? ["rgba(239,68,68,0.15)",  "#ef4444"] :
    val === "OOMKilled"        ? ["rgba(249,115,22,0.15)", "#f97316"] :
                                 ["rgba(239,68,68,0.12)",  "#ef4444"];
  return <span style={C.pill(bg, fg)}>{val}</span>;
}

function TypePill({ type }) {
  const [bg, fg] = type === "Warning"
    ? ["rgba(245,158,11,0.15)", "#f59e0b"]
    : ["rgba(110,118,129,0.15)", "#8b949e"];
  return <span style={C.pill(bg, fg)}>{type || "—"}</span>;
}

function SevPill({ sev }) {
  const [bg, fg] = sev === "high"
    ? ["rgba(239,68,68,0.15)", "#ef4444"]
    : ["rgba(245,158,11,0.15)", "#f59e0b"];
  return <span style={C.pill(bg, fg)}>{sev.toUpperCase()}</span>;
}

function StatCard({ value, label, color }) {
  return (
    <div style={C.statCard}>
      <div style={{ ...C.statVal, color: color || "#e6edf3" }}>{value}</div>
      <div style={C.statLbl}>{label}</div>
    </div>
  );
}

function EmptyRow({ cols, message }) {
  return (
    <tr>
      <td colSpan={cols} style={{ ...C.td, textAlign: "center", color: "#6e7681", padding: "32px" }}>
        {message}
      </td>
    </tr>
  );
}

// ── Tab: Pods ─────────────────────────────────────────────────────────────────

function PodsTab({ pods }) {
  const [filter, setFilter] = useState("");
  const visible = pods.filter(p =>
    !filter || p.namespace?.includes(filter) || p.name?.includes(filter)
  );
  return (
    <div>
      <div style={{ display: "flex", gap: "10px", marginBottom: "14px" }}>
        <input
          style={{ ...C.diagInput, maxWidth: 280 }}
          placeholder="Filter by name or namespace…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
        />
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={C.tbl}>
          <thead>
            <tr>
              {["Name", "Namespace", "Status", "Restarts", "Node"].map(h => (
                <th key={h} style={C.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.length === 0
              ? <EmptyRow cols={5} message="No pods found" />
              : visible.map(pod => (
                <tr key={`${pod.namespace}/${pod.name}`}
                  style={{ transition: "background 0.1s" }}
                  onMouseEnter={e => e.currentTarget.style.background = "#1c2128"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <td style={C.tdMono}>{pod.name}</td>
                  <td style={C.td}><span style={C.pill("rgba(88,166,255,0.1)", "#58a6ff")}>{pod.namespace}</span></td>
                  <td style={C.td}><PhasePill phase={pod.phase} reason={pod.reason} /></td>
                  <td style={{ ...C.td, color: pod.restart_count >= 3 ? "#ef4444" : pod.restart_count > 0 ? "#f59e0b" : "#22c55e", fontWeight: 600 }}>
                    {pod.restart_count ?? 0}
                  </td>
                  <td style={{ ...C.td, color: "#8b949e", fontSize: "12px" }}>{pod.node || "—"}</td>
                </tr>
              ))
            }
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Tab: Events ───────────────────────────────────────────────────────────────

function EventsTab({ events }) {
  const [showWarnings, setShowWarnings] = useState(false);
  const visible = showWarnings ? events.filter(e => e.type === "Warning") : events;
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "14px" }}>
        <label style={{ display: "flex", alignItems: "center", gap: "6px",
                        fontSize: "13px", color: "#8b949e", cursor: "pointer" }}>
          <input type="checkbox" checked={showWarnings}
            onChange={e => setShowWarnings(e.target.checked)}
            style={{ accentColor: "#f59e0b" }} />
          Warnings only
        </label>
        <span style={{ fontSize: "12px", color: "#6e7681", marginLeft: "auto" }}>
          {visible.length} events
        </span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={C.tbl}>
          <thead>
            <tr>
              {["Type", "Reason", "Namespace", "Message", "Count", "Time"].map(h => (
                <th key={h} style={C.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.length === 0
              ? <EmptyRow cols={6} message="No events" />
              : visible.map((ev, i) => (
                <tr key={ev.name || i}
                  onMouseEnter={e => e.currentTarget.style.background = "#1c2128"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <td style={C.td}><TypePill type={ev.type} /></td>
                  <td style={{ ...C.td, fontWeight: 600, color: ev.type === "Warning" ? "#f59e0b" : "#8b949e" }}>
                    {ev.reason || "—"}
                  </td>
                  <td style={C.td}><span style={C.pill("rgba(88,166,255,0.1)", "#58a6ff")}>{ev.namespace || "—"}</span></td>
                  <td style={{ ...C.td, color: "#c9d1d9", maxWidth: 420,
                               overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {ev.message || "—"}
                  </td>
                  <td style={{ ...C.td, color: "#8b949e", textAlign: "center" }}>{ev.count ?? 1}</td>
                  <td style={{ ...C.td, color: "#6e7681", fontSize: "12px", whiteSpace: "nowrap" }}>
                    {fmtTime(ev.last_timestamp)}
                  </td>
                </tr>
              ))
            }
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Tab: Resources ────────────────────────────────────────────────────────────

function ResourcesTab({ resources }) {
  const nodes = resources.nodes || [];
  const deployments = resources.deployments || [];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Nodes */}
      <div>
        <div style={{ ...C.cardTitle, marginBottom: "10px" }}>Nodes ({nodes.length})</div>
        <table style={C.tbl}>
          <thead>
            <tr>
              {["Name", "Status", "CPU Capacity", "Memory Capacity", "CPU Allocatable", "Memory Allocatable"].map(h => (
                <th key={h} style={C.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {nodes.length === 0
              ? <EmptyRow cols={6} message="No nodes" />
              : nodes.map(node => (
                <tr key={node.name}
                  onMouseEnter={e => e.currentTarget.style.background = "#1c2128"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <td style={C.tdMono}>{node.name}</td>
                  <td style={C.td}>
                    <span style={C.pill(
                      node.ready ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                      node.ready ? "#22c55e" : "#ef4444"
                    )}>{node.ready ? "Ready" : "NotReady"}</span>
                  </td>
                  <td style={{ ...C.td, color: "#8b949e" }}>{node.cpu_capacity || "—"}</td>
                  <td style={{ ...C.td, color: "#8b949e" }}>{node.memory_capacity || "—"}</td>
                  <td style={{ ...C.td, color: "#8b949e" }}>{node.cpu_allocatable || "—"}</td>
                  <td style={{ ...C.td, color: "#8b949e" }}>{node.memory_allocatable || "—"}</td>
                </tr>
              ))
            }
          </tbody>
        </table>
      </div>

      {/* Deployments */}
      <div>
        <div style={{ ...C.cardTitle, marginBottom: "10px" }}>Deployments ({deployments.length})</div>
        <table style={C.tbl}>
          <thead>
            <tr>
              {["Name", "Namespace", "Desired", "Ready", "Available", "Status"].map(h => (
                <th key={h} style={C.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {deployments.length === 0
              ? <EmptyRow cols={6} message="No deployments" />
              : deployments.map(dep => {
                  const healthy = dep.ready >= dep.desired && dep.desired > 0;
                  const degraded = dep.ready > 0 && dep.ready < dep.desired;
                  return (
                    <tr key={`${dep.namespace}/${dep.name}`}
                      onMouseEnter={e => e.currentTarget.style.background = "#1c2128"}
                      onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                      <td style={C.tdMono}>{dep.name}</td>
                      <td style={C.td}><span style={C.pill("rgba(88,166,255,0.1)", "#58a6ff")}>{dep.namespace}</span></td>
                      <td style={{ ...C.td, textAlign: "center" }}>{dep.desired}</td>
                      <td style={{ ...C.td, textAlign: "center",
                                   color: dep.ready === dep.desired ? "#22c55e" : dep.ready === 0 ? "#ef4444" : "#f59e0b",
                                   fontWeight: 600 }}>{dep.ready}</td>
                      <td style={{ ...C.td, textAlign: "center" }}>{dep.available}</td>
                      <td style={C.td}>
                        <span style={C.pill(
                          healthy  ? "rgba(34,197,94,0.15)"  :
                          degraded ? "rgba(245,158,11,0.15)" : "rgba(239,68,68,0.15)",
                          healthy  ? "#22c55e" : degraded ? "#f59e0b" : "#ef4444"
                        )}>
                          {healthy ? "Healthy" : degraded ? "Degraded" : "Unavailable"}
                        </span>
                      </td>
                    </tr>
                  );
                })
            }
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Tab: Diagnosis ────────────────────────────────────────────────────────────

function DiagnosisTab() {
  const [focus, setFocus]         = useState("");
  const [result, setResult]       = useState(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);

  const runDiagnosis = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${BASE_URL}/api/diagnose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ focus: focus.trim() || null }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={C.diagWrap}>
      <div style={C.card}>
        <div style={C.cardTitle}>AI Cluster Diagnosis</div>
        <p style={{ fontSize: "13px", color: "#8b949e", marginBottom: "14px", lineHeight: 1.5 }}>
          Claude will analyse the current cluster state and return a root-cause summary
          with actionable remediation commands.
        </p>
        <textarea
          style={{ ...C.diagInput, minHeight: 68 }}
          placeholder="Optional: describe a focus area — e.g. 'ml-pipeline pods are failing'"
          value={focus}
          onChange={e => setFocus(e.target.value)}
          rows={2}
        />
        <div style={{ marginTop: "12px", display: "flex", alignItems: "center", gap: "14px" }}>
          <button style={C.diagBtn(loading)} onClick={runDiagnosis} disabled={loading}>
            {loading && <span style={{ width: 14, height: 14, border: "2px solid #ffffff40",
              borderTop: "2px solid #fff", borderRadius: "50%",
              animation: "spin 0.8s linear infinite", display: "inline-block" }} />}
            {loading ? "Analysing…" : "Run Diagnosis"}
          </button>
          {error && <span style={{ fontSize: "13px", color: "#fca5a5" }}>⚠ {error}</span>}
        </div>
      </div>

      {result && (
        <div style={C.diagResultCard}>
          <div style={C.diagSection}>
            <div style={C.diagSectionTitle}>Summary</div>
            <p style={C.diagText}>{result.summary}</p>
          </div>
          <div style={C.diagSection}>
            <div style={C.diagSectionTitle}>Root Cause</div>
            <p style={{ ...C.diagText, color: "#fca5a5" }}>{result.rootCause}</p>
          </div>
          <div>
            <div style={C.diagSectionTitle}>Remediation Commands</div>
            {(result.kubectlCommands || []).map((cmd, i) => (
              <div key={i} style={C.cmdLine}>$ {cmd}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function KubernetesSentinel() {
  const [activeTab, setActiveTab] = useState("pods");
  const [pods,      setPods]      = useState([]);
  const [events,    setEvents]    = useState([]);
  const [resources, setResources] = useState({ nodes: [], deployments: [] });
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);
  const [sseAlive,  setSseAlive]  = useState(false);
  const esRef = useRef(null);

  // ── Fetch all three endpoints in parallel ──────────────────────────────────
  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pr, er, rr] = await Promise.all([
        fetch(`${BASE_URL}/api/pods`),
        fetch(`${BASE_URL}/api/events`),
        fetch(`${BASE_URL}/api/resources`),
      ]);

      const failed = [pr, er, rr].find(r => !r.ok);
      if (failed) throw new Error(`Server returned ${failed.status} for ${failed.url}`);

      const [podsData, eventsData, resourcesData] = await Promise.all([
        pr.json(), er.json(), rr.json(),
      ]);

      // Map fields: pods use name, namespace, phase, restart_count, node
      setPods(podsData);

      // Map fields: events use reason, namespace, message, type, last_timestamp (as time), count
      setEvents(eventsData);

      // Map fields: resources nested under nodes and deployments keys
      setResources({
        nodes:       resourcesData.nodes       || [],
        deployments: resourcesData.deployments || [],
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // ── SSE stream for live event updates ─────────────────────────────────────
  useEffect(() => {
    const connect = () => {
      const es = new EventSource(`${BASE_URL}/api/events/stream`);
      esRef.current = es;

      es.addEventListener("events", (e) => {
        try {
          const data = JSON.parse(e.data);
          setEvents(data);
          setSseAlive(true);
        } catch {}
      });

      es.onerror = () => {
        setSseAlive(false);
        es.close();
        // Reconnect after 5 s
        setTimeout(connect, 5000);
      };
    };

    connect();
    return () => {
      esRef.current?.close();
    };
  }, []);

  // ── Initial fetch ──────────────────────────────────────────────────────────
  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ── Derived values ─────────────────────────────────────────────────────────
  const score     = calcHealthScore(pods, resources);
  const anomalies = detectAnomalies(pods, events, resources);
  const warnings  = events.filter(e => e.type === "Warning").length;
  const notReady  = (resources.nodes || []).filter(n => !n.ready).length;
  const unhealthy = pods.filter(p =>
    (p.reason || "").includes("CrashLoopBackOff") || p.restart_count >= 3
  ).length;

  const TABS = [
    { id: "pods",      label: `Pods (${pods.length})` },
    { id: "events",    label: `Events (${events.length})` },
    { id: "resources", label: "Resources" },
    { id: "diagnosis", label: "Diagnosis" },
  ];

  // ── Loading screen ─────────────────────────────────────────────────────────
  if (loading) return (
    <>
      <style>{GLOBAL_CSS}</style>
      <div style={C.loadWrap}>
        <div style={C.spinner} />
        <div style={C.loadTxt}>Connecting to cluster…</div>
      </div>
    </>
  );

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      <style>{GLOBAL_CSS}</style>
      <div style={C.root}>

        {/* Header */}
        <header style={C.header}>
          <svg style={C.logo} viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="13" stroke="#58a6ff" strokeWidth="1.5" />
            <path d="M14 6l2.5 5h5.5l-4.5 3.5 1.5 5.5L14 17l-5 3 1.5-5.5L6 11h5.5z"
              fill="#58a6ff" opacity="0.9" />
          </svg>
          <span style={C.title}>k8s-sentinel</span>
          <span style={C.badge}>DEV</span>
          <div style={C.liveIndicator}>
            <span style={C.liveDot(sseAlive)} />
            <span>{sseAlive ? "Live" : "Polling"}</span>
          </div>
        </header>

        <main style={C.main}>

          {/* Error banner */}
          {error && (
            <div style={C.errBanner}>
              <span style={C.errMsg}>⚠ {error}</span>
              <button style={C.retryBtn} onClick={fetchAll}>Retry</button>
            </div>
          )}

          {/* Top row: gauge + stats */}
          <div style={C.topGrid}>
            <div style={C.card}>
              <HealthGauge score={score} />
            </div>
            <div style={{ ...C.card, display: "flex", flexDirection: "column", justifyContent: "center" }}>
              <div style={{ ...C.cardTitle, marginBottom: "16px" }}>Cluster Overview</div>
              <div style={C.statRow}>
                <StatCard value={pods.length}     label="Total Pods"       />
                <StatCard value={unhealthy}        label="Unhealthy Pods"  color={unhealthy  > 0 ? "#ef4444" : "#22c55e"} />
                <StatCard value={resources.nodes?.length ?? 0} label="Nodes" />
                <StatCard value={notReady}         label="NotReady Nodes"  color={notReady   > 0 ? "#ef4444" : "#22c55e"} />
                <StatCard value={warnings}         label="Warnings"        color={warnings   > 0 ? "#f59e0b" : "#22c55e"} />
                <StatCard value={anomalies.length} label="Anomalies"       color={anomalies.length > 0 ? "#ef4444" : "#22c55e"} />
              </div>
            </div>
          </div>

          {/* Anomaly banner */}
          {anomalies.length > 0 && (
            <div style={C.anomalyWrap}>
              <div style={{ ...C.card, padding: "14px 18px" }}>
                <div style={{ ...C.cardTitle, marginBottom: "10px" }}>
                  ⚠ Anomalies Detected ({anomalies.length})
                </div>
                {anomalies.map((a, i) => (
                  <div key={i} style={C.anomalyRow(a.sev)}>
                    <span style={C.anomalyIcon(a.sev)}>{a.sev === "high" ? "🔴" : "🟡"}</span>
                    <div style={{ flex: 1 }}>
                      <span style={{ fontWeight: 700, fontSize: "13px",
                                     color: a.sev === "high" ? "#fca5a5" : "#fde68a",
                                     marginRight: 8 }}>{a.label}</span>
                      {a.namespace && (
                        <span style={C.pill("rgba(88,166,255,0.1)", "#58a6ff")}>
                          {a.namespace}
                        </span>
                      )}
                      <div style={{ fontSize: "12px", color: "#8b949e", marginTop: "4px" }}>
                        {a.detail}
                      </div>
                    </div>
                    <SevPill sev={a.sev} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tab bar */}
          <div style={C.tabBar}>
            {TABS.map(t => (
              <button key={t.id} style={C.tab(activeTab === t.id)}
                onClick={() => setActiveTab(t.id)}>
                {t.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div style={C.card}>
            {activeTab === "pods"      && <PodsTab      pods={pods} />}
            {activeTab === "events"    && <EventsTab    events={events} />}
            {activeTab === "resources" && <ResourcesTab resources={resources} />}
            {activeTab === "diagnosis" && <DiagnosisTab />}
          </div>

        </main>
      </div>
    </>
  );
}
