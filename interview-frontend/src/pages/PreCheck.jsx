import React, { useRef, useState, useEffect, useId } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Camera, Mic, Wifi, CheckCircle2, AlertCircle, Play,
  ShieldCheck, Video, Settings, AlertTriangle, Lock, Mail, Volume2, AlertOctagon, MonitorUp
} from "lucide-react";
import { interviewApi } from "../services/api";
import { useAuth } from "../context/useAuth";
import { formatUtcDateTime } from "../utils/formatters";
import { cn } from "../utils/utils";
import HelpSupportButton from "../components/HelpSupportButton";
import { useAnnounce } from "../hooks/useAccessibility";

async function attachPreviewStream(videoElement, stream) {
  if (!videoElement) return;
  videoElement.srcObject = stream;
  videoElement.muted = true;
  videoElement.playsInline = true;
  try {
    await videoElement.play();
  } catch {
    await new Promise((resolve) => {
      const timeoutId = window.setTimeout(resolve, 500);
      videoElement.onloadedmetadata = () => { window.clearTimeout(timeoutId); resolve(); };
    });
    try { await videoElement.play(); } catch { }
  }
}

function checkMediaRecorderSupport() {
  if (typeof window === "undefined") return { supported: false, reason: "Non-browser environment." };
  if (typeof window.MediaRecorder === "undefined") {
    return { supported: false, reason: "MediaRecorder API is not supported in this browser." };
  }
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  const supported = candidates.some((type) => {
    try { return window.MediaRecorder.isTypeSupported(type); } catch { return false; }
  });
  if (!supported) {
    return { supported: false, reason: "No supported audio recording format found in this browser." };
  }
  return { supported: true, reason: "" };
}

