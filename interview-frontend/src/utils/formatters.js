export function screeningBandLabel(band) {
  if (band === "strong_shortlist") return "Strong Shortlist";
  if (band === "review_shortlist") return "Review Shortlist";
  if (band === "reject") return "Reject";
  return "Not evaluated";
}

export function formatPercent(value, fallback = "Pending") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return fallback;
  }
  return `${Number(value).toFixed(2)}%`;
}

export function formatScoreValue(value, fallback = "0.00") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return fallback;
  }
  return Number(value).toFixed(2);
}

export function formatDateTime(value) {
  if (!value) return "N/A";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

function parseDate(value, { assumeUtc = false } = {}) {
  if (!value) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  let raw = String(value).trim();
  if (!raw) return null;

  // Backward compatibility: some backend UTC fields were serialized without trailing timezone.
  if (assumeUtc && /T/.test(raw) && !/(Z|[+-]\d{2}:\d{2})$/.test(raw)) {
    raw = `${raw}Z`;
  }

  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatUtcDateTime(value, fallback = "Pending") {
  const date = parseDate(value, { assumeUtc: true });
  if (!date) return fallback;
  return date.toLocaleString();
}

export function resolveInterviewDateTime(source) {
  if (!source) return null;
  const rawUtc = source.interview_datetime_utc;
  const rawDateTime = source.interview_datetime;
  const rawDate = source.interview_date;

  const utcDate = parseDate(rawUtc, { assumeUtc: true });
  if (utcDate) return utcDate;

  // interview_datetime is stored as UTC on backend and should be treated as UTC when no suffix exists.
  const interviewDateTime = parseDate(rawDateTime, { assumeUtc: true });
  if (interviewDateTime) return interviewDateTime;

  return parseDate(rawDate, { assumeUtc: false });
}

export function formatInterviewDateTimeLocal(source, fallback = "Pending") {
  const date = resolveInterviewDateTime(source);
  if (!date) return fallback;
  return date.toLocaleString();
}

export function toDateTimeLocalInputValue(source) {
  const date = source instanceof Date ? source : resolveInterviewDateTime(source);
  if (!date) return "";
  const pad = (value) => String(value).padStart(2, "0");
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function toGoogleUtcStamp(date) {
  return date.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
}

export function getGoogleCalendarDateRange(source, durationMinutes = 60) {
  const date = source instanceof Date ? source : resolveInterviewDateTime(source);
  if (!date) return null;
  const endDate = new Date(date.getTime() + durationMinutes * 60 * 1000);
  return {
    startUtc: toGoogleUtcStamp(date),
    endUtc: toGoogleUtcStamp(endDate),
  };
}

export function titleCase(value) {
  return String(value || "")
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}
