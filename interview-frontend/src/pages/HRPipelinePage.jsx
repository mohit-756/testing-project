import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Eye, RefreshCw, ThumbsDown, ThumbsUp, Users, Calendar, CheckCircle, XCircle, Filter, Search } from "lucide-react";
import ScoreBadge from "../components/ScoreBadge";
import { hrApi } from "../services/api";
import { ATS_STAGE_DEFINITIONS as PIPELINE_STAGES, normalizeStageKey } from "../utils/stages";

const STAGE_ICONS = {
  applied: Users,
  screening: Filter,
  shortlisted: ThumbsUp,
  interview_scheduled: Calendar,
  interview_completed: CheckCircle,
  selected: CheckCircle,
  rejected: XCircle,
};

const STAGE_COLORS = {
  applied: { bg: "bg-slate-100 dark:bg-slate-800", border: "border-slate-300 dark:border-slate-700", text: "text-slate-600 dark:text-slate-300", pill: "bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300" },
  screening: { bg: "bg-blue-50 dark:bg-blue-900/20", border: "border-blue-300 dark:border-blue-700", text: "text-blue-600 dark:text-blue-400", pill: "bg-blue-200 dark:bg-blue-800 text-blue-600 dark:text-blue-300" },
  shortlisted: { bg: "bg-emerald-50 dark:bg-emerald-900/20", border: "border-emerald-300 dark:border-emerald-700", text: "text-emerald-600 dark:text-emerald-400", pill: "bg-emerald-200 dark:bg-emerald-800 text-emerald-600 dark:text-emerald-300" },
  interview_scheduled: { bg: "bg-amber-50 dark:bg-amber-900/20", border: "border-amber-300 dark:border-amber-700", text: "text-amber-600 dark:text-amber-400", pill: "bg-amber-200 dark:bg-amber-800 text-amber-600 dark:text-amber-300" },
  interview_completed: { bg: "bg-blue-50 dark:bg-blue-900/20", border: "border-blue-300 dark:border-blue-700", text: "text-blue-600 dark:text-blue-400", pill: "bg-blue-200 dark:bg-blue-800 text-blue-600 dark:text-blue-300" },
  selected: { bg: "bg-purple-50 dark:bg-purple-900/20", border: "border-purple-300 dark:border-purple-700", text: "text-purple-600 dark:text-purple-400", pill: "bg-purple-200 dark:bg-purple-800 text-purple-600 dark:text-purple-300" },
  rejected: { bg: "bg-red-50 dark:bg-red-900/20", border: "border-red-300 dark:border-red-700", text: "text-red-600 dark:text-red-400", pill: "bg-red-200 dark:bg-red-800 text-red-600 dark:text-red-300" },
};

function getCandidateJdId(candidate) {
  const jdId = candidate?.assignedJd?.id ?? candidate?.job?.id ?? null;
  return jdId == null ? "" : String(jdId);
}

function CandidateRow({ candidate, onQuickAction, quickActionLoadingId }) {
  const currentStage = normalizeStageKey(candidate?.status?.key);
  const isUpdating = quickActionLoadingId === candidate?.result_id;
  const stageColors = STAGE_COLORS[currentStage] || STAGE_COLORS.applied;

  return (
    <tr className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
      <td className="px-4 py-4">
        <div>
          <p className="font-semibold text-base text-slate-900 dark:text-white">{candidate?.name || "Unnamed"}</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">{candidate?.candidate_uid || "No ID"}</p>
        </div>
      </td>
      <td className="px-4 py-4">
        <ScoreBadge score={candidate?.finalAIScore || 0} />
      </td>
      <td className="px-4 py-4">
        <span className={`px-3 py-1.5 rounded-full text-sm font-semibold border ${stageColors.bg} ${stageColors.border} ${stageColors.text}`}>
          {candidate?.status?.label || currentStage}
        </span>
      </td>
      <td className="px-4 py-4 text-base text-slate-600 dark:text-slate-300">
        {candidate?.assignedJd?.title || candidate?.role || "—"}
      </td>
      <td className="px-4 py-4 text-base text-slate-500 dark:text-slate-400">
        {candidate?.created_at ? new Date(candidate.created_at).toLocaleDateString() : "—"}
      </td>
      <td className="px-4 py-4">
        <div className="flex items-center gap-2">
          <Link to={`/hr/candidates/${candidate?.candidate_uid}`} className="p-2.5 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 hover:border-blue-300 dark:hover:border-blue-500 transition-all" title="View Details">
            <Eye size={18} />
          </Link>
          <button type="button" disabled={isUpdating || currentStage === "shortlisted"} onClick={(event) => { event.stopPropagation(); onQuickAction(candidate, "shortlisted"); }} className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 transition-all disabled:opacity-50" title="Shortlist">
            <ThumbsUp size={18} />
          </button>
          <button type="button" disabled={isUpdating || currentStage === "rejected"} onClick={(event) => { event.stopPropagation(); onQuickAction(candidate, "rejected"); }} className="p-2.5 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/40 transition-all disabled:opacity-50" title="Reject">
            <ThumbsDown size={18} />
          </button>
        </div>
      </td>
    </tr>
  );
}

