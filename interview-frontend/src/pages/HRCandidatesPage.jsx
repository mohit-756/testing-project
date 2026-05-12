import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, Download, RefreshCw, ChevronLeft, ChevronRight, Eye, Trash2, ArrowUpDown, GitCompareArrows, Calendar, CheckCircle, XCircle, Users, Filter } from "lucide-react";
import StatusBadge from "../components/StatusBadge";
import ScoreBadge from "../components/ScoreBadge";
import EmptyState from "../components/EmptyState";
import { TableSkeleton } from "../components/LoadingSkeleton";
import { useToast } from "../context/ToastContext";
import { hrApi } from "../services/api";
import { ATS_STAGE_DEFINITIONS, ATS_STAGE_OPTIONS } from "../utils/stages";
import { cn } from "../utils/utils";

function SortButton({ column, label, sortKey, onSort }) {
  return (
    <button type="button" onClick={() => onSort(column)} className="flex items-center space-x-1 hover:text-blue-600 transition-colors uppercase tracking-wider font-bold">
      <span>{label}</span>
      <ArrowUpDown size={12} className={cn(sortKey === column ? "text-blue-600" : "text-slate-400 opacity-50")} />
    </button>
  );
}

function normalizeId(value) {
  const id = Number(value);
  return Number.isInteger(id) && id > 0 ? id : null;
}

