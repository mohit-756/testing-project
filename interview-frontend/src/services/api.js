import axios from "axios";
import { toStatusObject } from "../utils/stages";
import { uploadFileToS3 } from "../utils/s3Upload";
const configuredBaseUrl = String(import.meta.env?.VITE_API_BASE_URL || "/api").trim();
const baseURL = configuredBaseUrl === "/" ? "/api" : configuredBaseUrl.replace(/\/+$/, "");
const isProduction = configuredBaseUrl.includes("cloudfront.net") || configuredBaseUrl.includes("elasticbeanstalk.com") || configuredBaseUrl.includes("aws.amazon.com");

console.log("[API] VITE_API_BASE_URL:", import.meta.env?.VITE_API_BASE_URL);
console.log("[API] Resolved baseURL:", baseURL);
console.log("[API] Production mode:", isProduction);

const apiClient = axios.create({
  // Defaults to /api for Vite proxy. Override via VITE_API_BASE_URL when needed.
  baseURL,
  withCredentials: true,
});

export { apiClient, baseURL };

export function backendAssetUrl(path) {
  if (!path) return "";
  const value = String(path);
  if (value.startsWith("http://") || value.startsWith("https://")) return value;
  if (!value.startsWith("/")) return value;

  const apiUrl = new URL(baseURL || "/api", window.location.origin);
  const apiRootPath = apiUrl.pathname.replace(/\/api\/?$/, "") || "/";
  const assetPath = `${apiRootPath.replace(/\/+$/, "")}${value}`;
  return `${apiUrl.origin}${assetPath}`;
}

function buildAvatar(name) {
  const seed = String(name || "user").trim() || "user";
  return `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(seed)}`;
}

function extractErrorMessage(error) {
  const responseData = error?.response?.data;
  const status = error?.response?.status;
  const contentType = error?.response?.headers?.["content-type"] || "";

  const wrappedError = responseData?.error;
  if (typeof wrappedError === "string" && wrappedError.trim()) return wrappedError;

  const detail = responseData?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((i) => (typeof i === "string" ? i : i?.msg || JSON.stringify(i))).join(", ");
  }
  
  // Handle HTML responses (server errors)
  if (typeof responseData === "string" && !contentType.includes("application/json")) {
    if (responseData.includes("<!DOCTYPE html>") || responseData.includes("<html")) {
      console.error("[API] Received HTML response instead of JSON:", responseData.substring(0, 200));
      return "Server error. Please try again or contact support.";
    }
    return responseData;
  }
  
  // Map common error status codes to user-friendly messages
  const errorMessages = {
    400: "Invalid input. Please check and try again.",
    401: "Your session expired. Please log in again.",
    403: "You don't have permission for this action.",
    404: "The requested item was not found.",
    409: "This item was already modified. Please refresh and try again.",
    422: "Validation error. Please check your input.",
    429: "Too many requests. Please wait a moment.",
    500: "Server error. Please try again later.",
    502: "Server unavailable. Please try again later.",
    503: "Service temporarily unavailable. Please try again.",
  };
  
  // Return user-friendly message for known status codes
  if (status && errorMessages[status]) {
    return errorMessages[status];
  }
  
  // Fallback to generic message
  return error?.message || "Something went wrong. Please try again.";
}

const API_TIMEOUT_MS = 30000; // 30s timeout for all API calls

async function request(config) {
  try {
    console.log(`[API] Request: ${config.method} ${config.url}`, config.data ? 'with data' : '');
    console.log(`[API] Request data:`, JSON.stringify(config.data));
    const response = await apiClient({
      ...config,
      timeout: config.timeout || API_TIMEOUT_MS,
    });
    console.log(`[API] Response status:`, response.status);
    console.log(`[API] Response headers content-type:`, response.headers["content-type"]);
    console.log(`[API] Response data preview:`, typeof response.data === 'string' ? response.data.substring(0, 100) : JSON.stringify(response.data).substring(0, 200));
    // Unwrap ApiResponseMiddleware wrapper: { success, data, error }
    // Backend endpoints return { ok, ... } — middleware wraps them automatically.
    const body = response.data;
    if (body && typeof body === 'object' && 'success' in body && 'data' in body) {
      return body.data;
    }
    return body;
  } catch (error) {
    console.error(`[API] Error status:`, error.response?.status);
    console.error(`[API] Error content-type:`, error.response?.headers?.["content-type"]);
    console.error(`[API] Error response data:`, error.response?.data);
    throw new Error(extractErrorMessage(error));
  }
}