export default function HRPipelinePage() {
  const [candidates, setCandidates] = useState([]);
  const [availableJds, setAvailableJds] = useState([]);
  const [selectedJdId, setSelectedJdId] = useState("all");
  const [selectedStage, setSelectedStage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatingResultId, setUpdatingResultId] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");

  async function loadCandidates() {
    setLoading(true);
    setError("");
    try {
      let page = 1;
      let hasMore = true;
      let allCandidates = [];
      while (hasMore) {
        const response = await hrApi.listCandidates({ page, sort: "highest_score" });
        allCandidates = allCandidates.concat(response?.candidates || []);
        hasMore = Boolean(response?.has_next);
        page += 1;
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
      setCandidates(Array.isArray(allCandidates) ? allCandidates.filter((item) => item?.result_id) : []);
    } catch (loadError) {
      setError(loadError.message || "Failed to load pipeline.");
      setCandidates([]);
      setAvailableJds([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCandidates();
  }, []);

  const filteredCandidates = useMemo(() => {
    let result = candidates;
    if (selectedJdId !== "all") {
      result = result.filter((candidate) => getCandidateJdId(candidate) === String(selectedJdId));
    }
    if (selectedStage) {
      result = result.filter((candidate) => normalizeStageKey(candidate?.status?.key) === selectedStage);
    }
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter((candidate) =>
        candidate?.name?.toLowerCase().includes(query) ||
        candidate?.candidate_uid?.toLowerCase().includes(query) ||
        candidate?.assignedJd?.title?.toLowerCase().includes(query)
      );
    }
    return result;
  }, [candidates, selectedJdId, selectedStage, searchQuery]);

  const groupedCandidates = useMemo(() => {
    const groups = Object.fromEntries(PIPELINE_STAGES.map((stage) => [stage.key, []]));
    for (const candidate of filteredCandidates) {
      const stageKey = normalizeStageKey(candidate?.status?.key);
      if (groups[stageKey]) {
        groups[stageKey].push(candidate);
      }
    }
    return groups;
  }, [filteredCandidates]);

  const totalCandidates = filteredCandidates.length;
  const stageCounts = useMemo(() => {
    const counts = {};
    PIPELINE_STAGES.forEach((stage) => { counts[stage.key] = 0; });
    filteredCandidates.forEach((candidate) => {
      const key = normalizeStageKey(candidate?.status?.key);
      counts[key] = (counts[key] || 0) + 1;
    });
    return counts;
  }, [filteredCandidates]);

  function updateCandidateStageLocally(candidateId, nextStage) {
    const normalizedStage = normalizeStageKey(nextStage);
    setCandidates((current) => current.map((item) => item.result_id === candidateId ? {
      ...item,
      status: {
        key: normalizedStage,
        label: PIPELINE_STAGES.find((stage) => stage.key === normalizedStage)?.label || normalizedStage,
        tone: PIPELINE_STAGES.find((stage) => stage.key === normalizedStage)?.tone || "secondary",
      },
    } : item));
  }

  async function persistStageChange(candidate, nextStage, notePrefix = "Updated from HR pipeline") {
    const normalizedStage = normalizeStageKey(nextStage);
    const currentStage = normalizeStageKey(candidate?.status?.key);
    if (!candidate?.result_id || currentStage === normalizedStage) return;

    const previousCandidates = candidates;
    updateCandidateStageLocally(candidate.result_id, normalizedStage);
    setUpdatingResultId(candidate.result_id);
    setError("");

    try {
      await hrApi.updateCandidateStage(candidate.result_id, { stage: normalizedStage, note: `${notePrefix} to ${normalizedStage}.` });
      await loadCandidates();
    } catch (updateError) {
      setCandidates(previousCandidates);
      setError(updateError.message || "Failed to update candidate stage.");
    } finally {
      setUpdatingResultId(null);
    }
  }

  async function handleQuickAction(candidate, nextStage) {
    await persistStageChange(candidate, nextStage, "Updated from HR pipeline quick action");
  }

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <div className="text-center">
        <div className="w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        <p className="text-base text-slate-500 dark:text-slate-400">Loading pipeline...</p>
      </div>
    </div>
  );

  return (
    <div className="max-w-[1400px] mx-auto space-y-5 pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">HR Pipeline</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Manage candidates through hiring stages</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {/* Search */}
          <div className="relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input type="text" placeholder="Search..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="pl-10 pr-4 py-2.5 text-base bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-300 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 w-48" />
          </div>
          {/* Stage Filter Clear */}
          {selectedStage && (
            <button type="button" onClick={() => setSelectedStage(null)} className="px-4 py-2.5 text-base bg-blue-100 dark:bg-blue-900/30 border border-blue-300 dark:border-blue-700 text-blue-600 dark:text-blue-400 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-all">
              Clear Filter
            </button>
          )}
          {/* JD Filter */}
          <select value={selectedJdId} onChange={(event) => setSelectedJdId(event.target.value)} className="px-4 py-2.5 text-base bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="all">All Jobs</option>
            {availableJds.map((jd) => <option key={jd.id} value={jd.id}>{jd.title}</option>)}
          </select>
          <Link to="/hr/candidates" className="px-4 py-2.5 text-base bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-all flex items-center gap-2">
            <Eye size={16} /> List
          </Link>
          <button type="button" onClick={loadCandidates} className="px-4 py-2.5 text-base bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-all" title="Refresh">
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* Stage Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        {PIPELINE_STAGES.map((stage) => {
          const IconComponent = STAGE_ICONS[stage.key] || Users;
          const count = stageCounts[stage.key] || 0;
          const colors = STAGE_COLORS[stage.key] || STAGE_COLORS.applied;
          const isSelected = selectedStage === stage.key;
          return (
            <button
              key={stage.key}
              type="button"
              onClick={() => setSelectedStage(isSelected ? null : stage.key)}
              className={`p-4 rounded-xl border flex items-center gap-3 text-left transition-all cursor-pointer hover:scale-[1.02] ${
                isSelected
                  ? `${colors.bg} ${colors.border} ring-2 ring-offset-2 ring-blue-500`
                  : `${colors.bg} ${colors.border} opacity-100 hover:opacity-80`
              }`}
            >
              <IconComponent size={22} className={colors.text} />
              <div>
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400">{stage.label}</p>
                <p className={`text-xl font-bold ${colors.text}`}>{count}</p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Error */}
      {error && <div className="p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 text-base">{error}</div>}
      {updatingResultId && <p className="text-base text-slate-500 dark:text-slate-400">Updating...</p>}

      {/* Pipeline Stages */}
      {!totalCandidates ? (
        <div className="text-center py-16 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
          <Users size={40} className="mx-auto text-slate-300 dark:text-slate-600 mb-4" />
          <p className="text-lg font-medium text-slate-900 dark:text-white">{selectedJdId === "all" ? "No candidates yet" : "No candidates for this job"}</p>
          <p className="text-base text-slate-500 dark:text-slate-400 mt-1">Candidates will appear once applications come in.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {PIPELINE_STAGES.map((stage) => {
            const stageCandidates = groupedCandidates[stage.key] || [];
            const IconComponent = STAGE_ICONS[stage.key] || Users;
            const colors = STAGE_COLORS[stage.key] || STAGE_COLORS.applied;
            const count = stageCounts[stage.key] || 0;

            if (count === 0) return null;

            return (
              <div key={stage.key} className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                <div className="px-5 py-4 flex items-center justify-between border-b border-slate-100 dark:border-slate-800">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${colors.bg}`}>
                      <IconComponent size={18} className={colors.text} />
                    </div>
                    <span className={`text-lg font-semibold ${colors.text}`}>{stage.label}</span>
                    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${colors.pill}`}>{count}</span>
                  </div>
                </div>
                <div className="overflow-x-auto max-h-[400px]">
                  <table className="w-full min-w-[700px]">
                    <thead className="bg-slate-50 dark:bg-slate-800/50 sticky top-0">
                      <tr>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide">Candidate</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide">Score</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide">Stage</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide">Job</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide">Applied</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stageCandidates.slice(0, 5).map((candidate) => (
                        <CandidateRow key={candidate.result_id} candidate={candidate} onQuickAction={handleQuickAction} quickActionLoadingId={updatingResultId} />
                      ))}
                    </tbody>
                  </table>
                </div>
                {stageCandidates.length > 5 && (
                  <div className="text-center py-3 text-sm text-slate-500 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800">
                    + {stageCandidates.length - 5} more candidates in this stage
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}