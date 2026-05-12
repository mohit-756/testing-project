import { useEffect, useMemo, useState, useId } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight, Calendar, CheckCircle2, Clock, ExternalLink } from "lucide-react";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { candidateApi } from "../services/api";
import { useAnnounce } from "../hooks/useAccessibility";
import {
  formatInterviewDateTimeLocal,
  getGoogleCalendarDateRange,
  resolveInterviewDateTime,
  toDateTimeLocalInputValue,
} from "../utils/formatters";

function routeFromInterviewLink(interviewLink) {
  if (!interviewLink) return "";
  try {
    const url = new URL(interviewLink);
    let path = url.pathname;
    if (url.hash && url.hash.startsWith("#/")) {
      path = url.hash.replace(/^#/, "");
    }
    if (url.search) {
      path = `${path}${url.search}`;
    }
    return path;
  } catch {
    return interviewLink;
  }
}

function todayMinDateTimeLocal() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

export default function CandidateSchedulePage() {
  const [dashboard, setDashboard] = useState(null);
  const [scheduleDate, setScheduleDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [scheduling, setScheduling] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const { announce } = useAnnounce();
  const dateInputId = useId();

  const result = dashboard?.result || null;
  const selectedJd = useMemo(
    () => (dashboard?.available_jds || []).find((jd) => jd.id === dashboard?.selected_jd_id) || null,
    [dashboard],
  );
  const interviewCompleted = Boolean(result?.interview_completed || result?.stage?.key === "interview_completed");
  const finalDecision = result?.final_decision || null;
  const scheduledInterviewDate = resolveInterviewDateTime(result);
  const interviewScheduledLabel = formatInterviewDateTimeLocal(result, "Not scheduled");
  const interviewRoute = routeFromInterviewLink(result?.interview_link);
  const canStartInterview = Boolean(result?.interview_ready && interviewRoute) && !interviewCompleted && !finalDecision;
  const calendarDateRange = getGoogleCalendarDateRange(scheduledInterviewDate);
  const googleCalendarHref = calendarDateRange
    ? `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(
      "Interview - " + (selectedJd?.title || "Quadrant Technologies"),
    )}&dates=${calendarDateRange.startUtc}/${calendarDateRange.endUtc}&details=${encodeURIComponent(
      "Join Link: " + (result?.interview_link || ""),
    )}`
    : "";

  async function loadDashboard() {
    setLoading(true);
    setError("");
    try {
      const response = await candidateApi.dashboard();
      setDashboard(response);
      setScheduleDate(toDateTimeLocalInputValue(response?.result));
      announce("Schedule page loaded successfully");
    } catch (e) {
      setError(e.message);
      announce(`Error: ${e.message}`, "assertive");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  async function handleScheduleInterview() {
    if (!result?.id || !scheduleDate) {
      setError("Pick a date and time first.");
      return;
    }
    setScheduling(true);
    setError("");
    setMessage("");
    try {
      announce("Scheduling interview...");
      const response = await candidateApi.scheduleInterview(result.id, scheduleDate);
      setDashboard((current) => current ? { ...current, result: response.result } : current);
      setScheduleDate(toDateTimeLocalInputValue(response.result));
      setMessage(response.message || "Interview scheduled.");
      announce("Interview scheduled successfully");
    } catch (e) {
      setError(e.message);
      announce(`Error: ${e.message}`, "assertive");
    } finally {
      setScheduling(false);
    }
  }

  if (loading) {
    return (
      <div role="status" aria-label="Loading schedule page" className="center muted">
        <p>Loading calendar...</p>
      </div>
    );
  }

  if (error && !dashboard) {
    return (
      <div role="alert" className="alert error">
        <p>{error}</p>
      </div>
    );
  }

  const notReadyToSchedule = !result?.shortlisted || interviewCompleted || finalDecision;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Schedule Interview"
        subtitle={selectedJd?.title || "Choose your interview date and time"}
        icon={Calendar}
        actions={(
          <Link to="/candidate" className="subtle-button inline-flex items-center gap-2">
            <ArrowLeft size={16} />
            <span>Dashboard</span>
          </Link>
        )}
      />

      {error && (
        <div role="alert" className="alert error">
          <p>{error}</p>
        </div>
      )}
      {message && (
        <div role="status" className="alert success">
          <p>{message}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-8">
        <section aria-labelledby="calendar-heading" className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <div className="p-8 border-b border-slate-100 dark:border-slate-800">
            <p className="text-xs font-black text-blue-600 uppercase tracking-widest mb-2">Interview Calendar</p>
            <h2 id="calendar-heading" className="text-2xl font-bold text-slate-900 dark:text-white">
              Pick Your Interview Slot
            </h2>
            <p className="text-slate-500 dark:text-slate-400 mt-2">
              Select a convenient date and time. A confirmation email and interview link will be sent after scheduling.
            </p>
          </div>

          <div className="p-8 space-y-6">
            {notReadyToSchedule ? (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-800 p-5 text-amber-800 dark:text-amber-300">
                <p className="font-bold">Scheduling is not available for this application.</p>
                <p className="text-sm mt-1">You can schedule only after your resume is shortlisted and before the interview is completed.</p>
              </div>
            ) : (
              <>
                <div className="grid md:grid-cols-[minmax(0,1fr)_auto] gap-4 items-end">
                  <div>
                    <label htmlFor={dateInputId} className="text-xs font-black text-slate-500 dark:text-slate-400 uppercase tracking-wider block mb-2">
                      Date and Time
                    </label>
                    <div className="relative">
                      <Calendar className="absolute left-4 top-1/2 -translate-y-1/2 text-blue-600 w-5 h-5" aria-hidden="true" />
                      <input
                        id={dateInputId}
                        type="datetime-local"
                        min={todayMinDateTimeLocal()}
                        value={scheduleDate}
                        onChange={(e) => setScheduleDate(e.target.value)}
                        disabled={scheduling}
                        className="w-full pl-12 pr-4 py-4 rounded-2xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 outline-none focus:ring-2 focus:ring-blue-500 dark:text-white text-base"
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleScheduleInterview}
                    disabled={scheduling || !scheduleDate}
                    aria-busy={scheduling}
                    className="px-8 py-4 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white font-black transition-all shadow-lg shadow-blue-200 dark:shadow-blue-900/30 disabled:opacity-60"
                  >
                    {scheduling ? "Scheduling..." : scheduledInterviewDate ? "Reschedule" : "Schedule Interview"}
                  </button>
                </div>

                {scheduledInterviewDate && (
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 dark:bg-emerald-900/20 dark:border-emerald-800 p-5">
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="text-emerald-600 dark:text-emerald-400 mt-0.5" size={22} />
                      <div>
                        <p className="font-bold text-emerald-900 dark:text-emerald-200">Interview scheduled</p>
                        <p className="text-sm text-emerald-700 dark:text-emerald-300 mt-1">{interviewScheduledLabel}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-3 mt-5">
                      {googleCalendarHref && (
                        <a
                          href={googleCalendarHref}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white dark:bg-slate-900 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300 text-sm font-bold hover:bg-emerald-50 dark:hover:bg-emerald-900/30"
                        >
                          <ExternalLink size={16} />
                          <span>Add to Google Calendar</span>
                        </a>
                      )}
                      {canStartInterview && (
                        <Link
                          to={interviewRoute}
                          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold"
                        >
                          <span>Start Interview</span>
                          <ArrowRight size={16} />
                        </Link>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </section>

        <aside className="space-y-5">
          <section className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-6">
            <p className="text-xs font-black text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">Application</p>
            <div className="space-y-4">
              <div>
                <p className="text-sm text-slate-500 dark:text-slate-400">Candidate</p>
                <p className="font-bold text-slate-900 dark:text-white">{dashboard?.candidate?.name || "Candidate"}</p>
              </div>
              <div>
                <p className="text-sm text-slate-500 dark:text-slate-400">Role</p>
                <p className="font-bold text-slate-900 dark:text-white">{selectedJd?.title || "Selected role"}</p>
              </div>
              <div>
                <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">Status</p>
                <StatusBadge status={result?.stage || (result?.shortlisted ? "shortlisted" : "applied")} />
              </div>
            </div>
          </section>

          <section className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-6">
            <div className="flex items-center gap-3 mb-3">
              <Clock className="text-blue-600" size={20} />
              <p className="text-sm font-bold text-slate-900 dark:text-white">Before the Interview</p>
            </div>
            <div className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
              <p>Join 5 minutes before your scheduled time.</p>
              <p>Keep your camera, microphone, and internet connection ready.</p>
              <p>You can reschedule from this page before starting the interview.</p>
            </div>
          </section>
        </aside>
      </div>

      <div aria-live="polite" aria-atomic="true" className="sr-announcer" />
    </div>
  );
}