function deriveDecision({ status, shortlisted, sessionStatus, finalScore }) {
  const normalizedStatus = toStatusObject(status);
  const sessionKey = String(sessionStatus || "").trim().toLowerCase();
  if (sessionKey === "selected") return { key: "selected", label: "Selected", tone: "success" };
  if (sessionKey === "rejected") return { key: "rejected", label: "Rejected", tone: "danger" };
  if (normalizedStatus.key === "rejected") return { key: "rejected", label: "Rejected", tone: "danger" };
  if (shortlisted || normalizedStatus.key === "shortlisted" || normalizedStatus.key === "interview_scheduled")
    return { key: "shortlisted", label: "Shortlisted", tone: "success" };
  if (normalizedStatus.key === "completed" && typeof finalScore === "number" && finalScore >= 75)
    return { key: "selected", label: "Selected", tone: "success" };
  return { key: "pending", label: "Pending", tone: "secondary" };
}

function normalizeCandidateSummary(item) {
  const status = toStatusObject(item?.stage || item?.status);
  const decision = item?.recommendation
    ? { key: String(item.recommendation).toLowerCase().replace(/\s+/g, "_"), label: item.recommendation, tone: item.recommended ? "success" : "primary" }
    : deriveDecision({ status, shortlisted: false, sessionStatus: status.key, finalScore: item?.final_score ?? item?.score });
  const resumeScore = Number(item?.score || 0);
  const finalAIScore = Number((item?.final_score ?? item?.score) || 0);
  return {
    ...item,
    uid: item?.candidate_uid,
    candidate_uid: item?.candidate_uid,
    avatar: buildAvatar(item?.name),
    role: item?.job?.title || item?.assigned_jd?.title || "Candidate",
    assignedJd: item?.assigned_jd || null,
    resumeScore,
    score: resumeScore,
    finalAIScore,
    matchPercent: Math.round(Number(item?.score ?? item?.final_score ?? 0) || 0),
    interviewStatus: status,
    status,
    finalDecision: decision,
    recommendationTag: item?.recommendation || decision?.label,
    hrNotes: item?.hr_notes || "",
  };
}

function normalizeApplication(application) {
  const explanation = application?.explanation || {};
  const interviewScoring = explanation?.interview_scoring || {};
  const status = toStatusObject(application?.stage || application?.status);
  const breakdown = application?.score_breakdown || {};
  const decision = application?.recommendation
    ? { key: String(application.recommendation).toLowerCase().replace(/\s+/g, "_"), label: application.recommendation, tone: "primary" }
    : deriveDecision({ status, shortlisted: application?.shortlisted, sessionStatus: application?.latest_session?.status, finalScore: application?.final_score ?? interviewScoring?.final_score });
  return {
    ...application,
    explanation,
    status,
    stage: status,
    finalDecision: decision,
    resumeScore: typeof explanation?.final_resume_score === "number" ? explanation.final_resume_score : typeof application?.score === "number" ? application.score : 0,
    semanticScore: typeof explanation?.semantic_score === "number" ? explanation.semantic_score : 0,
    skillMatchScore: typeof breakdown?.skills_match_score === "number" ? breakdown.skills_match_score : typeof explanation?.matched_percentage === "number" ? explanation.matched_percentage : typeof explanation?.weighted_skill_score === "number" ? explanation.weighted_skill_score : 0,
    interviewScore: typeof breakdown?.interview_performance_score === "number" ? breakdown.interview_performance_score : typeof interviewScoring?.technical_score === "number" ? interviewScoring.technical_score : null,
    communicationScore: typeof breakdown?.communication_behavior_score === "number" ? breakdown.communication_behavior_score : null,
    finalAIScore: typeof application?.final_score === "number" ? application.final_score : typeof interviewScoring?.final_score === "number" ? interviewScoring.final_score : typeof application?.score === "number" ? application.score : 0,
    recommendationTag: application?.recommendation || decision?.label,
  };
}

