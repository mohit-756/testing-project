import { useState } from "react";
import { CheckCircle2, XCircle, TrendingUp, ChevronRight, Zap } from "lucide-react";
import { cn } from "../utils/utils";

/**
 * AnswerFeedback
 * Shown immediately after a candidate submits an answer.
 * Props:
 *   feedback: { overall_score, relevance, completeness, clarity, time_fit, word_count, grade, grade_color }
 *   onContinue: () => void   -- called when candidate is ready for next question
 *   isLastQuestion: bool
 */

function ScoreArc({ score }) {
  const r = 36;
  const circumference = 2 * Math.PI * r;
  const filled = (score / 100) * circumference;
  const color =
    score >= 80 ? "#10b981" : score >= 60 ? "#3b82f6" : score >= 40 ? "#f59e0b" : "#ef4444";

  return (
    <svg width="96" height="96" viewBox="0 0 96 96" className="rotate-[-90deg]">
      <circle cx="48" cy="48" r={r} fill="none" stroke="currentColor" strokeWidth="8"
        className="text-slate-100 dark:text-slate-800" />
      <circle cx="48" cy="48" r={r} fill="none" stroke={color} strokeWidth="8"
        strokeDasharray={`${filled} ${circumference}`} strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.8s ease" }} />
    </svg>
  );
}

function Bar({ label, value, color }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{label}</span>
        <span className="text-xs font-black text-slate-700 dark:text-slate-300">{Math.round(value)}%</span>
      </div>
      <div className="h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${Math.round(value)}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

const GRADE_CONFIG = {
  Strong:     { bg: "bg-emerald-50 dark:bg-emerald-900/20", text: "text-emerald-700 dark:text-emerald-400", border: "border-emerald-200 dark:border-emerald-800/50", icon: CheckCircle2, color: "#10b981" },
  Good:       { bg: "bg-blue-50 dark:bg-blue-900/20",    text: "text-blue-700 dark:text-blue-400",    border: "border-blue-200 dark:border-blue-800/50",    icon: TrendingUp,  color: "#3b82f6" },
  "Needs work": { bg: "bg-amber-50 dark:bg-amber-900/20",  text: "text-amber-700 dark:text-amber-400",  border: "border-amber-200 dark:border-amber-800/50",  icon: Zap,         color: "#f59e0b" },
  Weak:       { bg: "bg-red-50 dark:bg-red-900/20",      text: "text-red-700 dark:text-red-400",      border: "border-red-200 dark:border-red-800/50",      icon: XCircle,     color: "#ef4444" },
};

function scoreToGrade(score) {
  if (score >= 80) return "Strong";
  if (score >= 60) return "Good";
  if (score >= 40) return "Needs work";
  return "Weak";
}

const TIPS = {
  relevance: {
    low:  "Try to directly answer what was asked — use keywords from the question itself.",
    high: "Great relevance — you addressed the question directly.",
  },
  completeness: {
    low:  "Add a concrete example or measurable outcome to strengthen your answer.",
    high: "Solid depth — you covered the topic with enough detail.",
  },
  clarity: {
    low:  "Vary your sentence structure and avoid repeating the same words.",
    high: "Clear and well-structured answer.",
  },
  time_fit: {
    low:  "Try to pace yourself — aim to use 40–90% of the allotted time.",
    high: "Good time management.",
  },
};

function getTip(key, value) {
  return value < 55 ? TIPS[key].low : TIPS[key].high;
}

export default function AnswerFeedback({ feedback, onContinue, isLastQuestion }) {
  const [expanded, setExpanded] = useState(false);

  if (!feedback) return null;

  const score = Math.round(feedback.overall_score ?? 0);
  const grade = scoreToGrade(score);
  const cfg = GRADE_CONFIG[grade] ?? GRADE_CONFIG["Good"];
  const GradeIcon = cfg.icon;

  const bars = [
    { label: "Relevance",    value: feedback.relevance    ?? 0, color: "#3b82f6" },
    { label: "Completeness", value: feedback.completeness ?? 0, color: "#8b5cf6" },
    { label: "Clarity",      value: feedback.clarity      ?? 0, color: "#06b6d4" },
    { label: "Time fit",     value: feedback.time_fit     ?? 0, color: "#10b981" },
  ];

  const weakAreas = [
    { key: "relevance",    value: feedback.relevance    ?? 0 },
    { key: "completeness", value: feedback.completeness ?? 0 },
    { key: "clarity",      value: feedback.clarity      ?? 0 },
    { key: "time_fit",     value: feedback.time_fit     ?? 0 },
  ].filter(({ value }) => value < 70);

  return (
    <div className={cn(
      "rounded-3xl border p-6 space-y-5 animate-in fade-in slide-in-from-bottom-2 duration-300",
      cfg.bg, cfg.border
    )}>
      {/* Header row */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="relative w-24 h-24 flex items-center justify-center flex-shrink-0">
            <ScoreArc score={score} />
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-black text-slate-900 dark:text-white leading-none">{score}</span>
              <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">score</span>
            </div>
          </div>
          <div>
            <div className={cn("inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-black border mb-1", cfg.bg, cfg.text, cfg.border)}>
              <GradeIcon size={14} />
              {grade}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {feedback.word_count ? `${feedback.word_count} words` : "Answer recorded"}
            </p>
          </div>
        </div>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-xs font-bold text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
        >
          {expanded ? "Less" : "Details"}
        </button>
      </div>

      {/* Score breakdown bars */}
      {expanded && (
        <div className="space-y-3 pt-1">
          {bars.map(({ label, value, color }) => (
            <Bar key={label} label={label} value={value} color={color} />
          ))}
        </div>
      )}

      {/* Tips for weak areas */}
      {weakAreas.length > 0 && (
        <div className="space-y-2">
          {weakAreas.slice(0, 2).map(({ key, value }) => (
            <p key={key} className={cn("text-xs font-medium leading-relaxed flex items-start gap-1.5", cfg.text)}>
              <span className="mt-0.5 flex-shrink-0">→</span>
              {getTip(key, value)}
            </p>
          ))}
        </div>
      )}

      {/* Continue button */}
      <button
        onClick={onContinue}
        className={cn(
          "w-full flex items-center justify-center gap-2 py-3.5 rounded-2xl font-black text-sm transition-all active:scale-[0.98]",
          "bg-slate-900 dark:bg-white text-white dark:text-slate-900 hover:opacity-90 shadow-lg"
        )}
      >
        <span>{isLastQuestion ? "Finish interview" : "Next question"}</span>
        <ChevronRight size={16} />
      </button>
    </div>
  );
}
