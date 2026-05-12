import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Users, Target, FileText, Plus, Trash2 } from "lucide-react";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";
import { hrApi } from "../services/api";

export default function HRJdDetailPage() {
  const { jdId } = useParams();
  const [jd, setJd] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("details");
  const [customQuestions, setCustomQuestions] = useState([]);
  const [newQuestion, setNewQuestion] = useState("");
  const [savingCustom, setSavingCustom] = useState(false);

  const loadJdDetail = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const detailResponse = await hrApi.getJd(jdId);
      setJd(detailResponse.jd);
      setCustomQuestions(detailResponse.jd?.custom_questions || []);

      try {
        const candidatesResponse = await hrApi.listCandidates();
        const jdCandidates = (candidatesResponse.candidates || []).filter(
          (candidate) => Number(candidate.job?.id) === Number(jdId) || Number(candidate.assignedJd?.id) === Number(jdId)
        );
        setCandidates(jdCandidates);
      } catch {
        setCandidates([]);
      }
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, [jdId]);

  useEffect(() => {
    loadJdDetail();
  }, [loadJdDetail]);

  const handleAddQuestion = () => {
    if (newQuestion.trim()) {
      setCustomQuestions([...customQuestions, newQuestion.trim()]);
      setNewQuestion("");
    }
  };

  const handleRemoveQuestion = (index) => {
    setCustomQuestions(customQuestions.filter((_, i) => i !== index));
  };

  const handleSaveCustomQuestions = async () => {
    setSavingCustom(true);
    setError("");
    try {
      const response = await hrApi.updateCustomQuestions(jdId, { questions: customQuestions });
      setCustomQuestions(response.custom_questions || []);
      // Maybe show a success toast
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingCustom(false);
    }
  };

  if (loading) {
    return <p className="center muted py-12">Loading JD details...</p>;
  }

  if (error && !jd) {
    return <p className="alert error">{error}</p>;
  }

  if (!jd) {
    return <p className="muted">JD not found.</p>;
  }

  const requiredSkills = jd.weights_json ? Object.keys(jd.weights_json) : [];
  const totalApplicants = candidates.length;
  const shortlistedCount = candidates.filter(
    (candidate) =>
      candidate.finalDecision?.key === "shortlisted" ||
      candidate.finalDecision?.key === "selected"
  ).length;
  const rejectedCount = candidates.filter(
    (candidate) => candidate.finalDecision?.key === "rejected"
  ).length;
  const projectQuestionRatio = Number(jd.project_question_ratio || 0);
  const theoryQuestionRatio = Math.max(0, 1 - projectQuestionRatio);

  const tabs = [
    { id: "details", label: "JD Details", icon: FileText },
    { id: "skills", label: "Skills", icon: Target },
    { id: "candidates", label: "Candidates", icon: Users },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between gap-4">
        <Link
          to="/hr/jds"
          className="flex items-center space-x-2 text-slate-500 hover:text-blue-600 transition-colors font-medium"
        >
          <ArrowLeft size={20} />
          <span>Back to JD Management</span>
        </Link>
        <StatusBadge status={{ label: `JD #${jd.id}`, tone: "secondary" }} />
      </div>

      <div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white font-display">
          {jd.title}
        </h1>
        <p className="text-slate-500 dark:text-slate-400 mt-2">JD ID: {jd.id}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Total Applicants" value={totalApplicants} icon={Users} color="blue" />
        <MetricCard title="Shortlisted" value={shortlistedCount} icon={Target} color="green" />
        <MetricCard title="Rejected" value={rejectedCount} icon={Users} color="red" />
        <MetricCard title="Qualify Score" value={`${jd.qualify_score}%`} color="purple" />
      </div>

      <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="border-b border-slate-100 dark:border-slate-800 p-6 flex items-center gap-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-all ${
                  activeTab === tab.id
                    ? "bg-blue-600 text-white"
                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                }`}
              >
                <Icon size={18} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        <div className="p-8">
          {activeTab === "details" && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">
                  Description
                </h3>
                <div className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-6 text-slate-700 dark:text-slate-300 whitespace-pre-wrap text-sm leading-relaxed">
                  {jd.jd_text}
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">
                    Requirements
                  </h3>
                  <div className="space-y-3">
                    <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-widest font-bold">
                        Minimum Academic %
                      </p>
                      <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                        {jd.min_academic_percent}%
                      </p>
                    </div>
                    <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-widest font-bold">
                        Qualify Score
                      </p>
                      <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                        {jd.qualify_score}%
                      </p>
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">
                    Interview Config
                  </h3>
                  <div className="space-y-3">
                    <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-widest font-bold">
                        Total Questions
                      </p>
                      <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                        {jd.total_questions}
                      </p>
                    </div>
                    <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-widest font-bold">
                        Project Question Ratio
                      </p>
                      <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                        {(projectQuestionRatio * 100).toFixed(0)}%
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">
                  Mandatory Questions
                </h3>
                <div className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-6 space-y-4">
                  {customQuestions.map((q, i) => (
                    <div key={i} className="flex items-center gap-3 bg-white dark:bg-slate-700/50 p-3 rounded-lg border border-slate-200 dark:border-slate-700">
                      <p className="flex-1 text-sm text-slate-800 dark:text-slate-200">{q}</p>
                      <button type="button" onClick={() => handleRemoveQuestion(i)} className="p-2 rounded-md text-slate-400 hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/30"><Trash2 size={16} /></button>
                    </div>
                  ))}
                  {customQuestions.length === 0 && <p className="text-sm text-slate-500 dark:text-slate-400 text-center py-4">No mandatory questions set.</p>}
                  <div className="flex items-center gap-3 pt-4 border-t border-slate-200 dark:border-slate-700">
                    <input
                      type="text"
                      value={newQuestion}
                      onChange={(e) => setNewQuestion(e.target.value)}
                      placeholder="Add a new mandatory question..."
                      className="flex-1 px-3 py-2.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl outline-none text-sm dark:text-white"
                    />
                    <button type="button" onClick={handleAddQuestion} className="p-3 rounded-xl bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 hover:bg-blue-200 dark:hover:bg-blue-900/60"><Plus size={18} /></button>
                  </div>
                  <button type="button" onClick={handleSaveCustomQuestions} disabled={savingCustom} className="w-full mt-4 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold disabled:opacity-60">
                    {savingCustom ? "Saving..." : "Save Mandatory Questions"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === "skills" && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">
                  Required Skills and Weightage
                </h3>
                {requiredSkills.length > 0 ? (
                  <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {requiredSkills.map((skill) => (
                      <div
                        key={skill}
                        className="bg-blue-50 dark:bg-blue-900/20 rounded-2xl p-4 border border-blue-200 dark:border-blue-800"
                      >
                        <p className="text-sm text-blue-600 dark:text-blue-400 uppercase tracking-widest font-bold">
                          {skill}
                        </p>
                        <p className="text-2xl font-bold text-blue-900 dark:text-blue-200 mt-2">
                          {jd.weights_json[skill]}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-500 dark:text-slate-400">
                    No skills configured.
                  </p>
                )}
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-6">
                  <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-widest font-bold">
                    Project Questions
                  </p>
                  <p className="text-3xl font-bold text-slate-900 dark:text-white mt-3">
                    {(projectQuestionRatio * 100).toFixed(0)}%
                  </p>
                </div>
                <div className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-6">
                  <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-widest font-bold">
                    Theory Questions
                  </p>
                  <p className="text-3xl font-bold text-slate-900 dark:text-white mt-3">
                    {(theoryQuestionRatio * 100).toFixed(0)}%
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeTab === "candidates" && (
            <div className="space-y-4">
              {candidates.length === 0 ? (
                <p className="text-slate-500 dark:text-slate-400 text-center py-12">
                  No candidates have applied for this JD yet.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800">
                        <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                          Candidate
                        </th>
                        <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                          Email
                        </th>
                        <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                          Resume Score
                        </th>
                        <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                          Decision
                        </th>
                        <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                          Status
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {candidates.map((candidate) => (
                        <tr
                          key={candidate.candidate_uid}
                          className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors"
                        >
                          <td className="px-6 py-4">
                            <p className="font-medium text-slate-900 dark:text-white">
                              {candidate.name}
                            </p>
                          </td>
                          <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-300">
                            {candidate.email}
                          </td>
                          <td className="px-6 py-4">
                            <p className="font-semibold text-slate-900 dark:text-white">
                              {candidate.resumeScore || 0}%
                            </p>
                          </td>
                          <td className="px-6 py-4">
                            <StatusBadge status={candidate.finalDecision} />
                          </td>
                          <td className="px-6 py-4">
                            <StatusBadge status={candidate.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