function normalizeCandidateDetail(data) {
  const applications = (data?.applications || []).map(normalizeApplication).map((application) => ({
    ...application,
    hrNotes: application?.hr_notes || "",
  }));
  const latestApplication = applications[0] || null;
  const candidate = data?.candidate || {};
  const skillGap = data?.skill_gap || null;
  const resumeAdvice = data?.resume_advice || null;
  return {
    ...data,
    candidate: {
      ...candidate,
      uid: candidate?.candidate_uid,
      avatar: buildAvatar(candidate?.name),
      role: latestApplication?.job?.title || candidate?.assigned_jd?.title || "Candidate",
      finalDecision: latestApplication?.finalDecision || deriveDecision({ status: candidate?.current_stage || candidate?.current_status }),
      currentStage: toStatusObject(candidate?.current_stage || candidate?.current_status),
      resumeScore: latestApplication?.resumeScore ?? 0,
      semanticScore: latestApplication?.semanticScore ?? 0,
      skillMatchScore: latestApplication?.skillMatchScore ?? 0,
      interviewScore: latestApplication?.interviewScore ?? null,
      communicationScore: latestApplication?.communicationScore ?? null,
      finalAIScore: latestApplication?.finalAIScore ?? candidate?.final_score ?? 0,
      matchPercent: Math.round(Number(skillGap?.match_percentage ?? latestApplication?.score ?? latestApplication?.finalAIScore ?? 0) || 0),
      matchedSkills: skillGap?.matched_skills || latestApplication?.explanation?.matched_skills || [],
      missingSkills: skillGap?.missing_skills || latestApplication?.explanation?.missing_skills || [],
      strengths: resumeAdvice?.strengths || [],
      rewriteTips: resumeAdvice?.rewrite_tips || [],
      parsedResume: candidate?.parsed_resume || {},
      recommendationTag: candidate?.recommendation || latestApplication?.recommendationTag || latestApplication?.finalDecision?.label,
      assignedJd: candidate?.assigned_jd || null,
      hrNotes: candidate?.hr_notes || latestApplication?.hrNotes || "",
      resume_path: candidate?.resume_path || null,
    },
    applications,
    resume_advice: resumeAdvice,
    skill_gap: skillGap,
  };
}

// ── Auth ─────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (payload) => request({ method: "post", url: "/auth/login", data: { email: payload.email, password: payload.password, role: payload.role } }),
  signup: (payload) => request({ method: "post", url: "/auth/signup", data: payload }),
  logout: () => request({ method: "post", url: "/auth/logout" }),
  me: () => request({ method: "get", url: "/auth/me" }),
  updateProfile: (name, extras = {}) => request({ method: "put", url: "/auth/profile", data: { name, ...extras } }),
  changePassword: (currentPassword, newPassword) => request({ method: "post", url: "/auth/change-password", data: { current_password: currentPassword, new_password: newPassword } }),
  forgotPassword: (email) => request({ method: "post", url: "/auth/forgot-password", data: { email } }),
  resetPassword: (token, newPassword) => request({ method: "post", url: "/auth/reset-password", data: { token, new_password: newPassword } }),
  getPreferences: () => request({ method: "get", url: "/auth/preferences" }),
  savePreferences: (preferences) => request({ method: "post", url: "/auth/preferences", data: { preferences } }),
  uploadAvatar: (file) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post("/auth/avatar", formData, { withCredentials: true }).then((r) => r.data);
  },
};

