/**
 * ProctoringTimeline.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Reusable HR component that renders a full proctoring event timeline.
 * Handles all event types:
 *   • Face events      (no_face, multi_face, face_mismatch, baseline)
 *   • Tab switch       (tab_switch)
 *   • Emotion signals  (emotion — from candidate frontend)
 *   • Voice confidence (voice_confidence — from candidate frontend)
 *   • Motion           (high_motion)
 *   • Warnings         (warning_issued, pause_enforced)
 *
 * Usage:
 *   <ProctoringTimeline events={events} sessionInfo={session} />
 */

import { useMemo, useState } from "react";
import {
  AlertTriangle, Camera, Eye, Filter,
  MessageCircle, Brain, Mic, Monitor,
  CheckCircle2, XCircle, Clock,
} from "lucide-react";
import { cn } from "../utils/utils";
import { formatDateTime } from "../utils/formatters";

// ── event type config ─────────────────────────────────────────────────────────
const EVENT_CONFIG = {
  // Face
  no_face:           { label: "No Face",         icon: XCircle,       color: "red",    group: "face"   },
  multi_face:        { label: "Multiple Faces",   icon: AlertTriangle, color: "red",    group: "face"   },
  face_mismatch:     { label: "Face Mismatch",    icon: AlertTriangle, color: "red",    group: "face"   },
  baseline:          { label: "Baseline Set",     icon: CheckCircle2,  color: "green",  group: "face"   },
  baseline_no_face:  { label: "Baseline No Face", icon: XCircle,       color: "amber",  group: "face"   },
  // Motion
  high_motion:       { label: "High Motion",      icon: AlertTriangle, color: "amber",  group: "motion" },
  periodic:          { label: "Scan",             icon: Eye,           color: "slate",  group: "scan"   },
  // Warnings
  warning_issued:    { label: "Warning Issued",   icon: AlertTriangle, color: "red",    group: "warning"},
  pause_enforced:    { label: "Pause Enforced",   icon: Clock,         color: "red",    group: "warning"},
  // New events from frontend hook
  tab_switch:        { label: "Tab Switch",       icon: Monitor,       color: "red",    group: "behavior"},
  emotion:           { label: "Emotion Signal",   icon: Brain,         color: "blue",   group: "emotion"},
  voice_confidence:  { label: "Voice Confidence", icon: Mic,           color: "green",  group: "voice"  },
};

