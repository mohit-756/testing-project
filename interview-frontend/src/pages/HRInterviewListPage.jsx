import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Eye, Search, AlertTriangle, ChevronLeft, ChevronRight, X, Video, CheckCircle, PlayCircle } from "lucide-react";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { hrApi } from "../services/api";
import { formatDateTime } from "../utils/formatters";

const STATUS_TABS = [
  { key: "all", label: "All", icon: Video },
  { key: "in_progress", label: "Active", icon: PlayCircle },
  { key: "completed", label: "Completed", icon: CheckCircle },
  { key: "finalized", label: "Finalized", icon: CheckCircle },
  { key: "suspicious", label: "Suspicious", icon: AlertTriangle },
];

const getStatusTab = (row) => {
  if ((row.suspicious_events_count ?? 0) > 0) return "suspicious";
  if (row.status === "completed" || row.status === "selected" || row.status === "rejected") return "finalized";
  if (row.status === "in_progress") return "in_progress";
  return "completed";
};

function buildAvatar(name) {
  const seed = String(name || "user").trim() || "user";
  return `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(seed)}`;
}

export default function HRInterviewListPage() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("all");
  const [page, setPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [suspiciousModal, setSuspiciousModal] = useState(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const response = await hrApi.interviews();
        setData(response.interviews || []);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filteredRows = useMemo(() => {
    const needle = search.trim().toLowerCase();
    let rows = data;
    if (activeTab !== "all") {
      rows = rows.filter((row) => getStatusTab(row) === activeTab);
    }
    if (needle) {
      rows = rows.filter((row) => {
        const candidateName = row.candidate?.name || "";
        const candidateEmail = row.candidate?.email || "";
        const jobTitle = row.job?.title || "";
        const applicationId = row.application_id || "";
        return [candidateName, candidateEmail, jobTitle, applicationId, row.status || ""]
          .some((value) => String(value).toLowerCase().includes(needle));
      });
    }
    return rows;
  }, [data, search, activeTab]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / itemsPerPage));
  const paginatedRows = filteredRows.slice((page - 1) * itemsPerPage, page * itemsPerPage);

  useEffect(() => { setPage(1); }, [search, activeTab, itemsPerPage]);

  const stats = useMemo(() => {
    const total = data.length;
    const inProgress = data.filter((r) => r.status === "in_progress").length;
    const completed = data.filter((r) => r.status === "completed").length;
    const finalized = data.filter((r) => r.status === "selected" || r.status === "rejected").length;
    const suspiciousRows = data.filter((r) => (r.suspicious_events_count ?? 0) > 0).length;
    return { total, inProgress, completed, finalized, suspiciousRows };
  }, [data]);

  const getScoreBadge = (row) => {
    const score = row.final_score ?? row.ai_score ?? null;
    if (score === null) return <span className="text-slate-400">—</span>;
    const tone = score >= 75 ? "success" : score >= 50 ? "warning" : "danger";
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-bold ${
        tone === "success" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" :
        tone === "warning" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" :
        "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
      }`}>
        {Math.round(score)}%
      </span>
    );
  };

  const getDurationDisplay = (row) => {
    if (!row.started_at) return <span className="text-slate-400">—</span>;
    const started = new Date(row.started_at);
    const ended = row.ended_at ? new Date(row.ended_at) : new Date();
    const durationMs = ended - started;
    const minutes = Math.round(durationMs / 60000);
    if (minutes < 1) return <span className="text-slate-400">{'<1'}m</span>;
    if (minutes < 60) return <span className="text-sm">{minutes}m</span>;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return <span className="text-sm">{hours}h {mins}m</span>;
  };

  const getRowStatusBadge = (row) => {
    const key = getStatusTab(row);
    const config = {
      all: { key: "all", label: "All", tone: "secondary" },
      in_progress: { key: "in_progress", label: "Active", tone: "primary" },
      completed: { key: "completed", label: "Completed", tone: "secondary" },
      finalized: { key: "finalized", label: "Finalized", tone: "success" },
      suspicious: { key: "suspicious", label: "Review Needed", tone: "danger" },
    };
    return <StatusBadge status={config[key]} />;
  };

  if (loading) return (
    <div className="page-enter">
      <PageHeader title="Interview Reviews" subtitle="Review completed sessions, suspicious events, and finalize outcomes." />
      <div className="flex items-center justify-center py-20">
        <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    </div>
  );

  return (
    <div className="stack page-enter">
      <PageHeader
        title="Interview Reviews"
        subtitle="Review completed sessions, suspicious events, and finalize outcomes."
        actions={
          <Link to="/hr" className="button-link subtle-button">
            Back to HR Dashboard
          </Link>
        }
      />

      {error && <p className="alert error">{error}</p>}

      {data.length === 0 ? (
        <section className="card stack">
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
            <div className="w-16 h-16 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center mb-4">
              <Video size={24} className="text-slate-400" />
            </div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-1">
              No interviews yet
            </h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 max-w-xs">
              Candidates will appear here after completing their interview sessions.
            </p>
          </div>
        </section>
      ) : (
        <section className="card stack">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
            <div className="flex flex-wrap items-center gap-1.5">
              {STATUS_TABS.map((tab) => {
                const Icon = tab.icon;
                const count = tab.key === "all" ? stats.total
                  : tab.key === "in_progress" ? stats.inProgress
                  : tab.key === "completed" ? stats.completed
                  : tab.key === "finalized" ? stats.finalized
                  : stats.suspiciousRows;
                return (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveTab(tab.key)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                      activeTab === tab.key
                        ? tab.key === "suspicious" ? "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400" :
                          tab.key === "in_progress" ? "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400" :
                          "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                        : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    }`}
                  >
                    <Icon size={14} />
                    {tab.label}
                    <span className={`ml-0.5 px-1.5 py-0.5 rounded-full text-xs ${
                      activeTab === tab.key
                        ? "bg-white/70 dark:bg-black/20"
                        : "bg-slate-100 dark:bg-slate-700"
                    }`}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="relative w-full sm:w-56">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              <input
                type="search"
                placeholder="Search..."
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm"
              />
            </div>
          </div>

          {!paginatedRows.length && (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
              <div className="w-16 h-16 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center mb-4">
                <Video size={24} className="text-slate-400" />
              </div>
              <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-1">
                {activeTab === "all" ? "No interviews yet" : `No ${activeTab.replace("_", " ")} interviews`}
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 max-w-xs">
                {activeTab === "all" 
                  ? "Candidates will appear here after completing their interview sessions."
                  : "No interviews match this filter."}
              </p>
            </div>
          )}
          {!!paginatedRows.length && (
            <div className="overflow-x-auto -mx-4 sm:mx-0">
              <table className="table">
                <thead>
                  <tr>
                    <th>Application</th>
                    <th>Candidate</th>
                    <th>Job</th>
                    <th>Status</th>
                    <th>Started</th>
                    <th>Events</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedRows.map((row) => (
                    <tr key={row.interview_id}>
                      <td className="text-sm font-mono text-slate-500">{row.application_id || "N/A"}</td>
                      <td>
                        <div className="flex items-center gap-3">
                          <img
                            src={buildAvatar(row.candidate?.name)}
                            alt=""
                            className="w-9 h-9 rounded-full bg-slate-100 dark:bg-slate-800"
                          />
                          <div className="stack-sm">
                            <strong className="text-sm">{row.candidate?.name}</strong>
                            <span className="muted text-xs">{row.candidate?.email}</span>
                          </div>
                        </div>
                      </td>
                      <td className="text-sm">{row.job?.title || "—"}</td>
                      <td>{getRowStatusBadge(row)}</td>
                      <td className="text-sm text-slate-500">{formatDateTime(row.started_at)}</td>
                      <td className="text-center">
                        <div className="flex items-center justify-center gap-1">
                          <span className="text-sm">{row.events_count || 0}</span>
                          {(row.suspicious_events_count ?? 0) > 0 && (
                            <span className="inline-flex items-center px-1.5 py-0.5 bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 rounded text-xs font-bold">
                              {row.suspicious_events_count}
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <Link
                          to={`/hr/interviews/${row.interview_id}`}
                          className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-lg text-sm font-medium hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors"
                        >
                          <Eye size={14} />View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {filteredRows.length > itemsPerPage && (
            <div className="p-4 sm:p-5 bg-slate-50/30 dark:bg-slate-800/20 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3 mt-4">
              <div className="flex items-center gap-2 sm:gap-3 text-xs sm:text-sm">
                <span className="text-slate-500">Show</span>
                <select
                  value={itemsPerPage}
                  onChange={(e) => { setItemsPerPage(Number(e.target.value)); setPage(1); }}
                  className="px-2 py-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm dark:text-white"
                >
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                  <option value={15}>15</option>
                  <option value={25}>25</option>
                </select>
                <span className="text-slate-500">per page</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  disabled={page === 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="p-1.5 sm:p-2 rounded-xl border border-slate-200 dark:border-slate-800 disabled:opacity-30 hover:bg-white dark:hover:bg-slate-900 transition-all"
                >
                  <ChevronLeft size={14} />
                </button>
                <span className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white px-2">
                  Page {page} / {totalPages}
                </span>
                <button
                  disabled={page === totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="p-1.5 sm:p-2 rounded-xl border border-slate-200 dark:border-slate-800 disabled:opacity-30 hover:bg-white dark:hover:bg-slate-900 transition-all"
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {suspiciousModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSuspiciousModal(null)} />
          <div className="relative bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl w-full max-w-lg max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <AlertTriangle className="text-red-500" size={20} />
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">Suspicious Events</h3>
              </div>
              <button type="button" onClick={() => setSuspiciousModal(null)} className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg">
                <X size={20} className="text-slate-500" />
              </button>
            </div>
            <div className="p-4 overflow-y-auto max-h-[60vh]">
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
                Candidate: <span className="font-bold">{suspiciousModal.candidate?.name}</span><br />
                <span className="text-slate-500">Job: {suspiciousModal.job?.title}</span>
              </p>
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-3 mb-4">
                <p className="text-sm text-amber-800 dark:text-amber-200 font-medium">
                  <AlertTriangle size={14} className="inline mr-1" />
                  {suspiciousModal.suspicious_events_count} suspicious event{suspiciousModal.suspicious_events_count !== 1 ? 's' : ''} detected during interview
                </p>
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">Click "View" to see full details and timeline.</p>
              </div>
              <Link
                to={`/hr/interviews/${suspiciousModal.interview_id}`}
                className="flex items-center justify-center gap-2 w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold transition-colors"
                onClick={() => setSuspiciousModal(null)}
              >
                <Eye size={16} />View Full Interview & Timeline
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}