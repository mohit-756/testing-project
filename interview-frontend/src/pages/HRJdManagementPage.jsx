import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Plus, ChevronLeft, ChevronRight, Eye, Edit2, Trash2, MoreVertical, Upload, Loader2, X } from "lucide-react";
import MetricCard from "../components/MetricCard";
import { hrApi } from "../services/api";

function SkillsEditor({ skills, onChange }) {
  function updateWeight(skill, value) {
    onChange({ ...skills, [skill]: Math.max(1, Math.min(10, Number(value) || 1)) });
  }
  function removeSkill(skill) {
    const next = { ...skills };
    delete next[skill];
    onChange(next);
  }
  function addSkill() {
    const name = prompt("Skill name (e.g. python, react, sql):")?.trim().toLowerCase();
    if (name && !skills[name]) onChange({ ...skills, [name]: 5 });
  }
  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800">
            <th className="px-4 py-3 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">Skill</th>
            <th className="px-4 py-3 text-center text-xs font-bold text-slate-500 uppercase tracking-wider">Weight (1-10)</th>
            <th className="px-4 py-3 text-center text-xs font-bold text-slate-500 uppercase tracking-wider w-16">Remove</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {Object.entries(skills).map(([skill, weight]) => (
            <tr key={skill} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
              <td className="px-4 py-2.5 font-medium text-slate-900 dark:text-white capitalize">{skill}</td>
              <td className="px-4 py-2.5 text-center">
                <input type="number" min={1} max={10} value={weight}
                  onChange={(e) => updateWeight(skill, e.target.value)}
                  className="w-16 text-center px-2 py-1.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
              </td>
              <td className="px-4 py-2.5 text-center">
                <button onClick={() => removeSkill(skill)} className="p-1 text-slate-400 hover:text-red-500 transition-colors rounded">
                  <X size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-slate-100 dark:border-slate-800">
            <td colSpan={3} className="px-4 py-2.5">
              <button onClick={addSkill} className="text-sm text-blue-600 dark:text-blue-400 hover:underline font-medium flex items-center gap-1">
                <Plus size={14} />Add skill manually
              </button>
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

function JdForm({ initialData, onSave, onCancel }) {
  const [title, setTitle] = useState(initialData?.title || "");
  const [jdText, setJdText] = useState(initialData?.jd_text || "");
  const [qualifyScore, setQualifyScore] = useState(initialData?.qualify_score ?? 60);
  const [totalQuestions, setTotalQuestions] = useState(initialData?.total_questions ?? 5);
  const [skills, setSkills] = useState(initialData?.weights_json || {});
  const [educationRequirement, setEducationRequirement] = useState(initialData?.education_requirement || "");
  const [experienceRequirement, setExperienceRequirement] = useState(initialData?.experience_requirement ?? 0);
  const [minAcademicPercent, setMinAcademicPercent] = useState(initialData?.min_academic_percent ?? 0);
  const [projectQuestionRatioPct, setProjectQuestionRatioPct] = useState(
    initialData?.project_question_ratio != null ? Math.round(initialData.project_question_ratio * 100) : 80
  );
  const [totalDurationMinutes, setTotalDurationMinutes] = useState(initialData?.total_duration_minutes ?? 30);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const isEdit = Boolean(initialData?.id);

  async function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError("");
    try {
      const result = await hrApi.uploadJd(file);
      if (result.ai_skills && Object.keys(result.ai_skills).length > 0) setSkills(result.ai_skills);
      if (result.jd_title && !title) setTitle(result.jd_title);
      if (result.education_requirement) setEducationRequirement(result.education_requirement);
      if (result.experience_requirement != null) setExperienceRequirement(result.experience_requirement);
      if (result.min_academic_percent != null) setMinAcademicPercent(result.min_academic_percent);
    } catch (err) { setError(err.message); }
    finally { setUploading(false); e.target.value = ""; }
  }

  async function handleExtractFromText() {
    if (!jdText.trim()) { setError("Paste JD text first."); return; }
    setExtracting(true); setError("");
    try {
      const result = await hrApi.parseJdText(jdText, title);
      if (result.ai_skills && Object.keys(result.ai_skills).length > 0) setSkills(result.ai_skills);
      if (result.jd_title && !title) setTitle(result.jd_title);
      if (result.education_requirement) setEducationRequirement(result.education_requirement);
      if (result.experience_requirement != null) setExperienceRequirement(result.experience_requirement);
      if (result.min_academic_percent != null) setMinAcademicPercent(result.min_academic_percent);
    } catch (err) { setError(err.message); }
    finally { setExtracting(false); }
  }

  async function handleSave() {
    if (!title.trim()) { setError("Please enter a job title to identify this JD."); return; }
    if (!jdText.trim() && !Object.keys(skills).length) { setError("Please upload a JD file or paste job description text AND extract skills from it."); return; }
    setSaving(true); setError("");
    try {
      const payload = {
        title: title.trim(),
        jd_text: jdText.trim() || title,
        weights_json: skills,
        qualify_score: Number(qualifyScore),
        total_questions: Number(totalQuestions),
        education_requirement: educationRequirement.trim() || null,
        experience_requirement: Number(experienceRequirement) || 0,
        min_academic_percent: Number(minAcademicPercent) || 0,
        project_question_ratio: Math.max(0, Math.min(1, Number(projectQuestionRatioPct) / 100)),
        total_duration_minutes: Number(totalDurationMinutes) || 30,
      };
      if (isEdit) { await hrApi.updateJd(initialData.id, payload); }
      else { await hrApi.createJd(payload); }
      onSave();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-8 space-y-6">
      <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{isEdit ? "Edit Job Description" : "Create Job Description"}</h2>
      {error && <p className="alert error">{error}</p>}
      {!isEdit && (
        <div>
          <p className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-2">Upload JD file (PDF / DOCX / TXT)</p>
          <label className={`flex items-center gap-3 border-2 border-dashed rounded-2xl p-5 cursor-pointer transition-all ${uploading ? "border-blue-400 bg-blue-50/30" : "border-slate-200 dark:border-slate-700 hover:border-blue-400 hover:bg-blue-50/20"}`}>
            <input type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={handleFileUpload} disabled={uploading} />
            {uploading ? <Loader2 size={20} className="text-blue-500 animate-spin flex-shrink-0" /> : <Upload size={20} className="text-slate-400 flex-shrink-0" />}
            <div>
              <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                {uploading ? "Extracting skills with AI..." : "Click to upload — skills auto-extracted by AI"}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">or fill the fields manually below</p>
            </div>
          </label>
        </div>
      )}
      <div className="grid md:grid-cols-3 gap-4">
        <div className="md:col-span-1">
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Job Title *</label>
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Backend Engineer" aria-label="Job title (required)" aria-required="true"
            className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Used to identify this JD</p>
        </div>
        <div>
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Min Passing Score (%)</label>
          <input type="number" min={0} max={100} value={qualifyScore} onChange={(e) => setQualifyScore(e.target.value)} aria-label="Minimum qualifying score"
            className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Score needed to pass screening</p>
        </div>
        <div>
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Interview Questions</label>
          <input type="number" min={1} max={20} value={totalQuestions} onChange={(e) => setTotalQuestions(e.target.value)} aria-label="Number of interview questions"
            className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Total candidates will answer</p>
        </div>
      </div>
      <div className="p-6 bg-gradient-to-br from-slate-50 to-slate-50/50 dark:from-slate-800/50 dark:to-slate-800/30 rounded-2xl border border-slate-200 dark:border-slate-700">
        <p className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-4 flex items-center gap-2">
          <span className="text-base">👤</span>
          Candidate Requirements & Interview Setup
        </p>
        <div className="grid md:grid-cols-4 gap-4">
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Education Level</label>
            <select value={educationRequirement} onChange={(e) => setEducationRequirement(e.target.value)} aria-label="Minimum education requirement"
              className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white">
              <option value="">Any / Not required</option>
              <option value="bachelor">Bachelor's Degree</option>
              <option value="master">Master's Degree</option>
              <option value="phd">PhD / Doctorate</option>
            </select>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Filter candidates by education</p>
          </div>
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Min Experience (yrs)</label>
            <input type="number" min={0} max={30} value={experienceRequirement} aria-label="Minimum years of experience required"
              onChange={(e) => setExperienceRequirement(e.target.value)} placeholder="0 = any"
              className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Years in field (0 = any)</p>
          </div>
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Min GPA / Academic %</label>
            <input type="number" min={0} max={100} step={5} value={minAcademicPercent} aria-label="Minimum academic percentage or GPA"
              onChange={(e) => setMinAcademicPercent(e.target.value)} placeholder="0 = disabled"
              className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Set to 0 to disable</p>
          </div>
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Project Questions %</label>
            <input type="number" min={0} max={100} step={10} value={projectQuestionRatioPct} aria-label="Percentage of project-based questions"
              onChange={(e) => setProjectQuestionRatioPct(e.target.value)} placeholder="80"
              className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Rest will be theory</p>
          </div>
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Interview Duration (min)</label>
            <input type="number" min={5} max={120} value={totalDurationMinutes}
              onChange={(e) => setTotalDurationMinutes(e.target.value)} placeholder="30"
              className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
            <p className="text-xs text-slate-400 mt-1">Total interview time</p>
          </div>
        </div>
      </div>
      <div>
        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">JD Text (optional if file uploaded)</label>
        <textarea rows={5} value={jdText} onChange={(e) => setJdText(e.target.value)}
          placeholder="Paste job description here, or upload a file above..."
          className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white resize-none" />
        {!isEdit && jdText.trim() && (
          <button onClick={handleExtractFromText} disabled={extracting}
            className="mt-2 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-sm font-bold disabled:opacity-50 transition-all flex items-center gap-2">
            {extracting ? <><Loader2 size={16} className="animate-spin" /> Extracting...</> : <><Upload size={16} /> Extract Details from Text</>}
          </button>
        )}
      </div>
      <div>
        <div className="flex items-center justify-between mb-3">
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Skills & Weights</label>
          <span className="text-xs text-slate-400">{Object.keys(skills).length} skills</span>
        </div>
        {Object.keys(skills).length > 0 ? (
          <SkillsEditor skills={skills} onChange={setSkills} />
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-200 dark:border-slate-700 p-6 text-center">
            <p className="text-sm text-slate-500">Upload a JD file or paste text and click Extract Details.</p>
          </div>
        )}
      </div>
      <div className="flex items-center gap-3 pt-2">
        <button onClick={handleSave} disabled={saving}
          className="px-8 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold disabled:opacity-50 transition-all">
          {saving ? "Saving..." : isEdit ? "Update JD" : "Create JD"}
        </button>
        <button onClick={onCancel}
          className="px-6 py-3 rounded-xl border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 font-bold hover:bg-slate-50 dark:hover:bg-slate-800 transition-all">
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function HRJdManagementPage() {
  const navigate = useNavigate();
  const [jds, setJds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [showForm, setShowForm] = useState(false);
  const [editingJd, setEditingJd] = useState(null);
  const [openMenu, setOpenMenu] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const loadJds = useCallback(async () => {
    setLoading(true); setError("");
    try { const r = await hrApi.listJds(); setJds(Array.isArray(r) ? r : r?.jds || r?.jobs || []); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadJds(); }, [loadJds]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return !q ? jds : jds.filter((j) => [j.title, String(j.id)].some((v) => String(v || "").toLowerCase().includes(q)));
  }, [jds, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / itemsPerPage));
  const paged = filtered.slice((page - 1) * itemsPerPage, page * itemsPerPage);

  useEffect(() => { setPage(1); }, [search, itemsPerPage]);

  async function handleDelete(jdId) {
    if (!confirm("Delete this JD?")) return;
    setDeletingId(jdId); setError(""); setMessage("");
    try { await hrApi.deleteJd(jdId); await loadJds(); setMessage("JD deleted."); setOpenMenu(null); }
    catch (e) { setError(e.message); }
    finally { setDeletingId(null); }
  }

  async function handleToggleActive(jdId) {
    setError(""); setMessage("");
    try {
      const response = await hrApi.toggleJdActive(jdId);
      const next = response?.jd?.is_active ? "Active" : "Inactive";
      await loadJds();
      setMessage(`JD marked ${next}.`);
      setOpenMenu(null);
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleEdit(jdId) {
    try { const r = await hrApi.getJd(jdId); setEditingJd(r.jd); setShowForm(true); setOpenMenu(null); }
    catch (e) { setError(e.message); }
  }

  function handleFormSave() {
    setShowForm(false); setEditingJd(null);
    setMessage("JD saved successfully."); loadJds();
  }

  if (loading && !jds.length) return <p className="center muted py-12">Loading JDs...</p>;

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 page-enter">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white font-display">JD Management</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Create and manage job descriptions with skill weights, education requirements, and interview config.</p>
        </div>
        <button onClick={() => { setEditingJd(null); setShowForm(true); }}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm transition-all">
          <Plus size={16} /><span>Add JD</span>
        </button>
      </div>
      {error && <p className="alert error">{error}</p>}
      {message && <p className="alert success">{message}</p>}
      <div className="grid grid-cols-3 gap-4">
        <MetricCard title="Total JDs" value={jds.length} color="blue" />
        <MetricCard title="Avg Qualify Score" value={jds.length ? `${Math.round(jds.reduce((s, j) => s + Number(j.qualify_score || 0), 0) / jds.length)}%` : "—"} color="green" />
        <MetricCard title="Avg Questions" value={jds.length ? (jds.reduce((s, j) => s + Number(j.total_questions || 0), 0) / jds.length).toFixed(1) : "—"} color="purple" />
      </div>
      {showForm && (
        <JdForm initialData={editingJd} onSave={handleFormSave} onCancel={() => { setShowForm(false); setEditingJd(null); }} />
      )}
      <div className="bg-white dark:bg-slate-900 p-5 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
          <input type="text" placeholder="Search JDs by title or ID..." value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-full pl-11 pr-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
        </div>
      </div>
      <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/30 border-b border-slate-100 dark:border-slate-800">
                <th className="px-6 py-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">ID</th>
                <th className="px-6 py-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">Title</th>
                <th className="px-6 py-4 text-center text-xs font-bold text-slate-400 uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">Skills</th>
                <th className="px-6 py-4 text-center text-xs font-bold text-slate-400 uppercase tracking-wider">Qualify</th>
                <th className="px-6 py-4 text-center text-xs font-bold text-slate-400 uppercase tracking-wider">Exp</th>
                <th className="px-6 py-4 text-center text-xs font-bold text-slate-400 uppercase tracking-wider">Questions</th>
                <th className="px-6 py-4 text-right text-xs font-bold text-slate-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50 dark:divide-slate-800">
              {!paged.length ? (
                <tr><td colSpan={8} className="px-6 py-12 text-center text-slate-500">No JDs found. Create one to get started.</td></tr>
              ) : paged.map((jd) => (
                <tr key={jd.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-all">
                  <td className="px-6 py-4 text-xs font-bold text-slate-400">{jd.id}</td>
                  <td className="px-6 py-4">
                    <p className="font-bold text-slate-900 dark:text-white">{jd.title}</p>
                    <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">{jd.jd_text?.substring(0, 80)}...</p>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-bold border ${jd.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-800" : "bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700"}`}>
                      {jd.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(jd.weights_json || {}).slice(0, 4).map(([skill, w]) => (
                        <span key={skill} className="px-2 py-0.5 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 rounded text-xs font-medium">{skill} ({w})</span>
                      ))}
                      {Object.keys(jd.weights_json || {}).length > 4 && (
                        <span className="px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-500 rounded text-xs">+{Object.keys(jd.weights_json).length - 4} more</span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-center font-semibold text-slate-900 dark:text-white">{jd.qualify_score}%</td>
                  <td className="px-6 py-4 text-center text-xs text-slate-600 dark:text-slate-300">
                    {jd.experience_requirement > 0 ? `${jd.experience_requirement}+ yrs` : <span className="text-slate-400">Any</span>}
                  </td>
                  <td className="px-6 py-4 text-center font-semibold text-slate-900 dark:text-white">{jd.total_questions}</td>
                  <td className="px-6 py-4 text-right relative">
                    <button onClick={() => setOpenMenu(openMenu === jd.id ? null : jd.id)}
                      className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-all">
                      <MoreVertical size={18} />
                    </button>
                    {openMenu === jd.id && (
                      <div className="absolute right-6 mt-2 w-40 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-lg z-10 overflow-hidden">
                        <button onClick={() => navigate(`/hr/jds/${jd.id}`)} className="flex items-center gap-2 w-full px-4 py-2.5 text-left text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"><Eye size={15} />View</button>
                        <button onClick={() => handleEdit(jd.id)} className="flex items-center gap-2 w-full px-4 py-2.5 text-left text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"><Edit2 size={15} />Edit</button>
                        <button onClick={() => handleToggleActive(jd.id)} className="flex items-center gap-2 w-full px-4 py-2.5 text-left text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800">{jd.is_active ? "Deactivate" : "Activate"}</button>
                        <button onClick={() => handleDelete(jd.id)} disabled={deletingId === jd.id} className="flex items-center gap-2 w-full px-4 py-2.5 text-left text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 disabled:opacity-60"><Trash2 size={15} />{deletingId === jd.id ? "Deleting..." : "Delete"}</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="p-4 sm:p-5 bg-slate-50/30 dark:bg-slate-800/20 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 sm:gap-3 text-xs sm:text-sm">
            <span className="text-slate-500">Show</span>
            <select value={itemsPerPage} onChange={(e) => { setItemsPerPage(Number(e.target.value)); setPage(1); }} className="px-2 py-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm dark:text-white">
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={15}>15</option>
              <option value={25}>25</option>
            </select>
            <span className="text-slate-500">per page</span>
          </div>
          <div className="flex items-center gap-2">
            <button disabled={page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))} className="p-1.5 sm:p-2 rounded-xl border border-slate-200 dark:border-slate-800 disabled:opacity-30 hover:bg-white dark:hover:bg-slate-900 transition-all"><ChevronLeft size={14} /></button>
            <span className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white px-2">Page {page} / {totalPages}</span>
            <button disabled={page === totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} className="p-1.5 sm:p-2 rounded-xl border border-slate-200 dark:border-slate-800 disabled:opacity-30 hover:bg-white dark:hover:bg-slate-900 transition-all"><ChevronRight size={14} /></button>
          </div>
        </div>
      </div>
    </div>
  );
}
