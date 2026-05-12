import { useMemo, useState } from "react";
import { Loader2, Plus, Upload, X } from "lucide-react";
import { hrApi } from "../../services/api";

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

  const entries = useMemo(() => Object.entries(skills || {}), [skills]);

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
          {entries.map(([skill, weight]) => (
            <tr key={skill} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
              <td className="px-4 py-2.5 font-medium text-slate-900 dark:text-white capitalize">{skill}</td>
              <td className="px-4 py-2.5 text-center">
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={weight}
                  onChange={(e) => updateWeight(skill, e.target.value)}
                  className="w-16 text-center px-2 py-1.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white"
                />
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

// NOTE: Fresh JD form used by the clean management page only.
export default function JdFormCard({ initialData, onSaved, onCancel }) {
  const isEdit = Boolean(initialData?.id);
  const [title, setTitle] = useState(initialData?.title || "");
  const [jdText, setJdText] = useState(initialData?.jd_text || "");
  const [qualifyScore, setQualifyScore] = useState(initialData?.qualify_score ?? 65);
  const [totalQuestions, setTotalQuestions] = useState(initialData?.total_questions ?? 8);
  const [skills, setSkills] = useState(initialData?.weights_json || {});
  const [educationRequirement, setEducationRequirement] = useState(initialData?.education_requirement || "");
  const [experienceRequirement, setExperienceRequirement] = useState(initialData?.experience_requirement ?? 0);
  const [minAcademicPercent, setMinAcademicPercent] = useState(initialData?.min_academic_percent ?? 0);
  const [projectQuestionRatioPct, setProjectQuestionRatioPct] = useState(
    initialData?.project_question_ratio != null ? Math.round(initialData.project_question_ratio * 100) : 80
  );
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const result = await hrApi.uploadJd(file);
      if (result?.ai_skills && Object.keys(result.ai_skills).length > 0) setSkills(result.ai_skills);
      if (result?.jd_title && !title) setTitle(result.jd_title);
      if (result?.jd_text && !jdText) setJdText(result.jd_text);
    } catch (err) {
      setError(err.message || "JD file upload failed.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function handleSave() {
    if (!title.trim()) return setError("Title is required.");
    if (!jdText.trim() && !Object.keys(skills).length) return setError("Add JD text or at least one skill.");

    setSaving(true);
    setError("");
    try {
      const payload = {
        title: title.trim(),
        jd_text: jdText.trim() || title.trim(),
        weights_json: skills,
        qualify_score: Number(qualifyScore),
        total_questions: Number(totalQuestions),
        education_requirement: educationRequirement.trim() || null,
        experience_requirement: Number(experienceRequirement) || 0,
        min_academic_percent: Number(minAcademicPercent) || 0,
        project_question_ratio: Math.max(0, Math.min(1, Number(projectQuestionRatioPct) / 100)),
      };
      const response = isEdit
        ? await hrApi.updateJd(initialData.id, payload)
        : await hrApi.createJd(payload);
      onSaved?.(response?.jd || null);
    } catch (err) {
      setError(err.message || "Saving JD failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-8 space-y-6">
      <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{isEdit ? "Edit Job Description" : "Create Job Description"}</h2>
      {error ? <p className="alert error">{error}</p> : null}

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
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
        </div>
        <div>
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Qualify Score (%)</label>
          <input type="number" min={0} max={100} value={qualifyScore} onChange={(e) => setQualifyScore(e.target.value)} className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
        </div>
        <div>
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">No. of Questions</label>
          <input type="number" min={1} max={20} value={totalQuestions} onChange={(e) => setTotalQuestions(e.target.value)} className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
        </div>
      </div>

      <div className="p-5 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-200 dark:border-slate-700">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Candidate Requirements</p>
        <div className="grid md:grid-cols-4 gap-4">
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Education Level</label>
            <select value={educationRequirement} onChange={(e) => setEducationRequirement(e.target.value)} className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white">
              <option value="">Any / Not required</option>
              <option value="bachelor">Bachelor's</option>
              <option value="master">Master's</option>
              <option value="phd">PhD / Doctorate</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Min Experience (yrs)</label>
            <input type="number" min={0} max={30} value={experienceRequirement} onChange={(e) => setExperienceRequirement(e.target.value)} className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
          </div>
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Min Academic % (0=off)</label>
            <input type="number" min={0} max={100} step={5} value={minAcademicPercent} onChange={(e) => setMinAcademicPercent(e.target.value)} className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
          </div>
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">Project Q Ratio (%)</label>
            <input type="number" min={0} max={100} step={10} value={projectQuestionRatioPct} onChange={(e) => setProjectQuestionRatioPct(e.target.value)} className="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white" />
            <p className="text-xs text-slate-400 mt-1">Rest = theory questions</p>
          </div>
        </div>
      </div>

      <div>
        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-1.5">JD Text</label>
        <textarea rows={5} value={jdText} onChange={(e) => setJdText(e.target.value)} className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white resize-none" />
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
            <p className="text-sm text-slate-500">Upload a JD file to auto-extract skills, or add them manually.</p>
            <button onClick={() => setSkills({ python: 5 })} className="mt-3 text-sm text-blue-600 dark:text-blue-400 hover:underline">Add skill manually</button>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3 pt-2">
        <button onClick={handleSave} disabled={saving} className="px-8 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold disabled:opacity-50 transition-all">
          {saving ? "Saving..." : isEdit ? "Update JD" : "Create JD"}
        </button>
        <button onClick={onCancel} className="px-6 py-3 rounded-xl border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 font-bold hover:bg-slate-50 dark:hover:bg-slate-800 transition-all">
          Cancel
        </button>
      </div>
    </div>
  );
}
