import { useEffect, useMemo, useState, useRef } from "react";
import { ArrowRight, Upload, Check, X, Clock, Briefcase, Calendar } from "lucide-react";
import { Link } from "react-router-dom";
import StatusBadge from "../components/StatusBadge";
import StepChecklist from "../components/StepChecklist";
import { candidateApi } from "../services/api";
import HelpSupportButton from "../components/HelpSupportButton";
import { useAnnounce } from "../hooks/useAccessibility";
import { resolveInterviewDateTime } from "../utils/formatters";

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
  } catch (e) {
    return interviewLink;
  }
}

export default function CandidateDashboardPage() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [applications, setApplications] = useState([]);
  const fileInputRef = useRef(null);

  const { announce } = useAnnounce();

  const hasResume = Boolean(dashboard?.candidate?.resume_path);
  const selectedJdId = dashboard?.selected_jd_id;
  
  const selectedJd = useMemo(() => 
    (dashboard?.available_jds || []).find((jd) => jd.id === selectedJdId) || null, 
    [dashboard, selectedJdId]
  );
  
  const result = dashboard?.result || null;
  const interviewRoute = routeFromInterviewLink(result?.interview_link);
  const interviewReady = Boolean(result?.interview_ready && interviewRoute);
  const interviewCompleted = Boolean(result?.interview_completed || result?.stage?.key === "interview_completed");
  const finalDecision = result?.final_decision || null;
  const canScheduleInterview = Boolean(result?.shortlisted) && !interviewCompleted && !finalDecision;
  const showStartInterview = interviewReady && !interviewCompleted && !finalDecision;
  const interviewSessionStatus = String(result?.interview_session_status || "").toLowerCase();
  const scheduledInterviewDate = resolveInterviewDateTime(result);

  const isSelected = result?.shortlisted === true;
  const isRejected = result?.stage?.key === "rejected" || finalDecision === "rejected";
  const isApplied = selectedJdId != null && hasResume;
  const isUnderReview = isApplied && !isSelected && !isRejected && !result?.stage?.key;

  async function loadDashboard(jobId) {
    setLoading(true);
    setError("");
    try {
      const currentResults = dashboard?.results || {};
      const response = await candidateApi.dashboard(jobId);
      setDashboard({
        ...response,
        results: { ...currentResults, [jobId]: response.result }
      });
      setMessage("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
    loadApplications();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadApplications() {
    try {
      const response = await candidateApi.allResults();
      setApplications(response.applications || []);
    } catch (err) {
      console.log("Failed to load applications", err);
    }
  }

  async function handleApply(jdId, jdTitle) {
    if (!hasResume) {
      setError("Please upload your resume first before applying");
      announce("Please upload your resume first", "assertive");
      return;
    }
    announce(`Applying for: ${jdTitle}`);
    try {
      const response = await candidateApi.selectJd(jdId);
      setMessage(`Successfully applied for ${jdTitle}`);
      announce(`Successfully applied for ${jdTitle}`);
      
      if (response.result) {
        setDashboard(prev => ({
          ...prev,
          results: { ...(prev.results || {}), [jdId]: response.result }
        }));
      }
      
      await loadDashboard(jdId);
    } catch (err) {
      setError(err.message);
      announce(`Error: ${err.message}`, "assertive");
    }
  }

  async function handleRefreshStatus() {
    try {
      const response = await candidateApi.dashboard(selectedJdId);
      setDashboard(response);
      setMessage("Status refreshed");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleApplyToAll() {
    if (!hasResume) {
      setError("Please upload your resume first before applying");
      announce("Please upload your resume first", "assertive");
      return;
    }
    const jds = dashboard?.available_jds || [];
    if (jds.length === 0) return;
    
    announce(`Applying to all ${jds.length} positions...`);
    try {
      for (const jd of jds) {
        if (selectedJdId !== jd.id) {
          await candidateApi.selectJd(jd.id);
        }
      }
      await loadDashboard(jds[0].id);
      setMessage(`Applied to all ${jds.length} positions`);
      announce(`Applied to all positions`);
    } catch (err) {
      setError(err.message);
      announce(`Error: ${err.message}`, "assertive");
    }
  }

  async function handleResumeUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      announce("Uploading resume...");
      const response = await candidateApi.uploadResume(file, undefined);
      setDashboard(prev => ({
        ...response,
        results: prev?.results || {}
      }));
      setMessage("Resume uploaded. Now apply to jobs you're interested in.");
      announce("Resume uploaded successfully");
    } catch (err) {
      setError(err.message);
      announce(`Error: ${err.message}`, "assertive");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  const steps = [
    { title: "Job Description", description: selectedJd ? selectedJd.title : "Select a role to apply", completed: Boolean(selectedJd) },
    { title: "Resume uploaded", description: hasResume ? "Resume stored" : "Upload your resume", completed: hasResume },
    { title: "Applied", description: isApplied && hasResume ? "Application submitted" : "Not applied yet", completed: isApplied && hasResume },
    { title: "Interview stage", description: interviewCompleted ? "Interview submitted" : interviewReady ? "Ready to start" : canScheduleInterview ? "Schedule interview" : "Pending", completed: Boolean(interviewReady || interviewCompleted || finalDecision) },
  ];

  if (loading) return (
    <div role="status" aria-label="Loading dashboard" className="center muted">
      <p>Loading workspace...</p>
    </div>
  );

  if (error && !dashboard) return (
    <div role="alert" className="alert error">
      <p>{error}</p>
    </div>
  );

  return (
    <div className="space-y-8">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 page-enter">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white font-display">Candidate Workspace</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Track your application and interview progress.</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {uploading ? (
            <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-500">
              <Clock size={18} className="animate-spin" />
              <span className="text-sm font-medium">Uploading...</span>
            </div>
          ) : hasResume ? (
            <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400">
              <Check size={18} />
              <span className="text-sm font-medium">Resume Uploaded</span>
            </div>
          ) : (
            <label className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium cursor-pointer transition-all">
              <Upload size={18} />
              <span>Upload Resume</span>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                className="hidden"
                onChange={handleResumeUpload}
              />
            </label>
          )}
          {showStartInterview && (
            <Link
              to={interviewRoute}
              className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-bold transition-all shadow-lg shadow-blue-200 dark:shadow-blue-900/30 flex items-center space-x-2"
            >
              <span>{interviewSessionStatus === "in_progress" ? "Resume Interview" : "Start Interview"}</span>
              <ArrowRight size={18} aria-hidden="true" />
            </Link>
          )}
        </div>
      </header>

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

      <main id="main-content" className="grid grid-cols-1 md:grid-cols-2 gap-4 page-enter-delay-1">
        <article className="card card-hover-lift status-border-left blue">
          <p className="eyebrow">Current stage</p>
          <div className="mt-2">{result?.stage ? <StatusBadge status={result.stage} /> : <StatusBadge status="applied" />}</div>
          <p className="muted mt-3">Your application pipeline status</p>
        </article>
        <article className="card card-hover-lift status-border-left yellow">
          <p className="eyebrow">Interview status</p>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
            {interviewCompleted ? "Completed" : showStartInterview ? "Ready" : canScheduleInterview ? "Schedule" : "Pending"}
          </h2>
          <p className="muted">Next interview step</p>
        </article>
      </main>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 page-enter-delay-2">
        <div className="lg:col-span-2 space-y-8">
          <section aria-labelledby="jobs-heading" className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
            <div className="p-8 border-b border-slate-100 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 id="jobs-heading" className="text-2xl font-bold text-slate-900 dark:text-white">Available Positions</h2>
                <p className="text-slate-500 dark:text-slate-400 mt-1">Browse job descriptions and apply to get started.</p>
              </div>
              {hasResume && !isApplied && (
                <button
                  onClick={handleApplyToAll}
                  className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold transition-all whitespace-nowrap"
                >
                  Apply to All ({dashboard?.available_jds?.length || 0})
                </button>
              )}
            </div>
            <div className="p-8 space-y-6">
              {(dashboard?.available_jds || []).map((jd) => {
                const isThisJobApplied = selectedJdId === jd.id && hasResume;
                const jobResult = (dashboard.results && dashboard.results[jd.id]) || (isThisJobApplied ? result : null);
                const isThisSelected = jobResult?.shortlisted === true;
                const isThisRejected = jobResult?.stage?.key === "rejected" || jobResult?.final_decision === "rejected";
                const isThisUnderReview = isThisJobApplied && !isThisSelected && !isThisRejected && !jobResult?.stage?.key;

                return (
                  <div key={jd.id} className="border border-slate-200 dark:border-slate-700 rounded-2xl p-6 hover:border-blue-400 dark:hover:border-blue-600 transition-colors">
                    <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                      <div className="flex-1">
                        <h3 className="text-xl font-bold text-slate-900 dark:text-white">{jd.title}</h3>
                        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Qualify Score: {jd.qualify_score}% • {jd.total_questions} Questions</p>
                        
                        {isThisJobApplied && (
                          <div className="mt-2 flex items-center gap-2">
                            {isThisSelected && (
                              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 text-sm font-medium">
                                <Check size={14} /> Selected
                              </span>
                            )}
                            {isThisRejected && (
                              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-red-100 text-red-700 text-sm font-medium">
                                <X size={14} /> Rejected
                              </span>
                            )}
                            {isThisUnderReview && (
                              <button
                                onClick={handleRefreshStatus}
                                className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-sm font-medium hover:bg-amber-200 transition-colors"
                              >
                                <Clock size={14} /> Under Review (Refresh)
                              </button>
                            )}
                          </div>
                        )}
                      </div>

                      {isThisJobApplied ? (
                        isThisSelected && !interviewCompleted ? (
                          <Link
                            to="/candidate/schedule"
                            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold transition-all whitespace-nowrap"
                          >
                            Set Date
                            <ArrowRight size={16} />
                          </Link>
                        ) : isThisRejected ? (
                          <span className="inline-flex items-center px-5 py-2.5 rounded-xl bg-slate-100 text-slate-500 font-bold whitespace-nowrap">
                            Not Selected
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-5 py-2.5 rounded-xl bg-amber-50 text-amber-600 font-bold whitespace-nowrap">
                            Under Review
                          </span>
                        )
                      ) : hasResume ? (
                        <button
                          onClick={() => handleApply(jd.id, jd.title)}
                          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold transition-all whitespace-nowrap"
                        >
                          Apply
                          <ArrowRight size={16} />
                        </button>
                      ) : (
                        <button
                          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-200 dark:bg-slate-700 text-slate-500 font-bold whitespace-nowrap cursor-not-allowed"
                          disabled
                        >
                          Upload Resume First
                        </button>
                      )}
                    </div>
                    <div className="mt-4 p-4 bg-slate-50 dark:bg-slate-800 rounded-xl">
                      <p className="text-sm text-slate-600 dark:text-slate-300 whitespace-pre-wrap">{jd.description || "No description available."}</p>
                    </div>
                  </div>
                );
              })}
              {(dashboard?.available_jds || []).length === 0 && (
                <p className="text-center text-slate-500 dark:text-slate-400 py-8">No positions available at the moment.</p>
              )}
            </div>
          </section>

          {applications.length > 0 && (
            <section aria-labelledby="applications-heading" className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
              <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-center gap-3">
                <Briefcase size={24} className="text-indigo-600" />
                <div>
                  <h2 id="applications-heading" className="text-xl font-bold text-slate-900 dark:text-white">My Applications</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">Jobs you've applied to</p>
                </div>
              </div>
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {applications.map((app) => (
                  <div key={app.jd_id} className="p-4 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${app.status === 'selected' ? 'bg-emerald-500' : app.status === 'rejected' ? 'bg-red-500' : 'bg-amber-500'}`} />
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">{app.jd_title}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          Applied: {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : 'N/A'}
                        </p>
                      </div>
                    </div>
                    {app.status === 'selected' && (
                      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 text-sm font-medium">
                        <Check size={14} /> Selected
                      </span>
                    )}
                    {app.status === 'rejected' && (
                      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-red-100 text-red-700 text-sm font-medium">
                        <X size={14} /> Not Selected
                      </span>
                    )}
                    {app.status === 'under_review' && (
                      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-sm font-medium">
                        <Clock size={14} /> Under Review
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {selectedJd && isSelected && !interviewCompleted && !finalDecision && (
            <section aria-labelledby="schedule-heading" className="bg-gradient-to-r from-blue-600 to-indigo-700 p-8 rounded-3xl text-white">
              <h3 id="schedule-heading" className="text-xl font-bold font-display mb-2">Schedule Your Interview</h3>
              <p className="text-blue-100 mb-6">
                {scheduledInterviewDate ? "Your interview has a selected slot. You can update it from the calendar page." : "Open the calendar page to pick a date and time for your interview."}
              </p>
              <Link
                to="/candidate/schedule"
                className="inline-flex items-center gap-2 px-8 py-3 rounded-2xl bg-white text-blue-600 font-black hover:scale-[1.01] transition-all shadow-xl"
              >
                <span>{scheduledInterviewDate ? "View Calendar" : "Schedule Interview"}</span>
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
            </section>
          )}
        </div>

        <aside className="space-y-6 page-enter-delay-3">
          <section aria-labelledby="progress-heading" className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm card-hover-lift">
            <h4 id="progress-heading" className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider mb-6">Application Progress</h4>
            <StepChecklist steps={steps} />
          </section>
          
          {selectedJd && (
            <section aria-labelledby="selected-job-heading" className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm card-hover-lift">
              <h4 id="selected-job-heading" className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider mb-4">Applied Position</h4>
              <p className="text-lg font-bold text-slate-900 dark:text-white">{selectedJd.title}</p>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">Cutoff {selectedJd.qualify_score}% • {selectedJd.total_questions} questions</p>
            </section>
          )}
          
          <section aria-labelledby="guidance-heading" className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm card-hover-lift">
            <h4 id="guidance-heading" className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider mb-4">Next Step Guidance</h4>
            <div className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
              {!isApplied && (
                <div className="question-preview-card">Browse job positions, upload your resume, and apply to get started.</div>
              )}
              {isApplied && isUnderReview && (
                <div className="question-preview-card">
                  Your application is under review. Click the "Refresh" button to check for updates.
                </div>
              )}
              {result && isSelected && (
                <div className="question-preview-card text-emerald-700 dark:text-emerald-400">Congratulations! You have been selected. Schedule your interview to proceed.</div>
              )}
              {result && isRejected && (
                <div className="question-preview-card text-red-700 dark:text-red-400">Unfortunately, your application was not selected. Apply for other positions to try again.</div>
              )}
              {result && showStartInterview && (
                <div className="question-preview-card">Your interview is ready to start.</div>
              )}
              {result && canScheduleInterview && (
                <div className="question-preview-card">Schedule your interview to continue.</div>
              )}
              {interviewCompleted && (
                <div className="question-preview-card">Interview completed - wait for HR review.</div>
              )}
            </div>
          </section>
        </aside>
      </div>
      <HelpSupportButton supportEmail="support@quadranttech.com" />
      <div aria-live="polite" aria-atomic="true" className="sr-announcer" />
    </div>
  );
}