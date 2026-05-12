import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Video } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { hrApi } from "../services/api";
import ProctoringTimeline from "../components/ProctoringTimeline";

export default function HRProctoringPage() {
  const { sessionId } = useParams();
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState("");

  const loadTimeline = useCallback(async () => {
    if (!sessionId) { setError("No session ID provided"); setLoading(false); return; }
    setLoading(true); setError("");
    try {
      const data = await hrApi.proctoringTimeline(sessionId);
      setTimeline(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => { loadTimeline(); }, [loadTimeline]);

  if (loading) return (
    <div className="space-y-4">
      <Link to="/hr/interviews" className="flex items-center gap-2 text-slate-500 hover:text-blue-500 transition-colors font-medium">
        <ArrowLeft size={18} /><span>Back to Interviews</span>
      </Link>
      <p className="text-slate-500 text-sm">Loading proctoring data…</p>
    </div>
  );

  if (error && !timeline) return (
    <div className="space-y-4">
      <Link to="/hr/interviews" className="flex items-center gap-2 text-slate-500 hover:text-blue-500 transition-colors font-medium">
        <ArrowLeft size={18} /><span>Back to Interviews</span>
      </Link>
      <p className="alert error">{error}</p>
    </div>
  );

  const events      = timeline?.timeline || [];
  const session     = timeline?.session  || {};

  return (
    <div className="space-y-8 pb-12">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <Link to="/hr/interviews" className="flex items-center gap-2 text-slate-500 hover:text-blue-500 transition-colors font-medium">
          <ArrowLeft size={18} /><span>Back to Interviews</span>
        </Link>
      </div>

      {/* Session header */}
      <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        <div className="h-28 bg-gradient-to-r from-orange-600 to-red-700" />
        <div className="px-8 pb-8">
          <div className="relative -mt-10 flex flex-col md:flex-row md:items-end md:gap-6">
            <div className="w-20 h-20 rounded-2xl border-4 border-white dark:border-slate-900 bg-slate-100 dark:bg-slate-800 shadow-lg flex items-center justify-center">
              <Video size={32} className="text-slate-400" />
            </div>
            <div className="mt-3 md:mt-0">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                Proctoring — Session #{sessionId}
              </h1>
              <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
          <div className="flex items-center space-x-4 mb-4">
            <a href="https://d2awu07vokgf4.cloudfront.net/#/hr/interviews/165" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700">
              View Proctoring Images
            </a>
          </div>
                Candidate: {session.candidate_name || "—"} ·
                Status: {session.status || "—"} ·
                Warnings: {session.warning_count || 0} ·
                Baseline: {session.baseline_captured ? "✓ Captured" : "✗ Not captured"}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-8">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">Event Timeline</h2>
        <ProctoringTimeline events={events} sessionInfo={session} />
      </div>
    </div>
  );
}
