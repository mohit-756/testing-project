export const ATS_STAGE_DEFINITIONS = [
  { key: "applied", label: "Applied", tone: "secondary" },
  { key: "screening", label: "Screening", tone: "warning" },
  { key: "shortlisted", label: "Shortlisted", tone: "success" },
  { key: "interview_scheduled", label: "Scheduled", tone: "primary" },
  { key: "interview_completed", label: "Completed", tone: "dark" },
  { key: "selected", label: "Selected", tone: "success" },
  { key: "rejected", label: "Rejected", tone: "danger" },
];

export const ATS_STAGE_KEYS = ATS_STAGE_DEFINITIONS.map((stage) => stage.key);
export const ATS_STAGE_OPTIONS = ATS_STAGE_DEFINITIONS.map((stage) => ({ value: stage.key, label: stage.label }));

export const STATUS_MAP = new Map([
  ["applied", { key: "applied", label: "Applied", tone: "secondary" }],
  ["screening", { key: "screening", label: "Screening", tone: "warning" }],
  ["shortlisted", { key: "shortlisted", label: "Shortlisted", tone: "success" }],
  ["interview_scheduled", { key: "interview_scheduled", label: "Scheduled", tone: "primary" }],
  ["interview_completed", { key: "interview_completed", label: "Completed", tone: "dark" }],
  ["selected", { key: "selected", label: "Selected", tone: "success" }],
  ["rejected", { key: "rejected", label: "Rejected", tone: "danger" }],
]);

export function normalizeStageKey(value, fallback = "applied") {
  const key = String(value || "").trim().toLowerCase();
  return ATS_STAGE_KEYS.includes(key) ? key : fallback;
}

export function toStatusObject(status) {
  if (status && typeof status === "object" && status.label) return status;
  const raw = String(status || "").trim().toLowerCase();
  const mapped = STATUS_MAP.get(raw);
  if (mapped) return mapped;
  return {
    key: raw || "unknown",
    label: raw
      ? raw
          .split(/[_\s-]+/)
          .filter(Boolean)
          .map((word) => word[0].toUpperCase() + word.slice(1))
          .join(" ")
      : "Unknown",
    tone: "secondary",
  };
}