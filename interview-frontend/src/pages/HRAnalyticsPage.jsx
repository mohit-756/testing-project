import { useEffect, useState, useMemo } from "react";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";
import { hrApi } from "../services/api";
import {
  Users, Briefcase, TrendingUp, TrendingDown, AlertTriangle,
  CheckCircle2, Clock, BarChart3, Target, Zap, Award,
  ChevronDown, ChevronUp, Info,
} from "lucide-react";
import { cn } from "../utils/utils";

// Mini bar chart component
function MiniBar({ value, max, color = "bg-blue-500", label, sublabel }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-bold text-slate-700 dark:text-slate-300 truncate max-w-[140px]">{label}</span>
        <span className="font-black text-slate-900 dark:text-white ml-2">{value}{sublabel}</span>
      </div>
      <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full transition-all duration-700", color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// Score gauge
function ScoreGauge({ score, label, size = "md" }) {
  const color = score >= 75 ? "text-emerald-600" : score >= 55 ? "text-blue-600" : score >= 35 ? "text-amber-500" : "text-red-500";
  const ring = score >= 75 ? "#10b981" : score >= 55 ? "#3b82f6" : score >= 35 ? "#f59e0b" : "#ef4444";
  const r = size === "lg" ? 40 : 28;
  const circ = 2 * Math.PI * r;
  const filled = (score / 100) * circ;
  const sz = size === "lg" ? 100 : 72;
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: sz, height: sz }}>
        <svg width={sz} height={sz} viewBox={`0 0 ${sz} ${sz}`} className="-rotate-90">
          <circle cx={sz/2} cy={sz/2} r={r} fill="none" stroke="currentColor" strokeWidth={size === "lg" ? 8 : 6} className="text-slate-100 dark:text-slate-800" />
          <circle cx={sz/2} cy={sz/2} r={r} fill="none" stroke={ring} strokeWidth={size === "lg" ? 8 : 6} strokeDasharray={`${filled} ${circ}`} strokeLinecap="round" style={{ transition: "stroke-dasharray 0.8s ease" }} />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={cn("font-black", color, size === "lg" ? "text-2xl" : "text-base")}>{score}</span>
        </div>
      </div>
      <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">{label}</span>
    </div>
  );
}

