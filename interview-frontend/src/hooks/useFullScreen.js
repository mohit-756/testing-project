/**
 * useFullScreen.js
 *
 * Enforces full-screen mode for interview:
 * - Automatically requests full-screen when interview starts
 * - Forces interview to stop if user exits full-screen
 * - Tracks exit count
 *
 * Usage:
 *   const { isFullScreen, exitCount, forcePause, requestFullScreen } = useFullScreen({
 *     enabled: true,
 *     onExit: () => handleForceStop()
 *   });
 */

import { useCallback, useEffect, useRef, useState } from "react";

export function useFullScreen({ enabled = true, onExit = null }) {
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [exitCount, setExitCount] = useState(0);
  const [forcePause, setForcePause] = useState(false);
  const [hasRequested, setHasRequested] = useState(false);

  const exitCountRef = useRef(0);
  const isCurrentlyFullScreen = useRef(false);

  const checkFullScreen = useCallback(() => {
    const fs = !!(
      document.fullscreenElement ||
      document.webkitFullscreenElement ||
      document.mozFullScreenElement ||
      document.msFullscreenElement
    );
    setIsFullScreen(fs);
    return fs;
  }, []);

  const requestFullScreen = useCallback(async () => {
    if (!document.documentElement) return false;
    try {
      const el = document.documentElement;
      if (el.requestFullscreen) {
        await el.requestFullscreen();
      } else if (el.webkitRequestFullscreen) {
        await el.webkitRequestFullscreen();
      } else if (el.mozRequestFullScreen) {
        await el.mozRequestFullScreen();
      } else if (el.msRequestFullscreen) {
        await el.msRequestFullscreen();
      }
      setHasRequested(true);
      return true;
    } catch {
      return false;
    }
  }, []);

  const exitFullScreen = useCallback(async () => {
    try {
      if (document.exitFullscreen) {
        await document.exitFullscreen();
      } else if (document.webkitExitFullscreen) {
        await document.webkitExitFullscreen();
      } else if (document.mozCancelFullScreen) {
        await document.mozCancelFullScreen();
      } else if (document.msExitFullscreen) {
        await document.msExitFullscreen();
      }
    } catch { }
  }, []);

  const handleFullScreenChange = useCallback(() => {
    const nowFs = checkFullScreen();

    // User was in full-screen and now exited - force stop interview
    if (isCurrentlyFullScreen.current && !nowFs && hasRequested) {
      exitCountRef.current += 1;
      setExitCount(exitCountRef.current);

      // Force pause/stop the interview
      setForcePause(true);
      setHasRequested(false);

      // Trigger callback if provided
      if (onExit) {
        onExit(exitCountRef.current);
      }
    }

    // Successfully entered full-screen
    if (!isCurrentlyFullScreen.current && nowFs) {
      setForcePause(false);
      setHasRequested(true);
    }

    isCurrentlyFullScreen.current = nowFs;
  }, [checkFullScreen, hasRequested, onExit]);

  const handleKeyDown = useCallback((e) => {
    // Block Escape key when in interview
    if (e.key === "Escape" && hasRequested && !isFullScreen) {
      e.preventDefault();
      setForcePause(true);
    }
  }, [hasRequested, isFullScreen]);

  const handleBeforeUnload = useCallback((e) => {
    // Prevent leaving during interview
    if (hasRequested && isCurrentlyFullScreen.current === false) {
      e.preventDefault();
      e.returnValue = "";
    }
  }, [hasRequested]);

  useEffect(() => {
    if (!enabled) return;

    // Check initial state
    checkFullScreen();

    // Listen for fullscreen changes
    document.addEventListener("fullscreenchange", handleFullScreenChange);
    document.addEventListener("webkitfullscreenchange", handleFullScreenChange);
    document.addEventListener("mozfullscreenchange", handleFullScreenChange);
    document.addEventListener("MSFullscreenChange", handleFullScreenChange);

    // Listen for escape key
    document.addEventListener("keydown", handleKeyDown);

    // Prevent leaving page during interview
    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      document.removeEventListener("fullscreenchange", handleFullScreenChange);
      document.removeEventListener("webkitfullscreenchange", handleFullScreenChange);
      document.removeEventListener("mozfullscreenchange", handleFullScreenChange);
      document.removeEventListener("MSFullscreenChange", handleFullScreenChange);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [enabled, checkFullScreen, handleFullScreenChange, handleKeyDown, handleBeforeUnload]);

  const dismissPause = useCallback(() => {
    setForcePause(false);
  }, []);

  const resumeFromPause = useCallback(async () => {
    // Try to re-enter full-screen and resume
    await requestFullScreen();
    setForcePause(false);
  }, [requestFullScreen]);

  return {
    isFullScreen,
    exitCount,
    forcePause,
    hasRequested,
    requestFullScreen,
    exitFullScreen,
    dismissPause,
    resumeFromPause,
  };
}