export default function HRCandidatesPage() {
  const navigate = useNavigate();
  const [allCandidates, setAllCandidates] = useState([]);
  const [availableJds, setAvailableJds] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [jdFilter, setJdFilter] = useState("all");
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [sortConfig, setSortConfig] = useState({ key: "finalAIScore", direction: "desc" });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedForCompare, setSelectedForCompare] = useState([]);
  const [selectedForBulk, setSelectedForBulk] = useState([]);
  const [bulkStage, setBulkStage] = useState("");
  const [bulkLoading, setBulkLoading] = useState(false);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [deletingId, setDeletingId] = useState(null);
  const toast = useToast();

  const loadAllCandidates = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      let pageNumber = 1;
      let hasMore = true;
      let candidates = [];

      while (hasMore) {
        const response = await hrApi.listCandidates({ page: pageNumber, sort: "highest_score" });
        candidates = candidates.concat(response.candidates || []);
        hasMore = response.has_next;
        pageNumber += 1;
      }

      const jds = await hrApi.listJds();
      const safeJds = Array.isArray(jds)
        ? jds
        : Array.isArray(jds?.jobs)
          ? jds.jobs
          : Array.isArray(jds?.jds)
            ? jds.jds
            : [];
      setAvailableJds(safeJds);
      setAllCandidates(Array.isArray(candidates) ? candidates : []);
    } catch (loadError) {
      setError(loadError.message || "Failed to load candidates.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAllCandidates(); }, [loadAllCandidates]);

  const jdOptions = useMemo(() => Array.isArray(availableJds) ? availableJds : [], [availableJds]);

  const filteredCandidates = useMemo(() => {
    return (Array.isArray(allCandidates) ? allCandidates : [])
      .filter((candidate) => {
        const name = String(candidate?.name || "").toLowerCase();
        const email = String(candidate?.email || "").toLowerCase();
        const candidateUid = String(candidate?.candidate_uid || "").toLowerCase();
        const role = String(candidate?.role || "").toLowerCase();
        const query = searchTerm.toLowerCase();
        const matchesSearch = !query || name.includes(query) || email.includes(query) || candidateUid.includes(query) || role.includes(query);
        const matchesStatus = statusFilter === "all" || candidate?.status?.key === statusFilter;
        const assignedJdId = String(candidate?.assignedJd?.id || candidate?.job?.id || "");
        const matchesJd = jdFilter === "all" || assignedJdId === String(jdFilter);
        const finalScore = Number(candidate?.finalAIScore || 0);
        const matchesMin = minScore === "" || finalScore >= Number(minScore);
        const matchesMax = maxScore === "" || finalScore <= Number(maxScore);
        return matchesSearch && matchesStatus && matchesJd && matchesMin && matchesMax;
      })
      .sort((left, right) => {
        const leftValue = Number(left?.[sortConfig.key] || 0);
        const rightValue = Number(right?.[sortConfig.key] || 0);
        if (leftValue < rightValue) return sortConfig.direction === "asc" ? -1 : 1;
        if (leftValue > rightValue) return sortConfig.direction === "asc" ? 1 : -1;
        return 0;
      });
  }, [allCandidates, searchTerm, statusFilter, jdFilter, minScore, maxScore, sortConfig]);

  const stageCounts = useMemo(() => {
    const counts = {};
    ATS_STAGE_DEFINITIONS.forEach((stage) => { counts[stage.key] = 0; });
    allCandidates.forEach((candidate) => {
      const key = candidate?.status?.key || "applied";
      counts[key] = (counts[key] || 0) + 1;
    });
    return counts;
  }, [allCandidates]);

  const totalCandidates = allCandidates.length;
  const filteredCount = filteredCandidates.length;

  const totalPages = Math.max(1, Math.ceil(filteredCandidates.length / itemsPerPage));
  const safePage = Math.min(page, totalPages);
  const paginatedCandidates = filteredCandidates.slice((safePage - 1) * itemsPerPage, safePage * itemsPerPage);

  useEffect(() => { setPage(1); }, [searchTerm, statusFilter, jdFilter, minScore, maxScore, sortConfig]);
  useEffect(() => {
    setSelectedForCompare((prev) => (Array.isArray(prev) ? prev : []).filter((id) => filteredCandidates.some((candidate) => normalizeId(candidate?.result_id) === id)));
    setSelectedForBulk((prev) => (Array.isArray(prev) ? prev : []).filter((id) => filteredCandidates.some((candidate) => normalizeId(candidate?.result_id) === id)));
  }, [filteredCandidates]);

  const requestSort = (key) => {
    let direction = "desc";
    if (sortConfig.key === key && sortConfig.direction === "desc") direction = "asc";
    setSortConfig({ key, direction });
  };

  async function handleDeleteCandidate(candidateUid) {
    if (!window.confirm("Are you sure you want to delete this candidate?")) return;
    setDeletingId(candidateUid);
    try {
      await hrApi.deleteCandidate(candidateUid);
      await loadAllCandidates();
      toast.success("Candidate deleted");
    } catch (deleteError) {
      toast.error(deleteError.message || "Failed to delete candidate.");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleStageUpdate(resultId, stage) {
    const safeResultId = normalizeId(resultId);
    if (!safeResultId || !stage) return;
    try {
      await hrApi.updateCandidateStage(safeResultId, { stage, note: `Updated from candidate table to ${stage}.` });
      await loadAllCandidates();
      toast.success("Stage updated successfully");
    } catch (updateError) {
      toast.error(updateError.message || "Failed to update stage.");
    }
  }

  async function handleBulkStageUpdate(stage) {
    const safeStage = String(stage || bulkStage || "").trim();
    if (!safeStage || !selectedForBulk.length) return;
    setBulkLoading(true);
    setError("");
    try {
      await Promise.all(selectedForBulk.map((resultId) => hrApi.updateCandidateStage(resultId, { stage: safeStage, note: `Bulk updated from candidate table to ${safeStage}.` })));
      toast.success(`Updated ${selectedForBulk.length} candidates to ${safeStage}`);
      setSelectedForBulk([]);
      setBulkStage("");
      await loadAllCandidates();
    } catch (updateError) {
      toast.error(updateError.message || "Failed to update selected candidates.");
    } finally {
      setBulkLoading(false);
    }
  }

  async function handleAssignJd(candidateUid, jdId) {
    if (!candidateUid || !jdId) return;
    try {
      await hrApi.assignCandidateToJd(candidateUid, Number(jdId));
      await loadAllCandidates();
      toast.success("Candidate assigned to JD");
    } catch (assignError) {
      toast.error(assignError.message || "Failed to assign candidate to JD.");
    }
  }

  function handleExportCsv() {
    const header = ["Candidate ID", "Name", "Email", "Applications", "Match %", "Final Score", "Recommendation", "Stage"];
    const rows = filteredCandidates.map((candidate) => [
      candidate?.candidate_uid || "",
      candidate?.name || "",
      candidate?.email || "",
      candidate?.application_count || 1,
      candidate?.matchPercent || 0,
      candidate?.finalAIScore || 0,
      candidate?.recommendationTag || "–",
      candidate?.status?.label || "–",
    ]);
    const csvContent = [header, ...rows].map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "candidates.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  function toggleCompareSelection(candidate) {
    const resultId = normalizeId(candidate?.result_id);
    if (!resultId) return;

    setSelectedForCompare((prev) => {
      const normalizedPrev = (Array.isArray(prev) ? prev : []).filter(Boolean);
      if (normalizedPrev.includes(resultId)) return normalizedPrev.filter((id) => id !== resultId);
      if (normalizedPrev.length >= 3) return [...normalizedPrev.slice(1), resultId];
      return [...normalizedPrev, resultId];
    });
  }

  function toggleBulkSelection(candidate) {
    const resultId = normalizeId(candidate?.result_id);
    if (!resultId) return;
    setSelectedForBulk((prev) => prev.includes(resultId) ? prev.filter((id) => id !== resultId) : [...prev, resultId]);
  }

  function toggleSelectAllCurrentPage() {
    const pageIds = paginatedCandidates.map((candidate) => normalizeId(candidate?.result_id)).filter(Boolean);
    const allSelected = pageIds.length > 0 && pageIds.every((id) => selectedForBulk.includes(id));
    setSelectedForBulk((prev) => {
      const prevSet = new Set(prev);
      if (allSelected) {
        pageIds.forEach((id) => prevSet.delete(id));
      } else {
        pageIds.forEach((id) => prevSet.add(id));
      }
      return Array.from(prevSet);
    });
  }

  function handleCompareNavigate() {
    if (selectedForCompare.length < 2) return;
    navigate(`/hr/compare?ids=${selectedForCompare.join(",")}`);
  }

  const pageIds = paginatedCandidates.map((candidate) => normalizeId(candidate?.result_id)).filter(Boolean);
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedForBulk.includes(id));

  if (loading && !allCandidates.length) {
    return (
      <div className="space-y-8 pb-12">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 page-enter">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-white font-display">Candidate Directory</h1>
            <p className="text-slate-500 dark:text-slate-400 mt-1">Review ATS scores, assigned JDs, pipeline stages, recommendations, compare candidates, and apply bulk actions safely.</p>
          </div>
        </div>
        <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <TableSkeleton rows={10} cols={7} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 page-enter">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white font-display">Candidate Directory</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Review ATS scores, assigned JDs, pipeline stages, recommendations, compare candidates, and apply bulk actions safely.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button type="button" onClick={handleExportCsv} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 px-3 py-2 rounded-lg font-bold flex items-center gap-2 hover:bg-slate-50 dark:hover:bg-slate-800 transition-all text-sm"><Download size={14} /><span>Export</span></button>
          <button type="button" onClick={() => loadAllCandidates()} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 px-3 py-2 rounded-lg font-bold flex items-center gap-2 hover:bg-slate-50 dark:hover:bg-slate-800 transition-all text-sm" title="Refresh"><RefreshCw size={14} /><span>Refresh</span></button>
        </div>
      </div>

      {error && <p className="alert error">{error}</p>}

      <div className="grid grid-cols-2 xs:grid-cols-4 gap-2 sm:gap-3">
        <div className="card p-4 flex items-center gap-3 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
          <Calendar size={20} className="text-blue-600 dark:text-blue-400" />
          <div>
            <p className="text-xs text-blue-600 dark:text-blue-400 font-medium">Scheduled</p>
            <h3 className="text-xl font-bold text-blue-700 dark:text-blue-300">{stageCounts.interview_scheduled || 0}</h3>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-3 bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700">
          <CheckCircle size={20} className="text-slate-600 dark:text-slate-300" />
          <div>
            <p className="text-xs text-slate-600 dark:text-slate-400 font-medium">Completed</p>
            <h3 className="text-xl font-bold text-slate-700 dark:text-slate-300">{stageCounts.interview_completed || 0}</h3>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-3 bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800">
          <CheckCircle size={20} className="text-emerald-600 dark:text-emerald-400" />
          <div>
            <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">Selected</p>
            <h3 className="text-xl font-bold text-emerald-700 dark:text-emerald-300">{stageCounts.selected || 0}</h3>
          </div>
        </div>
        <div className="card p-4 flex items-center gap-3 bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800">
          <XCircle size={20} className="text-red-600 dark:text-red-400" />
          <div>
            <p className="text-xs text-red-600 dark:text-red-400 font-medium">Rejected</p>
            <h3 className="text-xl font-bold text-red-700 dark:text-red-300">{stageCounts.rejected || 0}</h3>
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 p-3 sm:p-4 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-wrap sm:flex-nowrap items-center gap-2 sm:gap-3">
        <div className="relative flex-1 min-w-[140px] w-full sm:w-auto">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
          <input type="text" placeholder="Search..." className="w-full pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm dark:text-white" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} />
        </div>
        
        <select className="px-2 sm:px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm dark:text-white min-w-[80px]" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="all">Stage: All</option>
          {ATS_STAGE_OPTIONS.map((stage) => <option key={stage.value} value={stage.value}>{stage.label}</option>)}
        </select>
        
        <select className="px-2 sm:px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm dark:text-white min-w-[80px]" value={jdFilter} onChange={(event) => setJdFilter(event.target.value)}>
          <option value="all">JD: All</option>
          {jdOptions.map((jd) => <option key={jd.id} value={jd.id}>{jd.title}</option>)}
        </select>

        <button type="button" onClick={handleCompareNavigate} disabled={selectedForCompare.length < 2} className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-40 flex items-center gap-2 whitespace-nowrap">
          <GitCompareArrows size={14} /><span className="hidden sm:inline">Compare</span> ({selectedForCompare.length})
        </button>
      </div>

      {selectedForBulk.length > 0 && (
        <div className="bg-gradient-to-r from-blue-50 to-blue-50/50 dark:from-blue-900/15 dark:to-blue-900/5 rounded-3xl border border-blue-200 dark:border-blue-800 shadow-sm p-6 space-y-4">
          <div className="flex items-center gap-2 mb-3">
            <CheckSquare size={20} className="text-blue-600 dark:text-blue-400" />
            <div>
              <p className="font-bold text-slate-900 dark:text-white">{selectedForBulk.length} candidate{selectedForBulk.length !== 1 ? "s" : ""} selected</p>
              <p className="text-xs text-slate-600 dark:text-slate-400">Choose an action to apply to selected candidates</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
            <button type="button" onClick={() => handleBulkStageUpdate("shortlisted")} disabled={bulkLoading} className="px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white text-sm font-bold transition-all" aria-label={`Move ${selectedForBulk.length} candidates to shortlisted`}>
              ✓ Shortlist All
            </button>
            <button type="button" onClick={() => handleBulkStageUpdate("rejected")} disabled={bulkLoading} className="px-4 py-2.5 rounded-lg bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white text-sm font-bold transition-all" aria-label={`Reject ${selectedForBulk.length} candidates`}>
              ✕ Reject All
            </button>
            <div className="flex items-center gap-2">
              <select value={bulkStage} onChange={(e) => setBulkStage(e.target.value)} className="flex-1 px-4 py-2.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm dark:text-white" aria-label="Select stage for bulk action">
                <option value="">Move to stage...</option>
                {ATS_STAGE_OPTIONS.filter((stage) => stage.value !== "applied").map((stage) => <option key={stage.value} value={stage.value}>{stage.label}</option>)}
              </select>
              <button type="button" onClick={() => handleBulkStageUpdate()} disabled={!bulkStage || bulkLoading} className="px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-bold transition-all" aria-label={`Move ${selectedForBulk.length} candidates to selected stage`}>
                Apply
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/30 border-b border-slate-100 dark:border-slate-800">
                <th className="px-2 py-3 text-[10px] text-slate-400 uppercase tracking-widest font-black w-10">#</th>
                <th className="px-4 py-3 text-[10px] text-slate-400 uppercase tracking-widest font-black">Candidate</th>
                <th className="px-4 py-3 text-[10px] text-slate-400 uppercase tracking-widest font-black">Email</th>
                <th className="px-4 py-3 min-w-[90px]"><SortButton column="resumeScore" label="Match %" sortKey={sortConfig.key} onSort={requestSort} /></th>
                <th className="px-4 py-3 min-w-[90px]"><SortButton column="finalAIScore" label="Final Score" sortKey={sortConfig.key} onSort={requestSort} /></th>
                <th className="px-4 py-3 text-[10px] text-slate-400 uppercase tracking-widest font-black">Stage</th>
                <th className="px-4 py-3 text-[10px] text-slate-400 uppercase tracking-widest font-black">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50 dark:divide-slate-800">
              {!paginatedCandidates.length ? (
                <tr>
                  <td colSpan={7}>
                    <EmptyState 
                      icon="candidates" 
                      title="No candidates found" 
                      description={searchTerm || statusFilter !== "all" || jdFilter !== "all" ? "Try adjusting your filters or search term" : "Add candidates to get started"}
                    />
                  </td>
                </tr>
              ) : paginatedCandidates.map((candidate, index) => {
                const resultId = normalizeId(candidate?.result_id);
                const compareSelectable = Boolean(resultId);
                const compareChecked = compareSelectable && selectedForCompare.includes(resultId);
                const candidateName = candidate?.name || "Unnamed candidate";
                const candidateUid = candidate?.candidate_uid || "No ID";
                const candidateEmail = candidate?.email || "No email";
                const serialNumber = (safePage - 1) * itemsPerPage + index + 1;
                return <tr key={candidateUid} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-all group">
                  <td className="px-2 py-3">
                    <div className="flex items-center gap-2">
                      <input 
                        type="checkbox" 
                        checked={compareChecked} 
                        onChange={() => toggleCompareSelection(candidate)} 
                        disabled={!compareSelectable || (!compareChecked && selectedForCompare.length >= 3)}
                        className="w-4 h-4 rounded border-slate-300 dark:border-slate-600 text-blue-600 focus:ring-blue-500 cursor-pointer" 
                      />
                      <span 
                        onClick={() => compareSelectable && toggleCompareSelection(candidate)}
                        className={compareSelectable ? "text-xs font-bold text-slate-400 dark:text-slate-500 cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 select-none min-w-[20px]" : "text-xs font-bold text-slate-300 dark:text-slate-600"}
                      >
                        {serialNumber}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="min-w-0">
                      <p className="text-sm font-bold text-slate-900 dark:text-white truncate">{candidateName}</p>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{candidateUid}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-300 truncate max-w-[200px]">{candidateEmail}</td>
                  <td className="px-4 py-3"><ScoreBadge score={candidate?.matchPercent || 0} /></td>
                  <td className="px-4 py-3"><ScoreBadge score={candidate?.finalAIScore || 0} /></td>
                  <td className="px-4 py-3"><StatusBadge status={candidate?.status} /></td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Link 
                        to={`/hr/candidates/${candidate?.candidate_uid}`} 
                        className="p-1.5 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-all"
                        title="View candidate"
                      >
                        <Eye size={16} />
                      </Link>
                      <button 
                        onClick={() => handleDeleteCandidate(candidate?.candidate_uid)}
                        disabled={deletingId === candidate?.candidate_uid}
                        className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-all disabled:opacity-40"
                        title="Delete candidate"
                      >
                        {deletingId === candidate?.candidate_uid ? (
                          <span className="w-4 h-4 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <Trash2 size={16} />
                        )}
                      </button>
                    </div>
                  </td>
                </tr>;
              })}
            </tbody>
          </table>
        </div>
        <div className="p-3 sm:p-4 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs sm:text-sm">
            <span className="text-slate-500 dark:text-slate-400">Show</span>
            <select value={itemsPerPage} onChange={(e) => { setItemsPerPage(Number(e.target.value)); setPage(1); }} className="px-2 py-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm dark:text-white">
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
            <span className="text-slate-500 dark:text-slate-400">per page</span>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" disabled={safePage === 1} onClick={() => setPage((current) => Math.max(1, current - 1))} className="p-1.5 sm:p-2 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-30 transition-all"><ChevronLeft size={14} /></button>
            <span className="text-xs sm:text-sm font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">Page {safePage} / {totalPages}</span>
            <button type="button" disabled={safePage === totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))} className="p-1.5 sm:p-2 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-30 transition-all"><ChevronRight size={14} /></button>
          </div>
        </div>
      </div>
    </div>
  );
}