function InlineLogin({ onSuccess }) {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const emailId = useId();
  const passwordId = useId();
  const errorId = useId();

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login({ email, password, role: "candidate" });
      onSuccess();
    } catch (err) {
      setError(err?.message || "Login failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white dark:bg-slate-900 rounded-3xl shadow-xl border border-slate-200 dark:border-slate-800 p-8 space-y-6">
        <div className="text-center">
          <div className="w-14 h-14 bg-blue-100 dark:bg-blue-900/30 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Lock size={28} className="text-blue-600 dark:text-blue-400" aria-hidden="true" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Sign in to continue</h2>
          <p className="text-slate-500 dark:text-slate-400 mt-2 text-sm">
            Please sign in with your candidate account to access your interview.
          </p>
        </div>

        {error && (
          <div id={errorId} role="alert" className="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 p-3 rounded-xl text-sm border border-red-100 dark:border-red-900/30">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" aria-describedby={error ? errorId : undefined}>
          <div className="relative">
            <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" aria-hidden="true" />
            <label htmlFor={emailId} className="sr-only">Email address</label>
            <input
              id={emailId}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email address"
              required
              autoComplete="email"
              className="w-full pl-11 pr-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:text-white"
            />
          </div>
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" aria-hidden="true" />
            <label htmlFor={passwordId} className="sr-only">Password</label>
            <input
              id={passwordId}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              required
              autoComplete="current-password"
              className="w-full pl-11 pr-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:text-white"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl transition-all disabled:opacity-60"
          >
            {loading ? "Signing in..." : "Sign In & Open Interview"}
          </button>
        </form>
      </div>
      <HelpSupportButton supportEmail="support@quadranttech.com" />
    </div>
  );
}

function MicWarningModal({ isOpen, onClose, onContinue }) {
  if (!isOpen) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="mic-warning-title"
      className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center z-50"
    >
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 max-w-md w-full mx-4 shadow-xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center">
            <AlertOctagon size={20} className="text-amber-500" aria-hidden="true" />
          </div>
          <h3 id="mic-warning-title" className="text-slate-900 dark:text-white font-bold text-lg">Microphone Access Required</h3>
        </div>
        <p className="text-slate-600 dark:text-slate-300 mb-4">
          We couldn't access your microphone. Please allow microphone access in your browser settings, then run the system check again.
        </p>
        <p className="text-slate-500 dark:text-slate-400 text-sm mb-6">
          Don't worry — you can still complete the interview by typing your answers!
        </p>
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-bold rounded-xl hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
          >
            Run System Check Again
          </button>
          <button
            onClick={onContinue}
            className="flex-1 px-4 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition-all"
          >
            Continue Anyway
          </button>
        </div>
      </div>
    </div>
  );
}

function SystemCheckItem({ label, status, detail, icon: Icon }) {
  const statusLabels = {
    granted: "Ready",
    denied: "Blocked",
    pending: "Checking...",
  };

  const statusAria = {
    granted: "passed",
    denied: "failed",
    pending: "not checked",
  };

  const isPending = status === "pending";

  return (
    <div
      className={cn(
        "flex items-center justify-between p-5 rounded-2xl border-2 transition-all",
        status === "granted"
          ? "bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-700"
          : status === "denied"
            ? "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-700"
            : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800"
      )}
      role="listitem"
      aria-label={`${label}: ${statusAria[status]}`}
    >
      <div className="flex items-center space-x-4">
        <div
          className={cn("w-12 h-12 rounded-xl flex items-center justify-center transition-colors",
            status === "granted" ? "bg-emerald-100 dark:bg-emerald-800" : "bg-slate-100 dark:bg-slate-800"
          )}
        >
          <Icon size={20} aria-hidden="true" />
        </div>
        <div>
          <span className="font-bold block text-slate-900 dark:text-white">{label}</span>
          {detail && <span className="text-xs text-slate-500 block">{detail}</span>}
        </div>
      </div>
      <div
        className={cn(
          "px-3 py-1.5 rounded-lg font-bold text-sm flex items-center gap-2",
          status === "granted" ? "bg-emerald-100 dark:bg-emerald-800 text-emerald-700 dark:text-emerald-300" :
          status === "denied" ? "bg-red-100 dark:bg-red-800 text-red-700 dark:text-red-300" :
          "bg-amber-100 dark:bg-amber-800 text-amber-600 dark:text-amber-400 animate-pulse"
        )}
        aria-live="polite"
      >
        {isPending && <span className="w-2 h-2 bg-amber-500 rounded-full animate-bounce" />}
        {statusLabels[status]}
      </div>
    </div>
  );
}

export default function PreCheck() {
  const { resultId } = useParams();
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const displayStreamRef = useRef(null);

  const [checks, setChecks] = useState({
    camera: { status: "pending", label: "Camera access" },
    mic: { status: "pending", label: "Microphone access" },
    screen: { status: "pending", label: "Full screen recording" },
    internet: { status: "granted", label: "Internet connection" },
    voiceRecorder: { status: "pending", label: "Voice recording support" },
  });
  const [isChecking, setIsChecking] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [selectedVoice, setSelectedVoice] = useState(() => {
    const saved = sessionStorage.getItem(`interview-voice:${resultId}`);
    return saved || "kajal";
  });
  const [isTestingVoice, setIsTestingVoice] = useState(false);
  const [showMicWarningModal, setShowMicWarningModal] = useState(false);

  const { announce } = useAnnounce();

  useEffect(() => {
    const { supported, reason } = checkMediaRecorderSupport();
    setChecks((prev) => ({
      ...prev,
      voiceRecorder: {
        status: supported ? "granted" : "denied",
        label: "Voice recording support",
        detail: reason,
      },
    }));
  }, []);

  useEffect(() => {
    const videoElement = videoRef.current;
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      if (videoElement) videoElement.srcObject = null;
    };
  }, []);

  async function requestFullScreenRecording() {
    setError("");
    if (!navigator.mediaDevices?.getDisplayMedia) {
      setChecks((prev) => ({
        ...prev,
        screen: {
          status: "denied",
          label: "Full screen recording",
          detail: "Screen recording is not supported in this browser. Use Chrome or Edge.",
        },
      }));
      announce("Full screen recording is not supported in this browser.", "assertive");
      return;
    }

    try {
      displayStreamRef.current?.getTracks?.().forEach((track) => track.stop());
      const displayStream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: 15 },
        audio: false,
      });
      displayStreamRef.current = displayStream;
      window.__interviewDisplayStream = displayStream;
      sessionStorage.setItem(`interview-screen-recording:${resultId}`, "granted");
      const [track] = displayStream.getVideoTracks();
      if (track) {
        track.onended = () => {
          if (window.__interviewDisplayStream === displayStream) window.__interviewDisplayStream = null;
          sessionStorage.removeItem(`interview-screen-recording:${resultId}`);
          setChecks((prev) => ({
            ...prev,
            screen: {
              status: "denied",
              label: "Full screen recording",
              detail: "Screen sharing was stopped. Enable it again before starting.",
            },
          }));
        };
      }
      setChecks((prev) => ({
        ...prev,
        screen: { status: "granted", label: "Full screen recording", detail: "Enabled for this interview." },
      }));
      announce("Full screen recording enabled.", "assertive");
    } catch {
      sessionStorage.removeItem(`interview-screen-recording:${resultId}`);
      setChecks((prev) => ({
        ...prev,
        screen: {
          status: "denied",
          label: "Full screen recording",
          detail: "Permission was not granted. Please enable it to start the interview.",
        },
      }));
      announce("Full screen recording permission was not granted.", "assertive");
    }
  }

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950" role="status" aria-label="Loading">
        <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!user) {
    return <InlineLogin onSuccess={() => window.location.reload()} />;
  }

  const startCheck = async () => {
    setIsChecking(true);
    setError("");
    announce("Starting system check...", "assertive");

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    const recorderCheck = checkMediaRecorderSupport();

    try {
      let stream;
      let micGranted = true;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      } catch {
        try {
          stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
          micGranted = false;
        } catch {
          throw new Error("Access denied");
        }
      }
      streamRef.current = stream;
      await attachPreviewStream(videoRef.current, stream);
      setChecks({
        camera: { status: "granted", label: "Camera access" },
        mic: { status: micGranted ? "granted" : "denied", label: "Microphone access" },
        screen: checks.screen,
        internet: { status: "granted", label: "Internet connection" },
        voiceRecorder: {
          status: recorderCheck.supported ? "granted" : "denied",
          label: "Voice recording support",
          detail: recorderCheck.reason,
        },
      });
      announce("System check complete. Camera and microphone access granted.", "assertive");
      if (!micGranted) {
        setShowMicWarningModal(true);
        setError("Microphone not available. You can still complete the interview by typing answers.");
      }
    } catch {
      setShowMicWarningModal(true);
      announce("System check failed. Camera access denied.", "assertive");
      setError("");
    } finally {
      setIsChecking(false);
    }
  };

  async function handleStartInterview() {
    if (starting) return;
    setStarting(true);
    setError("");
    try {
      if (document.documentElement.requestFullscreen) {
        try {
          await document.documentElement.requestFullscreen();
        } catch { }
      }
      const access = await interviewApi.access(Number(resultId));

      if (access?.interview_locked_reason === "scheduled_for_future" || access?.can_start_now === false) {
        const opensAt = access?.interview_window_open_utc
          ? formatUtcDateTime(access.interview_window_open_utc)
          : null;
        const errorMsg = opensAt
          ? `Interview can start only within the allowed window. Please try again after ${opensAt}.`
          : "Interview can start only within the allowed window. Please try again closer to your scheduled time.";
        setError(errorMsg);
        announce(errorMsg, "assertive");
        return;
      }

      if (access?.interview_locked_reason === "start_window_expired") {
        setError("Interview start window has expired. Please reschedule your interview.");
        announce("Interview start window has expired.", "assertive");
        return;
      }

      if (access?.interview_locked_reason === "already_completed") {
        announce("Interview already completed. Redirecting...", "assertive");
        navigate(`/interview/${resultId}/completed`);
        return;
      }

      if (access?.interview_ready === false) {
        setError("Interview is not ready to start yet. Please recheck your schedule and try again.");
        announce("Interview is not ready to start yet.", "assertive");
        return;
      }

      sessionStorage.setItem(`interview-consent:${resultId}`, "true");
      const currentToken = new URLSearchParams(location.search).get("token") ||
        (() => {
          try {
            const hash = location.hash || "";
            const hashPath = hash.replace("#", "");
            const qIndex = hashPath.indexOf("?");
            if (qIndex >= 0) {
              return new URLSearchParams(hashPath.substring(qIndex)).get("token") || "";
            }
          } catch (e) { }
          return "";
        })();
      if (currentToken) {
        sessionStorage.setItem(`interview-token:${resultId}`, currentToken);
      }
      announce("Starting interview...", "assertive");
      navigate(`/interview/${resultId}/live`);
    } catch (e) {
      setError(e?.message || "Interview questions are not ready yet. Please try again.");
      announce(`Error: ${e?.message || "Interview not ready yet."}`, "assertive");
    } finally {
      setStarting(false);
    }
  }

  const cameraGranted = checks.camera.status === "granted";
  const screenGranted = checks.screen.status === "granted";
  const voiceUnsupported = checks.voiceRecorder.status === "denied" && checks.voiceRecorder.detail;
  const allGranted = Object.values(checks).every((c) => c.status === "granted");

  const handleVoiceChange = (voice) => {
    setSelectedVoice(voice);
    sessionStorage.setItem(`interview-voice:${resultId}`, voice);
    announce(`Voice changed to ${voice === "kajal" ? "Kajal (Indian Female)" : "Matthew (US Male)"}`);
  };

  return (
    <div className="min-h-[calc(100vh-160px)] flex flex-col items-center justify-center py-12 px-4 page-enter">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <MicWarningModal
        isOpen={showMicWarningModal}
        onClose={() => { setShowMicWarningModal(false); }}
        onContinue={() => { setShowMicWarningModal(false); setError(""); }}
      />

      <div id="main-content" className="max-w-4xl w-full grid grid-cols-1 lg:grid-cols-2 gap-12">
        <div className="space-y-8">
          <div>
            <div className="flex items-center space-x-2 text-blue-600 mb-4">
              <ShieldCheck size={24} aria-hidden="true" />
              <span className="text-sm font-black uppercase tracking-widest">System Check</span>
            </div>
            <h1 className="text-4xl font-black text-slate-900 dark:text-white font-display leading-tight">
              Ready to start your interview?
            </h1>
            <p className="text-slate-500 dark:text-slate-400 mt-4 text-lg">
              Before we begin, ensure your camera, microphone, and browser are ready.
            </p>
          </div>

          {error && (
            <div role="alert" className="p-4 rounded-2xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300">
              <p className="font-bold flex items-center gap-2">
                <AlertCircle size={16} aria-hidden="true" />
                Error
              </p>
              <p className="mt-1">{error}</p>
            </div>
          )}

          {error && checks.camera.status === "denied" && (
            <div className="p-4 rounded-2xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <h4 className="font-bold text-amber-800 dark:text-amber-300 flex items-center gap-2 mb-3">
                <Lock size={16} aria-hidden="true" />
                How to Enable Camera & Microphone
              </h4>
              <ol className="text-sm text-amber-700 dark:text-amber-400 space-y-2 list-decimal list-inside">
                <li>Click the lock or camera icon in your browser address bar</li>
                <li>Set <strong>Camera</strong> and <strong>Microphone</strong> to "Allow"</li>
                <li>Click <strong>Done</strong> to save</li>
                <li>Click <strong>Run System Check</strong> again below</li>
              </ol>
            </div>
          )}

          {voiceUnsupported && (
            <div role="alert" className="flex items-start gap-3 px-4 py-3 rounded-2xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-sm text-amber-800 dark:text-amber-300">
              <AlertTriangle size={18} className="flex-shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <p className="font-bold">Voice recording not supported</p>
                <p className="mt-0.5">{checks.voiceRecorder.detail} You can still type your answers. Use Chrome or Edge for full voice support.</p>
              </div>
            </div>
          )}

          <div role="list" aria-label="System requirements" className="space-y-4">
            <SystemCheckItem label="Camera access" status={checks.camera.status} icon={Camera} />
            <SystemCheckItem label="Microphone access" status={checks.mic.status} icon={Mic} />
            <SystemCheckItem label="Full screen recording" status={checks.screen.status} detail={checks.screen.detail} icon={MonitorUp} />
            <SystemCheckItem label="Internet connection" status={checks.internet.status} icon={Wifi} />
            <SystemCheckItem label="Voice recording support" status={checks.voiceRecorder.status} detail={checks.voiceRecorder.detail} icon={Mic} />
          </div>

          <div className="rounded-3xl border border-blue-100 dark:border-blue-800/50 bg-blue-50 dark:bg-blue-900/20 p-5 space-y-3">
            <div className="flex items-start gap-3">
              <div className="w-11 h-11 rounded-2xl bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center flex-shrink-0">
                <MonitorUp size={20} className="text-blue-600 dark:text-blue-300" aria-hidden="true" />
              </div>
              <div>
                <p className="font-bold text-blue-900 dark:text-blue-200">Enable full screen recording</p>
                <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                  Select your interview tab or entire screen when the browser prompt opens. This must stay enabled during the interview.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={requestFullScreenRecording}
              className={cn(
                "w-full py-3 rounded-2xl font-black flex items-center justify-center gap-2 transition-all",
                screenGranted
                  ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                  : "bg-blue-600 hover:bg-blue-700 text-white"
              )}
            >
              {screenGranted ? <CheckCircle2 size={18} aria-hidden="true" /> : <MonitorUp size={18} aria-hidden="true" />}
              <span>{screenGranted ? "Full Screen Recording Enabled" : "Enable Full Screen Recording"}</span>
            </button>
          </div>

          <fieldset className="space-y-3">
            <legend className="flex items-center justify-between w-full mb-2">
              <span className="font-bold text-slate-700 dark:text-slate-300">Voice Selection</span>
              <button
                type="button"
                onClick={async () => {
                  const testText = "Hello! This is a sample voice. Your interview questions will be read in this voice.";
                  try {
                    setIsTestingVoice(true);
                    announce("Testing voice...", "assertive");
                    const { interviewApi } = await import("../services/api");
                    await interviewApi.tts(testText, selectedVoice);
                    announce("Voice test complete", "assertive");
                  } catch (e) {
                    console.warn("Voice test failed:", e);
                    announce("Voice test failed", "assertive");
                  } finally {
                    setIsTestingVoice(false);
                  }
                }}
                disabled={isTestingVoice}
                className="text-xs px-3 py-1.5 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50 font-bold transition-colors flex items-center gap-1"
              >
                {isTestingVoice ? "Testing..." : "Test Voice"}
              </button>
            </legend>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handleVoiceChange("kajal")}
                aria-pressed={selectedVoice === "kajal"}
                className={cn(
                  "flex-1 py-3 px-3 rounded-xl font-bold text-sm transition-all border-2",
                  selectedVoice === "kajal"
                    ? "bg-pink-50 dark:bg-pink-900/20 border-pink-400 text-pink-700 dark:text-pink-300"
                    : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-pink-300"
                )}
              >
                Female (Kajal)
              </button>
              <button
                type="button"
                onClick={() => handleVoiceChange("matthew")}
                aria-pressed={selectedVoice === "matthew"}
                className={cn(
                  "flex-1 py-3 px-3 rounded-xl font-bold text-sm transition-all border-2",
                  selectedVoice === "matthew"
                    ? "bg-blue-50 dark:bg-blue-900/20 border-blue-400 text-blue-700 dark:text-blue-300"
                    : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-blue-300"
                )}
              >
                Male (Matthew)
              </button>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Selected: <span className="font-bold">{selectedVoice === "kajal" ? "Kajal (Indian Female)" : "Matthew (US Male)"}</span>
            </p>
          </fieldset>

          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={startCheck}
              disabled={isChecking}
              aria-busy={isChecking}
              className="flex-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 font-black py-4 rounded-2xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-all flex items-center justify-center space-x-2 shadow-sm"
            >
              {isChecking ? (
                <>
                  <span className="animate-spin" aria-hidden="true">⟳</span>
                  <span>Checking...</span>
                </>
              ) : "Run System Check"}
            </button>

            <button
              type="button"
              disabled={!cameraGranted || !screenGranted || starting}
              onClick={handleStartInterview}
              aria-busy={starting}
              className={cn(
                "flex-[1.5] py-4 rounded-2xl font-black flex items-center justify-center space-x-2 transition-all shadow-xl",
                cameraGranted && screenGranted
                  ? "bg-blue-600 hover:bg-blue-700 text-white shadow-blue-200 dark:shadow-none"
                  : "bg-slate-100 dark:bg-slate-800 text-slate-400 cursor-not-allowed"
              )}
              title={!cameraGranted ? "Camera access required to start interview" : !screenGranted ? "Full screen recording must be enabled before starting" : ""}
            >
              <span>{starting ? "Starting..." : "Start Interview"}</span>
              <Play size={18} fill="currentColor" aria-hidden="true" />
            </button>
          </div>

          {!allGranted && cameraGranted && (
            <p className="text-xs text-slate-500 dark:text-slate-400 text-center">
              Camera is ready. You can start — type answers if mic is unavailable.
            </p>
          )}

          {!cameraGranted && (
            <p className="text-xs text-red-500 dark:text-red-400 text-center">
              Camera access required. Please allow camera access to continue.
            </p>
          )}

          {cameraGranted && !screenGranted && (
            <p className="text-xs text-red-500 dark:text-red-400 text-center">
              Full screen recording must be enabled before starting the interview.
            </p>
          )}
        </div>

        <div className="space-y-6">
          <div className="relative aspect-video bg-slate-900 rounded-[32px] overflow-hidden shadow-2xl border-4 border-white dark:border-slate-800">
            <video
              ref={videoRef}
              className="w-full h-full object-cover scale-x-[-1]"
              autoPlay
              muted
              playsInline
              aria-label="Camera preview"
            />
            {checks.camera.status !== "granted" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500">
                <div className="w-20 h-20 bg-slate-800 rounded-full flex items-center justify-center mb-4">
                  <Video size={32} aria-hidden="true" />
                </div>
                <p className="text-sm font-bold uppercase tracking-widest">No Video Feed</p>
              </div>
            )}
            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center space-x-2 bg-black/50 backdrop-blur-md px-4 py-2 rounded-full border border-white/20">
              <div className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
              </div>
              <span className="text-[10px] font-black text-white uppercase tracking-widest">Live Preview</span>
            </div>
          </div>

          <div className="bg-blue-50 dark:bg-blue-900/20 p-6 rounded-3xl border border-blue-100 dark:border-blue-800/50">
            <h4 className="text-sm font-bold text-blue-800 dark:text-blue-300 flex items-center mb-3">
              <Settings className="mr-2" size={16} aria-hidden="true" />
              Interview Requirements
            </h4>
            <ul className="space-y-2 text-xs text-blue-700 dark:text-blue-400 font-medium">
              <li className="flex items-center space-x-2">
                <div className="w-1 h-1 bg-blue-400 rounded-full flex-shrink-0" aria-hidden="true" />
                <span>Sit in a well-lit and quiet room</span>
              </li>
              <li className="flex items-center space-x-2">
                <div className="w-1 h-1 bg-blue-400 rounded-full flex-shrink-0" aria-hidden="true" />
                <span>Ensure your face is clearly visible</span>
              </li>
              <li className="flex items-center space-x-2">
                <div className="w-1 h-1 bg-blue-400 rounded-full flex-shrink-0" aria-hidden="true" />
                <span>Use Chrome or Edge for best voice recording support</span>
              </li>
              <li className="flex items-start space-x-2">
                <Volume2 size={12} className="flex-shrink-0 mt-0.5" aria-hidden="true" />
                <span>Each question will be <strong>read aloud automatically</strong> — you can mute this at any time using the voice button during the interview</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
      <HelpSupportButton supportEmail="support@quadranttech.com" />

      <div aria-live="polite" aria-atomic="true" className="sr-announcer" />
    </div>
  );
}