// Insight card with trend indicator
function InsightCard({ title, value, sub, trend, color = "blue", icon: Icon }) {
  const colors = {
    blue: "bg-blue-50 dark:bg-blue-900/20 border-blue-100 dark:border-blue-800/50 text-blue-600 dark:text-blue-400",
    green: "bg-emerald-50 dark:bg-emerald-900/20 border-emerald-100 dark:border-emerald-800/50 text-emerald-600 dark:text-emerald-400",
    amber: "bg-amber-50 dark:bg-amber-900/20 border-amber-100 dark:border-amber-800/50 text-amber-600 dark:text-amber-400",
    red: "bg-red-50 dark:bg-red-900/20 border-red-100 dark:border-red-800/50 text-red-600 dark:text-red-400",
    purple: "bg-purple-50 dark:bg-purple-900/20 border-purple-100 dark:border-purple-800/50 text-purple-600 dark:text-purple-400",
  };
  return (
    <div className={cn("rounded-2xl border p-4 space-y-2", colors[color])}>
      <div className="flex items-center justify-between">
        {Icon && <Icon size={18} />}
        {trend !== undefined && (
          <span className={cn("text-xs font-bold flex items-center gap-0.5", trend >= 0 ? "text-emerald-600" : "text-red-500")}>
            {trend >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
            {Math.abs(trend)}%
          </span>
        )}
      </div>
      <p className="text-2xl font-black">{value}</p>
      <p className="text-xs font-bold opacity-80">{title}</p>
      {sub && <p className="text-[10px] opacity-60">{sub}</p>}
    </div>
  );
}

export default function HRAnalyticsPage() {
  const [dashboard, setDashboard] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [jds, setJds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedJd, setSelectedJd] = useState("all");
  const [expandedRole, setExpandedRole] = useState(null);

  // Load dashboard and candidates when selected JD changes
  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      setError("");
      try {
        const jobId = selectedJd === "all" ? undefined : selectedJd;
        const [dashRes, jdsRes] = await Promise.all([
          hrApi.dashboard(jobId),
          hrApi.listJds()
        ]);
        setDashboard(dashRes);
        setJds(Array.isArray(jdsRes) ? jdsRes : jdsRes?.jds || jdsRes?.jobs || []);

        // Load candidates filtered by JD (or all if "all")
        let allCandidates = [];
        let pageNumber = 1;
        let hasMore = true;
        while (hasMore) {
          const response = await hrApi.listCandidates({ page: pageNumber, job_id: jobId });
          allCandidates = allCandidates.concat(response.candidates || []);
          hasMore = response.has_next;
          pageNumber += 1;
        }
        // Enrich with application detail using batch API
        const candidateUids = allCandidates.map((c) => c.candidate_uid);
        if (candidateUids.length > 0) {
          const batchResponse = await hrApi.batchCandidateDetails(candidateUids);
          const candidatesData = batchResponse.candidates || {};
          const details = candidateUids.map((uid) => candidatesData[uid] || { candidate: {}, applications: [] });
          const enriched = allCandidates.map((c, i) => {
            const detail = details[i];
            const app = detail?.applications?.[0] || {};
            const dc = detail?.candidate || {};
            return {
              ...c,
              jobId: app.job?.id,
              jobTitle: app.job?.title || c.role || "Unknown",
              resumeScore: Number(dc.resumeScore || c.score || 0),
              interviewScore: Number(dc.interviewScore || 0),
              finalAIScore: Number(dc.finalAIScore || c.score || 0),
              skillMatchScore: Number(dc.skillMatchScore || 0),
              interviewStatus: app.status || c.status,
              finalDecision: dc.finalDecision || c.finalDecision,
              explanation: app.explanation || {},
            };
          });
          setCandidates(enriched);
        } else {
          setCandidates([]);
        }
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
loadDashboard();
  }, [selectedJd]);

  // For "all" - use all candidates
  const filtered = candidates;

  const overview = dashboard?.analytics?.overview || {};
  const pipeline = dashboard?.analytics?.pipeline || [];
  const missingSkills = dashboard?.analytics?.top_missing_skills || [];
  const matchedSkills = dashboard?.analytics?.top_matched_skills || [];

  // Compute metrics from filtered candidates when JD is selected
  const computedMetrics = useMemo(() => {
    if (selectedJd === "all") {
      return {
        applications: overview.total_applications || 0,
        activeCandidates: overview.active_candidates || 0,
        avgResumeScore: overview.avg_resume_score || 0,
        shortlistRate: overview.shortlist_rate || 0,
      };
    }
    const filteredCandidates = filtered;
    const total = filteredCandidates.length;
    if (total === 0) {
      return { applications: 0, activeCandidates: 0, avgResumeScore: 0, shortlistRate: 0 };
    }
    const withScore = filteredCandidates.filter((c) => c.resumeScore > 0);
    const avgScore = withScore.length > 0
      ? withScore.reduce((sum, c) => sum + c.resumeScore, 0) / withScore.length
      : 0;
    const shortlisted = filteredCandidates.filter((c) =>
      c.status?.key === "shortlisted" || c.finalDecision?.key === "shortlisted" ||
      c.status?.key === "selected" || c.finalDecision?.key === "selected"
    ).length;
    return {
      applications: total,
      activeCandidates: total,
      avgResumeScore: avgScore,
      shortlistRate: total > 0 ? (shortlisted / total) * 100 : 0,
    };
  }, [filtered, selectedJd, overview]);

  // --- Deep analytics computed from candidates ---

  // Experience tier classification based on resume keywords
  const expTiers = useMemo(() => {
    const tiers = { fresher: 0, junior: 0, mid: 0, senior: 0 };
    filtered.forEach((c) => {
      const exp = c.explanation?.total_experience_detected || 0;
      if (exp === 0) tiers.fresher++;
      else if (exp <= 2) tiers.junior++;
      else if (exp <= 5) tiers.mid++;
      else tiers.senior++;
    });
    return tiers;
  }, [filtered]);

  // Per-role stats
  const roleStats = useMemo(() => {
    const map = {};
    filtered.forEach((c) => {
      const role = c.jobTitle || "Unknown";
      if (!map[role]) map[role] = { count: 0, scores: [], interview: [], shortlisted: 0, completed: 0 };
      map[role].count++;
      if (c.resumeScore > 0) map[role].scores.push(c.resumeScore);
      if (c.interviewScore > 0) map[role].interview.push(c.interviewScore);
      if ((c.finalDecision?.key === "shortlisted" || c.finalDecision?.key === "selected") || (c.status?.key === "shortlisted" || c.status?.key === "selected")) map[role].shortlisted++;
      if ((c.status?.key === "completed" || c.status?.key === "interview_completed") || c.interviewScore > 0) map[role].completed++;
    });
    return Object.entries(map).map(([role, d]) => ({
      role,
      count: d.count,
      avgResume: d.scores.length ? Math.round(d.scores.reduce((a, b) => a + b, 0) / d.scores.length) : 0,
      avgInterview: d.interview.length ? Math.round(d.interview.reduce((a, b) => a + b, 0) / d.interview.length) : 0,
      shortlisted: d.shortlisted,
      completed: d.completed,
      conversionRate: d.count > 0 ? Math.round((d.shortlisted / d.count) * 100) : 0,
    })).sort((a, b) => b.count - a.count);
  }, [filtered]);

  // Interview performance analysis — what's going wrong?
  const perfAnalysis = useMemo(() => {
    const completedCandidates = filtered.filter((c) => (c.status?.key === "completed" || c.status?.key === "interview_completed") || c.interviewScore > 0);
    if (!completedCandidates.length) return null;
    const avgResume = completedCandidates.reduce((s, c) => s + c.resumeScore, 0) / completedCandidates.length;
    const avgInterview = completedCandidates.reduce((s, c) => s + c.interviewScore, 0) / completedCandidates.length;
    const dropOff = avgResume - avgInterview;
    const highResumeLowInterview = completedCandidates.filter((c) => c.resumeScore > 65 && c.interviewScore < 50).length;
    const lowResumeHighInterview = completedCandidates.filter((c) => c.resumeScore < 50 && c.interviewScore > 65).length;
    return {
      avgResume: Math.round(avgResume),
      avgInterview: Math.round(avgInterview),
      dropOff: Math.round(dropOff),
      highResumeLowInterview,
      lowResumeHighInterview,
      total: completedCandidates.length,
    };
  }, [filtered]);

  // Skill gap depth — how many candidates are missing key skills
  const skillGapSeverity = useMemo(() => {
    const totalMissing = filtered.reduce((s, c) => s + (c.explanation?.missing_skills?.length || 0), 0);
    const totalMatched = filtered.reduce((s, c) => s + (c.explanation?.matched_skills?.length || 0), 0);
    return filtered.length > 0 ? {
      avgMissing: Math.round(totalMissing / filtered.length * 10) / 10,
      avgMatched: Math.round(totalMatched / filtered.length * 10) / 10,
    } : { avgMissing: 0, avgMatched: 0 };
  }, [filtered]);

  if (loading) return <p className="center muted">Loading analytics...</p>;
  if (error && !dashboard) return <p className="alert error">{error}</p>;

  const maxPipelineCount = Math.max(...pipeline.map((p) => p.count), 1);

  return (
    <div className="space-y-8 pb-12">
      {error ? <p className="alert error">{error}</p> : null}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 page-enter">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white font-display">HR Analytics</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Recruitment health, candidate profile breakdown, and interview performance signals.</p>
        </div>
        {/* JD Filter */}
        <div className="flex items-center gap-3">
          <Briefcase size={16} className="text-slate-400" />
          <select
            value={selectedJd}
            onChange={(e) => setSelectedJd(e.target.value)}
            className="px-4 py-2.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm font-bold dark:text-white shadow-sm"
          >
            <option value="all">All JDs</option>
            {jds.map((jd) => <option key={jd.id} value={String(jd.id)}>{jd.title}</option>)}
          </select>
        </div>
      </div>

      {/* Top metric cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard title="Total Jobs" value={overview.total_jobs || 0} color="blue" />
        <MetricCard title="Applications" value={selectedJd === "all" ? (filtered.length || overview.total_applications || 0) : computedMetrics.applications} color="purple" />
        <MetricCard title="Active Candidates" value={selectedJd === "all" ? (overview.active_candidates || 0) : computedMetrics.activeCandidates} color="green" />
        <MetricCard title="Avg Resume Score" value={`${Math.round(selectedJd === "all" ? (overview.avg_resume_score || 0) : computedMetrics.avgResumeScore)}%`} color="yellow" />
        <MetricCard title="Shortlist Rate" value={`${Math.round(selectedJd === "all" ? (overview.shortlist_rate || 0) : computedMetrics.shortlistRate)}%`} color="green" />
      </div>

      {/* 3-column main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Pipeline funnel */}
        <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 space-y-4 chart-card-accent blue">
          <div className="flex items-center gap-2 mb-2">
            <Target size={18} className="text-blue-600" />
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Pipeline Funnel</h3>
          </div>
          <div className="space-y-3">
            {pipeline.map((item) => (
              <MiniBar
                key={item.key}
                label={item.label}
                value={item.count}
                max={maxPipelineCount}
                sublabel=""
                color={
                  item.key === "shortlisted" || item.key === "selected" ? "bg-emerald-500" :
                  item.key === "rejected" ? "bg-red-400" :
                  item.key === "completed" ? "bg-purple-500" :
                  item.key === "interview_scheduled" ? "bg-blue-500" : "bg-slate-300"
                }
              />
            ))}
          </div>
          {pipeline.length === 0 && <p className="text-sm text-slate-500">No pipeline data yet.</p>}
        </div>

        {/* Candidate profile — experience tier breakdown */}
        <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 space-y-4 chart-card-accent purple">
          <div className="flex items-center gap-2 mb-2">
            <Users size={18} className="text-purple-600" />
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Who Applied</h3>
            <span className="text-xs text-slate-400 font-medium">by experience</span>
          </div>
          <div className="space-y-3">
            {[
              { label: "Fresher (0 yrs)", value: expTiers.fresher, color: "bg-violet-400" },
              { label: "Junior (1–2 yrs)", value: expTiers.junior, color: "bg-blue-500" },
              { label: "Mid-Level (3–5 yrs)", value: expTiers.mid, color: "bg-emerald-500" },
              { label: "Senior (5+ yrs)", value: expTiers.senior, color: "bg-amber-500" },
            ].map((tier) => (
              <MiniBar key={tier.label} label={tier.label} value={tier.value} max={Math.max(...Object.values(expTiers), 1)} color={tier.color} sublabel=" candidates" />
            ))}
          </div>
          <div className="pt-3 border-t border-slate-100 dark:border-slate-800">
            <p className="text-xs text-slate-500">Based on experience years detected in resume text</p>
          </div>
        </div>

        {/* Skill insights */}
        <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 space-y-4 chart-card-accent yellow">
          <div className="flex items-center gap-2 mb-2">
            <Zap size={18} className="text-amber-500" />
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Skill Health</h3>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-emerald-50 dark:bg-emerald-900/20 rounded-2xl p-3 border border-emerald-100 dark:border-emerald-800/50">
              <p className="text-xs font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider">Avg Matched</p>
              <p className="text-2xl font-black text-emerald-700 dark:text-emerald-400 mt-1">{skillGapSeverity.avgMatched}</p>
              <p className="text-[10px] text-emerald-600 opacity-70">skills per candidate</p>
            </div>
            <div className="bg-red-50 dark:bg-red-900/20 rounded-2xl p-3 border border-red-100 dark:border-red-800/50">
              <p className="text-xs font-bold text-red-700 dark:text-red-400 uppercase tracking-wider">Avg Missing</p>
              <p className="text-2xl font-black text-red-700 dark:text-red-400 mt-1">{skillGapSeverity.avgMissing}</p>
              <p className="text-[10px] text-red-600 opacity-70">skills per candidate</p>
            </div>
          </div>
          <div className="space-y-2">
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Top Missing Skills</p>
            {missingSkills.slice(0, 4).map((item) => (
              <div key={item.skill} className="flex items-center justify-between text-sm">
                <span className="font-medium text-slate-700 dark:text-slate-300 capitalize">{item.skill}</span>
                <span className="text-xs font-bold text-red-500 bg-red-50 dark:bg-red-900/20 px-2 py-0.5 rounded-full">{item.count} missing</span>
              </div>
            ))}
            {missingSkills.length === 0 && <p className="text-sm text-slate-500">No gap data yet.</p>}
          </div>
          <div className="space-y-2">
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Top Matched Skills</p>
            {matchedSkills.slice(0, 3).map((item) => (
              <div key={item.skill} className="flex items-center justify-between text-sm">
                <span className="font-medium text-slate-700 dark:text-slate-300 capitalize">{item.skill}</span>
                <span className="text-xs font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 px-2 py-0.5 rounded-full">{item.count} matched</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Interview Performance Diagnostics — NEW KEY SECTION */}
      {perfAnalysis && (
        <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-amber-100 dark:bg-amber-900/30 rounded-2xl flex items-center justify-center">
              <AlertTriangle size={20} className="text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-slate-900 dark:text-white">Interview Performance Diagnostics</h3>
              <p className="text-sm text-slate-500">What's going right — and what needs attention</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-5 text-center space-y-1">
              <ScoreGauge score={perfAnalysis.avgResume} label="Avg Resume" />
            </div>
            <div className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-5 text-center space-y-1">
              <ScoreGauge score={perfAnalysis.avgInterview} label="Avg Interview" />
            </div>
            <InsightCard
              icon={perfAnalysis.dropOff > 15 ? TrendingDown : TrendingUp}
              title="Resume → Interview Drop"
              value={`${Math.abs(perfAnalysis.dropOff)}pts`}
              sub={perfAnalysis.dropOff > 15 ? "⚠ Candidates struggle in live interviews vs paper" : "Performance is consistent across stages"}
              color={perfAnalysis.dropOff > 15 ? "amber" : "green"}
            />
            <InsightCard
              icon={AlertTriangle}
              title="Strong Resume, Weak Interview"
              value={perfAnalysis.highResumeLowInterview}
              sub="Candidates who looked good on paper but underperformed live"
              color={perfAnalysis.highResumeLowInterview > 2 ? "red" : "blue"}
            />
          </div>

          {/* Diagnosis signals */}
          <div className="space-y-3">
            <p className="text-xs font-black text-slate-400 uppercase tracking-widest">What This Signals</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {perfAnalysis.dropOff > 20 && (
                <div className="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-900/50 rounded-2xl">
                  <AlertTriangle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-bold text-red-700 dark:text-red-400">Large Resume-Interview Gap ({perfAnalysis.dropOff}pts)</p>
                    <p className="text-xs text-red-600 dark:text-red-400/80 mt-0.5">Candidates may be embellishing resumes, or interview questions don't align with job requirements. Review question quality.</p>
                  </div>
                </div>
              )}
              {perfAnalysis.dropOff > 0 && perfAnalysis.dropOff <= 20 && (
                <div className="flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-900/50 rounded-2xl">
                  <Info size={16} className="text-amber-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-bold text-amber-700 dark:text-amber-400">Moderate Drop-off ({perfAnalysis.dropOff}pts)</p>
                    <p className="text-xs text-amber-600 dark:text-amber-400/80 mt-0.5">Normal variation. Some candidates may need coaching on live interview communication skills.</p>
                  </div>
                </div>
              )}
              {perfAnalysis.highResumeLowInterview > 2 && (
                <div className="flex items-start gap-3 p-4 bg-purple-50 dark:bg-purple-900/20 border border-purple-100 dark:border-purple-900/50 rounded-2xl">
                  <Users size={16} className="text-purple-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-bold text-purple-700 dark:text-purple-400">{perfAnalysis.highResumeLowInterview} candidates underperformed</p>
                    <p className="text-xs text-purple-600 dark:text-purple-400/80 mt-0.5">High resume score but low interview score. Could indicate question difficulty mismatch or candidate anxiety.</p>
                  </div>
                </div>
              )}
              {perfAnalysis.lowResumeHighInterview > 0 && (
                <div className="flex items-start gap-3 p-4 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-900/50 rounded-2xl">
                  <Award size={16} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-bold text-emerald-700 dark:text-emerald-400">{perfAnalysis.lowResumeHighInterview} hidden gems found</p>
                    <p className="text-xs text-emerald-600 dark:text-emerald-400/80 mt-0.5">Weak resumes but strong interview performance. Consider reviewing these candidates — skills may be underrepresented on paper.</p>
                  </div>
                </div>
              )}
              {perfAnalysis.total > 0 && perfAnalysis.dropOff <= 0 && (
                <div className="flex items-start gap-3 p-4 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-900/50 rounded-2xl">
                  <CheckCircle2 size={16} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-bold text-emerald-700 dark:text-emerald-400">Interview performance is strong</p>
                    <p className="text-xs text-emerald-600 dark:text-emerald-400/80 mt-0.5">Candidates are performing at or above their resume level in live interviews.</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Per-Role Breakdown — NEW */}
      {roleStats.length > 0 && (
        <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-8">
          <div className="flex items-center gap-3 mb-6">
            <Briefcase size={20} className="text-blue-600" />
            <h3 className="text-xl font-bold text-slate-900 dark:text-white">Performance by Role</h3>
            <span className="text-sm text-slate-400">— how each JD is performing</span>
          </div>
          <div className="space-y-3">
            {roleStats.map((role) => (
              <div key={role.role} className="border border-slate-100 dark:border-slate-800 rounded-2xl overflow-hidden">
                <button
                  type="button"
                  onClick={() => setExpandedRole(expandedRole === role.role ? null : role.role)}
                  className="w-full flex items-center justify-between p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-all"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900/30 rounded-xl flex items-center justify-center text-blue-600 font-black text-sm">{role.count}</div>
                    <div className="text-left">
                      <p className="font-bold text-slate-900 dark:text-white">{role.role}</p>
                      <p className="text-xs text-slate-500">{role.completed} completed interviews · {role.shortlisted} shortlisted</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="hidden sm:flex items-center gap-6">
                      <div className="text-center">
                        <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">Resume</p>
                        <p className={cn("text-lg font-black", role.avgResume >= 65 ? "text-emerald-600" : "text-amber-500")}>{role.avgResume}%</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">Interview</p>
                        <p className={cn("text-lg font-black", role.avgInterview >= 65 ? "text-emerald-600" : role.avgInterview > 0 ? "text-amber-500" : "text-slate-300")}>{role.avgInterview > 0 ? `${role.avgInterview}%` : "—"}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">Conversion</p>
                        <p className={cn("text-lg font-black", role.conversionRate >= 50 ? "text-emerald-600" : "text-red-500")}>{role.conversionRate}%</p>
                      </div>
                    </div>
                    {expandedRole === role.role ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
                  </div>
                </button>

                {expandedRole === role.role && (
                  <div className="px-4 pb-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/20">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4">
                      <div className="bg-white dark:bg-slate-900 rounded-xl p-3 border border-slate-100 dark:border-slate-800">
                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Applicants</p>
                        <p className="text-2xl font-black text-slate-900 dark:text-white mt-1">{role.count}</p>
                      </div>
                      <div className="bg-white dark:bg-slate-900 rounded-xl p-3 border border-slate-100 dark:border-slate-800">
                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Avg Resume</p>
                        <p className={cn("text-2xl font-black mt-1", role.avgResume >= 65 ? "text-emerald-600" : "text-amber-500")}>{role.avgResume}%</p>
                      </div>
                      <div className="bg-white dark:bg-slate-900 rounded-xl p-3 border border-slate-100 dark:border-slate-800">
                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Avg Interview</p>
                        <p className={cn("text-2xl font-black mt-1", role.avgInterview >= 65 ? "text-emerald-600" : role.avgInterview > 0 ? "text-amber-500" : "text-slate-300")}>{role.avgInterview > 0 ? `${role.avgInterview}%` : "—"}</p>
                      </div>
                      <div className="bg-white dark:bg-slate-900 rounded-xl p-3 border border-slate-100 dark:border-slate-800">
                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Shortlisted</p>
                        <p className="text-2xl font-black text-emerald-600 mt-1">{role.shortlisted}</p>
                      </div>
                    </div>
                    {role.avgResume > 0 && role.avgInterview > 0 && role.avgResume - role.avgInterview > 15 && (
                      <div className="mt-3 flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded-xl px-3 py-2 border border-amber-100 dark:border-amber-900/50">
                        <AlertTriangle size={13} />
                        <span>Large resume-to-interview gap ({role.avgResume - role.avgInterview}pts) for this role. Check if questions match the JD expectations.</span>
                      </div>
                    )}
                    {role.conversionRate < 30 && role.count >= 3 && (
                      <div className="mt-3 flex items-center gap-2 text-xs text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-xl px-3 py-2 border border-red-100 dark:border-red-900/50">
                        <TrendingDown size={13} />
                        <span>Low shortlist rate ({role.conversionRate}%) for this role. Consider adjusting the qualify score threshold or screening criteria.</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Current Job Focus */}
      {dashboard?.jobs?.[0] && (
        <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-8">
          <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
            <Briefcase className="text-blue-600" size={22} />Current Job Focus
          </h3>
          {(() => {
            const topJob = dashboard.jobs[0];
            return (
              <div className="grid md:grid-cols-2 gap-8">
                <div>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white">{topJob.jd_title}</p>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-3">Cutoff {topJob.cutoff_score}% | Questions {topJob.question_count}</p>
                </div>
                <div className="space-y-3">
                  {Object.entries(topJob.skill_scores || {}).slice(0, 6).map(([skill, weight]) => (
                    <div key={skill} className="flex items-center justify-between">
                      <span className="text-sm text-slate-600 dark:text-slate-300 capitalize">{skill}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-24 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                          <div className="h-full bg-blue-500 rounded-full" style={{ width: `${(Number(weight) / 10) * 100}%` }} />
                        </div>
                        <span className="text-xs font-bold text-slate-900 dark:text-white w-4">{weight}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
