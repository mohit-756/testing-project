import { useEffect, useMemo, useState } from "react";
import {
  Search, ChevronLeft, ChevronRight, Eye, Trash2, ArrowUpDown,
  Table as TableIcon, LayoutGrid, Users, Target, BarChart3,
  CheckCircle2, FileText, Filter, Briefcase,
} from "lucide-react";
import { Link } from "react-router-dom";
import StatusBadge from "../components/StatusBadge";
import ScoreBadge from "../components/ScoreBadge";
import ScoreProgressCell from "../components/ScoreProgressCell";
import MetricCard from "../components/MetricCard";
import { hrApi } from "../services/api";
import { ATS_STAGE_OPTIONS } from "../utils/stages";
import { cn } from "../utils/utils";

function SortButton({ column, label, sortKey, onSort }) {
  return (
    <button
      type="button"
      onClick={() => onSort(column)}
      className="flex items-center space-x-1 hover:text-blue-600 transition-colors uppercase tracking-wider font-bold"
    >
      <span>{label}</span>
      <ArrowUpDown size={12} className={cn(sortKey === column ? "text-blue-600" : "text-slate-400 opacity-50")} />
    </button>
  );
}

function average(values) {
  if (!values.length) return 0;
  return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
}

export default function HRScoreMatrixPage() {
  const [view, setView] = useState("table");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [jdFilter, setJdFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [decisionFilter, setDecisionFilter] = useState("all");
  const [sortConfig, setSortConfig] = useState({ key: "finalAIScore", direction: "desc" });
  const [page, setPage] = useState(1);
  const [jdList, setJdList] = useState([]);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  async function loadRows() {
    setLoading(true);
    setError("");
    try {
      // Load JDs for the filter dropdown
      const jdsResponse = await hrApi.listJds();
      setJdList(Array.isArray(jdsResponse) ? jdsResponse : jdsResponse?.jds || jdsResponse?.jobs || []);

      let pageNumber = 1;
      let hasMore = true;
      let allCandidates = [];
      while (hasMore) {
        const response = await hrApi.listCandidates({ page: pageNumber });
        allCandidates = allCandidates.concat(response.candidates || []);
        hasMore = response.has_next;
        pageNumber += 1;
      }
      const candidateUids = allCandidates.map((c) => c.candidate_uid);
      const batchResponse = await hrApi.batchCandidateDetails(candidateUids);
      const candidatesData = batchResponse.candidates || {};
      const details = candidateUids.map((uid) => candidatesData[uid] || { candidate: {}, applications: [] });
      const detailMap = new Map(details.map((detail) => [detail.candidate?.candidate_uid || detail.candidate?.uid, detail]));
      const mergedRows = allCandidates.map((candidate) => {
        const detail = detailMap.get(candidate.candidate_uid);
        const detailCandidate = detail?.candidate || {};
        const application = detail?.applications?.[0] || {};
        return {
          ...candidate,
          uid: candidate.candidate_uid,
          semanticScore: Number(detailCandidate.semanticScore || 0),
          skillMatchScore: Number(detailCandidate.skillMatchScore || 0),
          resumeScore: Number(detailCandidate.resumeScore || candidate.resumeScore || 0),
          interviewScore: detailCandidate.interviewScore === null || detailCandidate.interviewScore === undefined ? 0 : Number(detailCandidate.interviewScore),
          communicationScore: detailCandidate.communicationScore === null || detailCandidate.communicationScore === undefined ? 0 : Number(detailCandidate.communicationScore),
          finalAIScore: Number(detailCandidate.finalAIScore || candidate.resumeScore || 0),
          finalDecision: detailCandidate.finalDecision || candidate.finalDecision,
          interviewStatus: application.status || candidate.status,
          // JD info for filter
          jobId: application.job?.id || null,
          jobTitle: application.job?.title || candidate.role || "—",
        };
      });
      setRows(mergedRows);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadRows(); }, []);

  const filteredCandidates = useMemo(() => {
    return rows
      .filter((candidate) => {
        const matchesSearch =
          candidate.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          candidate.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
          String(candidate.candidate_uid || "").toLowerCase().includes(searchTerm.toLowerCase());
        const matchesJd = jdFilter === "all" || String(candidate.jobId) === jdFilter || candidate.jobTitle === jdFilter;
        const matchesStatus = statusFilter === "all" || candidate.status?.key === statusFilter;
        const matchesDecision = decisionFilter === "all" || (candidate.finalDecision?.key || candidate.status?.key) === decisionFilter;
        return matchesSearch && matchesJd && matchesStatus && matchesDecision;
      })
      .sort((left, right) => {
        const leftValue = Number(left[sortConfig.key] || 0);
        const rightValue = Number(right[sortConfig.key] || 0);
        if (leftValue < rightValue) return sortConfig.direction === "asc" ? -1 : 1;
        if (leftValue > rightValue) return sortConfig.direction === "asc" ? 1 : -1;
        return 0;
      });
  }, [rows, searchTerm, jdFilter, statusFilter, decisionFilter, sortConfig]);

  useEffect(() => { setPage(1); }, [searchTerm, jdFilter, statusFilter, decisionFilter, sortConfig, itemsPerPage]);

  const totalPages = Math.max(1, Math.ceil(filteredCandidates.length / itemsPerPage));
  const paginatedCandidates = filteredCandidates.slice((page - 1) * itemsPerPage, page * itemsPerPage);

  const requestSort = (key) => {
    setSortConfig((prev) => ({ key, direction: prev.key === key && prev.direction === "desc" ? "asc" : "desc" }));
  };

  async function handleDelete(candidateUid) {
    try {
      await hrApi.deleteCandidate(candidateUid);
      await loadRows();
    } catch (deleteError) {
      setError(deleteError.message);
    }
  }

  // Per-JD stats for the JD summary cards
  const jdStats = useMemo(() => {
    const map = {};
    rows.forEach((r) => {
      const key = String(r.jobId || r.jobTitle || "Unknown");
      const label = r.jobTitle || "Unknown";
      if (!map[key]) map[key] = { label, count: 0, scores: [], shortlisted: 0 };
      map[key].count++;
      if (r.finalAIScore > 0) map[key].scores.push(r.finalAIScore);
      if ((r.finalDecision?.key === "shortlisted" || r.finalDecision?.key === "selected") || (r.status?.key === "shortlisted" || r.status?.key === "selected")) map[key].shortlisted++;
    });
    return Object.entries(map).map(([key, val]) => ({
      key,
      label: val.label,
      count: val.count,
      avgScore: val.scores.length ? Math.round(val.scores.reduce((a, b) => a + b, 0) / val.scores.length) : 0,
      shortlisted: val.shortlisted,
    }));
  }, [rows]);

  const resumeScores = filteredCandidates.map((c) => c.resumeScore);
  const interviewScores = filteredCandidates.map((c) => c.interviewScore).filter((v) => v > 0);
  const finalScores = filteredCandidates.map((c) => c.finalAIScore);
  const shortlistedCount = filteredCandidates.filter((c) => (c.finalDecision?.key === "shortlisted" || c.finalDecision?.key === "selected") || (c.status?.key === "shortlisted" || c.status?.key === "selected")).length;

  if (loading && !rows.length) return <p className="center muted py-12">Loading candidate score matrix...</p>;

  return (
    <div className="space-y-8 pb-12">
      {error ? <p className="alert error">{error}</p> : null}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white font-display">Candidate Score Matrix</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Compare backend-derived screening and interview metrics across all candidates.</p>
        </div>
        <div className="flex p-1 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <button type="button" onClick={() => setView("table")} className={cn("flex items-center space-x-2 px-4 py-2 rounded-xl text-sm font-bold transition-all", view === "table" ? "bg-blue-600 text-white shadow-lg" : "text-slate-500 hover:text-slate-700")}>
            <TableIcon size={18} /><span>Table View</span>
          </button>
          <button type="button" onClick={() => setView("matrix")} className={cn("flex items-center space-x-2 px-4 py-2 rounded-xl text-sm font-bold transition-all", view === "matrix" ? "bg-blue-600 text-white shadow-lg" : "text-slate-500 hover:text-slate-700")}>
            <LayoutGrid size={18} /><span>Matrix View</span>
          </button>
        </div>
      </div>

      {/* Summary Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard title="Total Candidates" value={filteredCandidates.length} icon={Users} color="blue" />
        <MetricCard title="Avg Resume Score" value={`${average(resumeScores)}%`} icon={FileText} color="purple" />
        <MetricCard title="Avg Interview Score" value={`${average(interviewScores)}%`} icon={Target} color="green" />
        <MetricCard title="Top Final Score" value={`${Math.max(...finalScores, 0)}%`} icon={BarChart3} color="yellow" />
        <MetricCard title="Shortlisted Count" value={shortlistedCount} icon={CheckCircle2} color="green" />
      </div>

      {/* JD Breakdown Cards — NEW */}
      {jdStats.length > 0 && (
        <div>
          <h2 className="text-sm font-black text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2">
            <Briefcase size={14} />Per JD Breakdown
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {jdStats.map((jd) => (
              <button
                key={jd.key}
                type="button"
                onClick={() => setJdFilter(jdFilter === jd.key ? "all" : jd.key)}
                className={cn(
                  "text-left p-4 rounded-2xl border transition-all",
                  jdFilter === jd.key
                    ? "bg-blue-600 border-blue-600 text-white shadow-lg shadow-blue-100 dark:shadow-none"
                    : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 hover:border-blue-300"
                )}
              >
                <p className={cn("text-xs font-bold uppercase tracking-wider mb-1 truncate", jdFilter === jd.key ? "text-blue-100" : "text-slate-500")}>{jd.label}</p>
                <div className="flex items-end justify-between mt-2">
                  <div>
                    <p className={cn("text-2xl font-black", jdFilter === jd.key ? "text-white" : "text-slate-900 dark:text-white")}>{jd.count}</p>
                    <p className={cn("text-xs", jdFilter === jd.key ? "text-blue-100" : "text-slate-400")}>applicants</p>
                  </div>
                  <div className="text-right">
                    <p className={cn("text-lg font-black", jdFilter === jd.key ? "text-white" : "text-blue-600")}>{jd.avgScore}%</p>
                    <p className={cn("text-xs", jdFilter === jd.key ? "text-blue-100" : "text-slate-400")}>{jd.shortlisted} shortlisted</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
          {jdFilter !== "all" && (
            <button onClick={() => setJdFilter("all")} className="mt-2 text-xs text-blue-600 hover:underline font-bold">
              ✕ Clear JD filter
            </button>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex items-center gap-2 mb-1">
          <Filter size={14} className="text-slate-400" />
          <span className="text-xs font-black text-slate-400 uppercase tracking-widest">Filters</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="relative lg:col-span-2">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Search by name, email, or ID..."
              className="w-full pl-11 pr-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm font-medium dark:text-white"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          {/* JD Filter dropdown */}
          <select
            className="px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm font-medium dark:text-white"
            value={jdFilter}
            onChange={(e) => setJdFilter(e.target.value)}
          >
            <option value="all">All JDs</option>
            {jdList.map((jd) => (
              <option key={jd.id} value={String(jd.id)}>{jd.title}</option>
            ))}
          </select>
          <select
            className="px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm font-medium dark:text-white"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">Interview Status: All</option>
            {ATS_STAGE_OPTIONS.map((stage) => <option key={stage.value} value={stage.value}>{stage.label}</option>)}
            <option value="completed">Completed</option>
          </select>
          <select
            className="px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm font-medium dark:text-white"
            value={decisionFilter}
            onChange={(e) => setDecisionFilter(e.target.value)}
          >
            <option value="all">Decision: All</option>
            <option value="selected">Selected</option>
            <option value="shortlisted">Shortlisted</option>
            <option value="pending">Pending</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
        <p className="text-xs text-slate-400 font-bold uppercase tracking-widest pl-1">
          Showing {paginatedCandidates.length} of {filteredCandidates.length} matching candidates
          {jdFilter !== "all" && <span className="ml-2 text-blue-500">· filtered by JD</span>}
        </p>
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-slate-900 rounded-[32px] border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/30 border-b border-slate-100 dark:border-slate-800">
                <th className="px-6 py-5 text-[10px] text-slate-400 uppercase tracking-widest font-black">Candidate Info</th>
                <th className="px-6 py-5 text-[10px] text-slate-400 uppercase tracking-widest font-black">Applied JD</th>
                <th className="px-6 py-5 min-w-[110px]"><SortButton column="semanticScore" label="Semantic" sortKey={sortConfig.key} onSort={requestSort} /></th>
                <th className="px-6 py-5 min-w-[110px]"><SortButton column="skillMatchScore" label="Skill Match" sortKey={sortConfig.key} onSort={requestSort} /></th>
<th className="px-6 py-5 min-w-[110px]"><SortButton column="resumeScore" label="Resume" sortKey={sortConfig.key} onSort={requestSort} /></th>
                <th className="px-6 py-5 min-w-[110px]"><SortButton column="interviewScore" label="Interview" sortKey={sortConfig.key} onSort={requestSort} /></th>
                <th className="px-6 py-5 min-w-[110px]"><SortButton column="communicationScore" label="Comm." sortKey={sortConfig.key} onSort={requestSort} /></th>
                <th className="px-6 py-5 min-w-[110px] bg-blue-50/20 dark:bg-blue-900/10"><SortButton column="finalAIScore" label="Final AI" sortKey={sortConfig.key} onSort={requestSort} /></th>
                <th className="px-6 py-5 text-[10px] text-slate-400 uppercase tracking-widest font-black">Decision</th>
                <th className="px-6 py-5 text-[10px] text-slate-400 uppercase tracking-widest font-black">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50 dark:divide-slate-800">
              {!paginatedCandidates.length ? (
                <tr><td colSpan={10} className="px-6 py-12 text-center text-sm text-slate-500 dark:text-slate-400">No candidates match the current filters.</td></tr>
              ) : paginatedCandidates.map((candidate) => (
                <tr key={candidate.candidate_uid} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-all group">
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-3">
                      <div className="w-9 h-9 rounded-xl bg-slate-100 dark:bg-slate-800 overflow-hidden ring-2 ring-transparent group-hover:ring-blue-100 dark:group-hover:ring-blue-900 transition-all">
                        <img src={candidate.avatar} alt="" className="w-full h-full object-cover" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-slate-900 dark:text-white truncate">{candidate.name}</p>
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{candidate.candidate_uid}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-xs font-bold text-slate-600 dark:text-slate-300 max-w-[140px] truncate">{candidate.jobTitle}</p>
                  </td>
                  <td className="px-6 py-4">{view === "matrix" ? <ScoreProgressCell score={candidate.semanticScore} /> : <ScoreBadge score={candidate.semanticScore} />}</td>
                  <td className="px-6 py-4">{view === "matrix" ? <ScoreProgressCell score={candidate.skillMatchScore} /> : <ScoreBadge score={candidate.skillMatchScore} />}</td>
                  <td className="px-6 py-4">{view === "matrix" ? <ScoreProgressCell score={candidate.resumeScore} /> : <ScoreBadge score={candidate.resumeScore} />}</td>
                  <td className="px-6 py-4">{view === "matrix" ? <ScoreProgressCell score={candidate.interviewScore} /> : <ScoreBadge score={candidate.interviewScore} />}</td>
                  <td className="px-6 py-4">{view === "matrix" ? <ScoreProgressCell score={candidate.communicationScore} /> : <ScoreBadge score={candidate.communicationScore} />}</td>
                  <td className="px-6 py-4 bg-blue-50/20 dark:bg-blue-900/5">
                    {view === "matrix" ? <ScoreProgressCell score={candidate.finalAIScore} /> : <ScoreBadge score={candidate.finalAIScore} className="scale-110 shadow-sm" />}
                  </td>
                  <td className="px-6 py-4"><StatusBadge status={candidate.finalDecision} /></td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center space-x-2">
                      <Link to={`/hr/candidates/${candidate.candidate_uid}`} className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-xl transition-all"><Eye size={18} /></Link>
                      <button type="button" onClick={() => handleDelete(candidate.candidate_uid)} className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-all"><Trash2 size={18} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="p-6 bg-slate-50/30 dark:bg-slate-800/20 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-sm font-medium text-slate-500">Show</span>
            <select value={itemsPerPage} onChange={(e) => { setItemsPerPage(Number(e.target.value)); setPage(1); }} className="px-2 py-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm dark:text-white">
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={15}>15</option>
              <option value={25}>25</option>
            </select>
            <span className="text-sm font-medium text-slate-500">per page</span>
            <span className="text-sm text-slate-400 ml-2">({filteredCandidates.length} total)</span>
          </div>
          <div className="flex items-center space-x-2">
            <button type="button" disabled={page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))} className="p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 text-slate-500 hover:bg-white dark:hover:bg-slate-900 disabled:opacity-30 transition-all"><ChevronLeft size={20} /></button>
            <div className="flex items-center space-x-1 px-4"><span className="text-sm font-black text-slate-900 dark:text-white">Page {page}</span><span className="text-sm text-slate-400">of {totalPages}</span></div>
            <button type="button" disabled={page === totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} className="p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 text-slate-500 hover:bg-white dark:hover:bg-slate-900 disabled:opacity-30 transition-all"><ChevronRight size={20} /></button>
          </div>
        </div>
      </div>
    </div>
  );
}