const COLOR_CLASSES = {
  red:   { bg: "bg-red-500/10",   border: "border-red-500/30",   text: "text-red-400",    icon: "text-red-400"    },
  amber: { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-400",  icon: "text-amber-400"  },
  green: { bg: "bg-emerald-500/10",border:"border-emerald-500/30",text:"text-emerald-400",icon: "text-emerald-400"},
  blue:  { bg: "bg-blue-500/10",  border: "border-blue-500/30",  text: "text-blue-400",   icon: "text-blue-400"   },
  slate: { bg: "bg-slate-800/40", border: "border-slate-700/50", text: "text-slate-400",  icon: "text-slate-500"  },
};

// Groups for filter tabs
const GROUPS = [
  { id: "all",      label: "All"      },
  { id: "face",     label: "Face"     },
  { id: "behavior", label: "Behavior" },
  { id: "emotion",  label: "Emotion"  },
  { id: "voice",    label: "Voice"    },
  { id: "motion",   label: "Motion"   },
  { id: "warning",  label: "Warnings" },
];

function getConfig(eventType) {
  const key = (eventType || "").toLowerCase().replace(/-/g, "_");
  return EVENT_CONFIG[key] || {
    label: eventType,
    icon: Eye,
    color: "slate",
    group: "scan",
  };
}

function EventRow({ event }) {
  const cfg     = getConfig(event.event_type);
  const colors  = COLOR_CLASSES[cfg.color] || COLOR_CLASSES.slate;
  const Icon    = cfg.icon;
  const meta    = event.meta_json || {};

  // Build a detail string based on event type
  let detail = "";
  if (event.event_type === "tab_switch")        detail = "Candidate switched browser tab";
  else if (event.event_type === "emotion")      detail = `${meta.emotion || "—"} (${Math.round((meta.confidence || 0) * 100)}% confidence)`;
  else if (event.event_type === "voice_confidence") {
    detail = `${meta.speaking_rate || "—"} wpm · confidence ${Math.round((meta.confidence_score || 0) * 100)}%`;
  }
  else if (meta.faces_count != null)            detail = `${meta.faces_count} face${meta.faces_count !== 1 ? "s" : ""} detected`;
  else if (meta.motion_score != null)           detail = `Motion score ${Number(meta.motion_score).toFixed(2)}`;

  return (
    <div className={cn(
      "flex items-start gap-3 px-4 py-3 rounded-xl border transition-all",
      colors.bg, colors.border
    )}>
      <div className={cn("flex-shrink-0 mt-0.5", colors.icon)}>
        <Icon size={16} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className={cn("text-xs font-black", colors.text)}>{cfg.label}</span>
          <span className="text-[10px] text-slate-500 flex-shrink-0">{formatDateTime(event.created_at)}</span>
        </div>
        {detail && <p className="text-[11px] text-slate-400 mt-0.5">{detail}</p>}
        {event.image_url && (
          <a href={event.image_url} target="_blank" rel="noreferrer"
            className="inline-flex items-center gap-1 text-[10px] text-blue-400 hover:underline mt-1">
            <Camera size={11} />View snapshot
          </a>
        )}
      </div>
      {event.score != null && (
        <span className={cn("text-[10px] font-black flex-shrink-0", colors.text)}>
          {Number(event.score).toFixed(1)}
        </span>
      )}
    </div>
  );
}

// ── summary stats ─────────────────────────────────────────────────────────────
function SummaryCard({ label, value, color = "slate", icon: Icon }) {
  const colors = COLOR_CLASSES[color] || COLOR_CLASSES.slate;
  return (
    <div className={cn("rounded-xl border p-3 flex items-center gap-3", colors.bg, colors.border)}>
      {Icon && <Icon size={18} className={colors.icon} />}
      <div>
        <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{label}</p>
        <p className={cn("text-xl font-black", colors.text)}>{value}</p>
      </div>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────
export default function ProctoringTimeline({ events = [] }) {
  const [activeGroup, setActiveGroup] = useState("all");

  const stats = useMemo(() => {
    const tabSwitches    = events.filter((e) => e.event_type === "tab_switch").length;
    const noFace         = events.filter((e) => e.event_type === "no_face").length;
    const multiFace      = events.filter((e) => e.event_type === "multi_face").length;
    const warnings       = events.filter((e) => ["warning_issued", "pause_enforced"].includes(e.event_type)).length;
    const emotionEvents  = events.filter((e) => e.event_type === "emotion");
    const voiceEvents    = events.filter((e) => e.event_type === "voice_confidence");

    // Average voice confidence
    const avgVoiceConf = voiceEvents.length
      ? (voiceEvents.reduce((s, e) => s + ((e.meta_json?.confidence_score) || 0), 0) / voiceEvents.length)
      : null;

    // Dominant emotion
    const emotionCounts = {};
    emotionEvents.forEach((e) => {
      const em = e.meta_json?.emotion || "unknown";
      emotionCounts[em] = (emotionCounts[em] || 0) + 1;
    });
    const dominantEmotion = Object.keys(emotionCounts).sort(
      (a, b) => emotionCounts[b] - emotionCounts[a]
    )[0] || null;

    return { tabSwitches, noFace, multiFace, warnings, avgVoiceConf, dominantEmotion };
  }, [events]);

  const filteredEvents = useMemo(() => {
    if (activeGroup === "all") return events;
    return events.filter((e) => {
      const cfg = getConfig(e.event_type);
      return cfg.group === activeGroup;
    });
  }, [events, activeGroup]);

  return (
    <div className="space-y-6">

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <SummaryCard label="Total Events"   value={events.length}             color="slate"  icon={Eye}           />
        <SummaryCard label="Tab Switches"   value={stats.tabSwitches}         color={stats.tabSwitches > 0 ? "red" : "slate"} icon={Monitor} />
        <SummaryCard label="No Face"        value={stats.noFace}              color={stats.noFace > 0 ? "amber" : "slate"} icon={XCircle} />
        <SummaryCard label="Multi-Face"     value={stats.multiFace}           color={stats.multiFace > 0 ? "red" : "slate"} icon={AlertTriangle} />
        <SummaryCard label="Warnings"       value={stats.warnings}            color={stats.warnings > 0 ? "red" : "slate"} icon={AlertTriangle} />
        <SummaryCard
          label="Dominant Emotion"
          value={stats.dominantEmotion ? stats.dominantEmotion : "—"}
          color="blue"
          icon={Brain}
        />
      </div>

      {/* Voice confidence summary */}
      {stats.avgVoiceConf !== null && (
        <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-3 flex items-center gap-3">
          <Mic size={18} className="text-emerald-400" />
          <div>
            <p className="text-xs font-black text-emerald-300">Average Voice Confidence</p>
            <p className="text-sm text-emerald-400">
              {Math.round(stats.avgVoiceConf * 100)}% —{" "}
              {stats.avgVoiceConf >= 0.7 ? "Candidate appeared confident overall" :
               stats.avgVoiceConf >= 0.45 ? "Moderate confidence with some hesitation" :
               "Candidate showed signs of significant hesitation"}
            </p>
          </div>
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter size={14} className="text-slate-500 flex-shrink-0" />
        {GROUPS.map((g) => {
          const count = g.id === "all"
            ? events.length
            : events.filter((e) => getConfig(e.event_type).group === g.id).length;
          if (count === 0 && g.id !== "all") return null;
          return (
            <button
              key={g.id}
              type="button"
              onClick={() => setActiveGroup(g.id)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-black border transition-all",
                activeGroup === g.id
                  ? "bg-blue-600 border-blue-600 text-white"
                  : "bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600"
              )}
            >
              {g.label}
              <span className="ml-1.5 opacity-70">{count}</span>
            </button>
          );
        })}
      </div>

      {/* Event list */}
      <div className="space-y-2">
        {filteredEvents.length === 0 && (
          <div className="text-center py-12 text-slate-600">
            <Eye size={32} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm font-bold uppercase tracking-widest">No events in this category</p>
          </div>
        )}
        {filteredEvents.map((ev, i) => (
          <EventRow key={ev.id || i} event={ev} />
        ))}
      </div>
    </div>
  );
}
