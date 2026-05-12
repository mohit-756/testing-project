/**
 * useProctoring.js
 *
 * Lightweight proctoring hook for the Interview page.
 *
 * Features (all run asynchronously, none block the UI thread):let sharedAudioContext = null;
 *   1. Tab-switch detection - visibilitychange event
 *   2. Voice confidence - pure heuristic on transcript text:
 *      speaking rate, filler words, sentence fragmentation.
 *
 * All events are stored in a local ref array AND tab-switch events are sent to
 * the backend via the existing interview event endpoint.
 *
 * Usage:
 *   const { proctoringEvents, voiceMetrics, analyseAnswer } = useProctoring({
 *     sessionId,
 *     enabled: true,
 *   });
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { interviewApi, proctorApi } from "../services/api";

const MAX_EVENTS_STORED = 200;
const FRAME_CAPTURE_INTERVAL_MS = 5000; // Capture frame every 5 seconds

// Capture a frame from video element and convert to JPEG blob
async function captureFrame(videoElement, quality = 0.7) {
  if (!videoElement || videoElement.readyState < 2) return null;
  const canvas = document.createElement("canvas");
  // Downscale to reduce payload size
  const scale = Math.min(1, 320 / videoElement.videoWidth);
  canvas.width = videoElement.videoWidth * scale;
  canvas.height = videoElement.videoHeight * scale;
  const ctx = canvas.getContext("2d");
  ctx.scale(-1, 1); // Mirror effect to match displayed video
  ctx.drawImage(videoElement, -canvas.width, 0, canvas.width, canvas.height);
  return new Promise((resolve) => {
    canvas.toBlob(
      (blob) => resolve(blob),
      "image/jpeg",
      quality
    );
  });
}

const FILLER_WORDS = [
  "uh", "um", "er", "ah", "like", "you know", "i mean",
  "basically", "literally", "actually", "sort of", "kind of",
];

function analyseVoiceConfidence(transcript, durationSeconds) {
  if (!transcript || durationSeconds <= 0) return null;

  const words = transcript.trim().split(/\s+/).filter(Boolean);
  const wordCount = words.length;
  if (wordCount < 3) return null;

  const speakingRate = Math.round((wordCount / durationSeconds) * 60);
  const lowerWords = transcript.toLowerCase();

  let fillerCount = 0;
  FILLER_WORDS.forEach((f) => {
    const re = new RegExp(`\\b${f}\\b`, "g");
    const matches = lowerWords.match(re);
    if (matches) fillerCount += matches.length;
  });

  const hesitationScore = parseFloat(
    Math.min(1, fillerCount / Math.max(1, wordCount / 5)).toFixed(2)
  );

  let rateScore = 1.0;
  if (speakingRate < 80 || speakingRate > 220) rateScore = 0.5;
  else if (speakingRate < 100 || speakingRate > 200) rateScore = 0.75;

  const confidenceScore = parseFloat(
    ((rateScore * 0.6) + ((1 - hesitationScore) * 0.4)).toFixed(2)
  );

  return {
    speaking_rate: speakingRate,
    word_count: wordCount,
    filler_count: fillerCount,
    hesitation_score: hesitationScore,
    confidence_score: confidenceScore,
    duration_seconds: Math.round(durationSeconds),
  };
}

export function useProctoring({ sessionId, resultId, interviewToken, enabled = true, videoRef }) {
  const [proctoringEvents, setProctoringEvents] = useState([]);
  const [voiceMetrics, setVoiceMetrics] = useState(null);
  const [frameStatus, setFrameStatus] = useState(null);

  const eventsRef = useRef([]);
  const frameIntervalRef = useRef(null);

  const pushEvent = useCallback((event) => {
    const stamped = { ...event, timestamp: new Date().toISOString() };
    eventsRef.current = [stamped, ...eventsRef.current].slice(0, MAX_EVENTS_STORED);
    setProctoringEvents((prev) => [stamped, ...prev].slice(0, MAX_EVENTS_STORED));
  }, []);

  // Frame capture for CV proctoring
  useEffect(() => {
    if (!enabled || !sessionId || !videoRef?.current) return;

    let stopped = false;

    async function captureAndSend() {
      if (stopped) return;
      const videoEl = videoRef.current;
      if (!videoEl || videoEl.readyState < 2) return;

      try {
        const blob = await captureFrame(videoEl);
        if (!blob || stopped) return;

        const response = await proctorApi.uploadFrame(sessionId, blob, "scan");
        if (response && response.event_type) {
          setFrameStatus(response);
          // Log suspicious events to proctoring panel
          if (response.suspicious) {
            pushEvent({
              type: response.event_type.toUpperCase(),
              detail: response.frame_reasons || response.event_type,
              suspicious: true,
              compliance_score: response.compliance_score,
            });
          }
        }
      } catch (err) {
        // Silently fail - don't block interview for proctoring errors
        console.warn("Frame capture failed:", err.message);
      }
    }

    // Initial capture
    captureAndSend();
    // Repeat every 5 seconds
    frameIntervalRef.current = setInterval(captureAndSend, FRAME_CAPTURE_INTERVAL_MS);

    return () => {
      stopped = true;
      if (frameIntervalRef.current) {
        clearInterval(frameIntervalRef.current);
        frameIntervalRef.current = null;
      }
    };
  }, [enabled, sessionId, videoRef, pushEvent]);

  // Tab-switch detection
  useEffect(() => {
    if (!enabled || !sessionId) return;

    function onVisibilityChange() {
      if (!document.hidden) return;

      const event = { type: "TAB_SWITCH", detail: "Candidate switched browser tab" };
      pushEvent(event);

      const eventTargetId = interviewToken || resultId || sessionId;
      if (!eventTargetId) return;

      interviewApi.logEvent(eventTargetId, {
        event_type: "tab_switch",
        detail: "Candidate switched away from the interview tab",
        timestamp: new Date().toISOString(),
        meta: { hidden: true },
      }).catch(() => {});
    }

    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, [enabled, sessionId, resultId, interviewToken, pushEvent]);

  const analyseAnswer = useCallback((transcript, durationSeconds) => {
    const metrics = analyseVoiceConfidence(transcript, durationSeconds);
    if (!metrics) return null;
    setVoiceMetrics(metrics);
    pushEvent({ type: "VOICE_CONFIDENCE", ...metrics });
    return metrics;
  }, [pushEvent]);

  return {
    proctoringEvents,
    voiceMetrics,
    analyseAnswer,
    frameStatus,
  };
}