// ── Candidate ────────────────────────────────────────────────────────────────
export const candidateApi = {
  dashboard: (jobId) => request({ method: "get", url: "/candidate/dashboard", params: jobId ? { job_id: jobId } : undefined }),
  jds: () => request({ method: "get", url: "/candidate/jds" }),
  selectJd: (jdId) => request({ method: "post", url: "/candidate/select-jd", data: { jd_id: jdId } }),
  uploadResume: async (file, jobId, onProgress) => {
    try {
      console.log("[UPLOAD] Starting resume upload, file:", file?.name, "jobId:", jobId);
      
      if (isProduction) {
        const s3Url = await uploadFileToS3(file, onProgress);
        const response = await apiClient.post("/candidate/upload-resume-s3", 
          { resume_url: s3Url, job_id: jobId },
          { headers: { "Content-Type": "application/json" } }
        );
        return response.data;
      }
      
      const formData = new FormData();
      formData.append("resume", file);
      if (jobId) formData.append("job_id", String(jobId));
      
      const response = await apiClient.post("/candidate/upload-resume", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return response.data;
    } catch (err) {
      console.error("[UPLOAD] Resume upload failed:", err.message);
      throw err;
    }
  },
  scheduleInterview: (resultId, interviewDate) => request({ method: "post", url: "/candidate/select-interview-date", data: { result_id: resultId, interview_date: interviewDate } }),
  regenerateQuestions: (resultId) => request({ method: "post", url: "/candidate/regenerate-questions", data: { result_id: resultId } }),
  practiceKit: (jobId) => request({ method: "get", url: "/candidate/practice-kit", params: jobId ? { job_id: jobId } : undefined }),
  allResults: () => request({ method: "get", url: "/candidate/all-results" }),
  
  // FAQ
  getQuestions: (status) => request({ method: "get", url: "/faq/questions", params: status ? { status } : undefined }),
  submitQuestion: (question, jobId) => request({ method: "post", url: "/faq/questions", data: { question, job_id: jobId } }),
  getPendingQuestions: () => request({ method: "get", url: "/faq/questions/pending" }),
  answerQuestion: (questionId, answer) => request({ method: "post", url: `/faq/questions/${questionId}/answer`, data: { answer } }),
  dismissQuestion: (questionId) => request({ method: "post", url: `/faq/questions/${questionId}/dismiss` }),
};

// ── HR ───────────────────────────────────────────────────────────────────────
export const hrApi = {
  dashboard: (jobId) => request({ method: "get", url: "/hr/dashboard", params: jobId ? { job_id: jobId } : undefined }),
  calendar: (params) => request({ method: "get", url: "/hr/dashboard/calendar", params }),

  // JDs
  listJds: () => request({ method: "get", url: "/hr/jds" }),
  getJd: (jdId) => request({ method: "get", url: `/hr/jds/${jdId}` }),
  createJd: (payload) => request({ method: "post", url: "/hr/jds", data: payload }),
  updateJd: (jdId, payload) => request({ method: "put", url: `/hr/jds/${jdId}`, data: payload }),
  toggleJdActive: (jdId) => request({ method: "post", url: `/hr/jds/${jdId}/toggle-active` }),
  deleteJd: (jdId) => request({ method: "delete", url: `/hr/jds/${jdId}` }),

  // JD file upload + LLM extraction (skills + requirements)
  uploadJd: (file) => {
    const formData = new FormData();
    formData.append("jd_file", file);
    return request({ method: "post", url: "/hr/upload-jd", data: formData });
  },
  // Parse JD text (for pasted text - extracts skills + requirements)
  parseJdText: (jdText, jdTitle = "") => {
    const formData = new FormData();
    formData.append("jd_text", jdText);
    formData.append("jd_title", jdTitle);
    return request({ method: "post", url: "/hr/parse-jd-text", data: formData });
  },
  confirmJd: (payload) => request({ method: "post", url: "/hr/confirm-jd", data: payload }),
  updateSkillWeights: (payload) => request({ method: "post", url: "/hr/update-skill-weights", data: payload }),

  // Candidates
  candidacy: (params = {}) => {
    const response = request({ method: "get", url: "/hr/candidates", params });
    return response;
  },
  candidates: (params = {}) => hrApi.listCandidates(params),
  async listCandidates(params = {}) {
    const response = await request({ method: "get", url: "/hr/candidates", params });
    return { ...response, candidates: (response?.candidates || []).map(normalizeCandidateSummary) };
  },
  async allApplications(params = {}) {
    const response = await request({ method: "get", url: "/hr/applications", params });
    return { ...response, applications: (response?.applications || []).map(normalizeApplication) };
  },
  async candidateDetail(candidateUid) {
    const response = await request({ method: "get", url: `/hr/candidates/${candidateUid}` });
    return normalizeCandidateDetail(response);
  },
  async batchCandidateDetails(candidateUids) {
    const response = await request({ method: "post", url: "/hr/candidates/batch-details", data: { candidate_uids: candidateUids } });
    return response;
  },
  skillGap: (candidateUid, jobId) => request({ method: "get", url: `/hr/candidates/${candidateUid}/skill-gap`, params: jobId ? { job_id: jobId } : undefined }),
  deleteCandidate: (candidateUid) => request({ method: "post", url: `/hr/candidates/${candidateUid}/delete` }),
  updateCandidateStage: (resultId, payload) => request({ method: "post", url: `/hr/results/${resultId}/stage`, data: payload }),
  rankedCandidates: (params) => request({ method: "get", url: "/hr/candidates/ranked", params }),
  compareCandidates: (resultIds) => request({ method: "post", url: "/hr/candidates/compare", data: { result_ids: resultIds } }),
  assignCandidateToJd: (candidateUid, jdId) => request({ method: "post", url: `/hr/candidates/${candidateUid}/assign-jd`, data: { jd_id: jdId } }),
  updateCandidateNotes: (resultId, notes) => request({ method: "post", url: `/hr/results/${resultId}/notes`, data: { notes } }),

  // Interviews
  interviews: () => request({ method: "get", url: "/hr/interviews" }),
  interviewDetail: (interviewId) => request({ method: "get", url: `/hr/interviews/${interviewId}` }),
  finalizeInterview: (interviewId, payload) => request({ method: "post", url: `/hr/interviews/${interviewId}/finalize`, data: payload }),
  // FIX C1: Added missing reEvaluateInterview — was causing JS crash on HR interview review page
  reEvaluateInterview: (interviewId) => request({ method: "post", url: `/hr/interviews/${interviewId}/re-evaluate` }),
  proctoringTimeline: (sessionId) => request({ method: "get", url: `/hr/proctoring/${sessionId}` }),

  // Backup
  async localBackup() {
    const response = await apiClient({ method: "get", url: "/hr/local-backup", responseType: "blob" });
    return response.data;
  },
  
  // FAQ Management
  getPendingQuestions: () => request({ method: "get", url: "/faq/questions/pending" }),
  answerQuestion: (questionId, answer) => request({ method: "post", url: `/faq/questions/${questionId}/answer`, data: { answer } }),
  dismissQuestion: (questionId) => request({ method: "post", url: `/faq/questions/${questionId}/dismiss` }),
  getAllFAQQuestions: () => request({ method: "get", url: "/faq/admin/questions" }),
  answerFAQQuestion: (questionId, payload) => request({ method: "post", url: `/faq/questions/${questionId}/answer`, data: payload }),
  updateFAQQuestion: (questionId, payload) => request({ method: "put", url: `/faq/questions/${questionId}`, data: payload }),
  dismissFAQQuestion: (questionId) => request({ method: "post", url: `/faq/questions/${questionId}/dismiss` }),
};

// ── Interview ─────────────────────────────────────────────────────────────────
export const interviewApi = {
  access: (resultId) => request({ method: "get", url: `/interview/${resultId}/access` }),
  start: (payload) => request({ method: "post", url: "/interview/start", data: payload }),
  tts: (text, voice = "kajal") => request({ method: "post", url: "/interview/tts", data: { text, voice } }),
  submitAnswer: (payload) => request({ method: "post", url: "/interview/answer", data: payload }),
  transcribe: (formData) => request({ method: "post", url: "/interview/transcribe", data: formData }),
  uploadRecording: (sessionId, formData) => request({ method: "post", url: `/interview/${sessionId}/recording`, data: formData, timeout: 300000 }),
  logEvent: (targetId, payload) => request({ method: "post", url: `/interview/${targetId}/event`, data: payload }),
  evaluate: (sessionId) => request({ method: "post", url: `/interview/${sessionId}/evaluate` }),
  sessionSummary: (sessionId) => request({ method: "get", url: `/interview/session/${sessionId}/summary` }),
  submitFeedback: (sessionId, payload) => request({ method: "post", url: `/interview/${sessionId}/feedback`, data: payload }),
};

export const proctorApi = {
  uploadFrame: (sessionId, frameData, eventType = "scan") => {
    const formData = new FormData();
    formData.append("file", frameData, "frame.jpg");
    formData.append("session_id", String(sessionId));
    formData.append("event_type", eventType);
    return request({ method: "post", url: "/proctor/frame", data: formData });
  },
};

