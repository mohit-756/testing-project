/**
 * useInputBlocking.js
 *
 * Blocks user input to prevent cheating during interview:
 * - Right-click context menu
 * - Copy/Paste/Cut shortcuts (Ctrl+C/V/X/A)
 * - Keyboard shortcuts (F12, Ctrl+U, Ctrl+S)
 * - Text selection
 *
 * Usage:
 *   const { isBlocked, blockCount } = useInputBlocking({ enabled: true });
 */

import { useCallback, useEffect, useRef, useState } from "react";

const BLOCKED_KEYS = [
  "c", // Ctrl+C
  "v", // Ctrl+V
  "x", // Ctrl+X
  "a", // Ctrl+A
  "s", // Ctrl+S
  "u", // Ctrl+U
  "i", // Ctrl+I (inspector)
  "j", // Ctrl+J
  "k", // Ctrl+K
  "p", // Ctrl+P (print)
];

export function useInputBlocking({ enabled = true }) {
  const [isBlocked, setIsBlocked] = useState(false);
  const [blockCount, setBlockCount] = useState(0);
  const [lastBlockedAction, setLastBlockedAction] = useState(null);

  const blockRef = useRef(0);

  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
    blockRef.current += 1;
    setBlockCount(blockRef.current);
    setLastBlockedAction("right_click");
    setIsBlocked(true);
    setTimeout(() => setIsBlocked(false), 100);
  }, []);

  const handleKeyDown = useCallback((e) => {
    const isCtrl = e.ctrlKey || e.metaKey;
    const isAlt = e.altKey;

    // Block right-click context menu
    if (e.key === "F12") {
      e.preventDefault();
      blockRef.current += 1;
      setBlockCount(blockRef.current);
      setLastBlockedAction("F12");
      setIsBlocked(true);
      setTimeout(() => setIsBlocked(false), 100);
      return;
    }

    // Block Ctrl+U (view source)
    if (isCtrl && e.key.toLowerCase() === "u") {
      e.preventDefault();
      blockRef.current += 1;
      setBlockCount(blockRef.current);
      setLastBlockedAction("view_source");
      setIsBlocked(true);
      setTimeout(() => setIsBlocked(false), 100);
      return;
    }

    // Block copy/paste/cut/select all
    if (isCtrl || isAlt) {
      const key = e.key.toLowerCase();
      if (BLOCKED_KEYS.includes(key)) {
        e.preventDefault();
        blockRef.current += 1;
        setBlockCount(blockRef.current);
        setLastBlockedAction(`ctrl_${key}`);
        setIsBlocked(true);
        setTimeout(() => setIsBlocked(false), 100);
        return;
      }
    }

    // Block Print screen
    if (e.key === "PrintScreen") {
      e.preventDefault();
      blockRef.current += 1;
      setBlockCount(blockRef.current);
      setLastBlockedAction("printscreen");
      setIsBlocked(true);
      setTimeout(() => setIsBlocked(false), 100);
      return;
    }
  }, []);

  const handleSelectStart = useCallback((e) => {
    // Disable text selection during interview
    if (e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
      e.preventDefault();
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;

    // Block context menu
    document.addEventListener("contextmenu", handleContextMenu);

    // Block keyboard shortcuts
    document.addEventListener("keydown", handleKeyDown);

    // Block text selection
    document.addEventListener("selectstart", handleSelectStart, { passive: false });

    // Add CSS to prevent selection
    document.body.style.userSelect = "none";
    document.body.style.webkitUserSelect = "none";
    document.body.style.mozUserSelect = "none";
    document.body.style.msUserSelect = "none";

    return () => {
      document.removeEventListener("contextmenu", handleContextMenu);
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("selectstart", handleSelectStart);

      // Restore selection
      document.body.style.userSelect = "";
      document.body.style.webkitUserSelect = "";
      document.body.style.mozUserSelect = "";
      document.body.style.msUserSelect = "";
    };
  }, [enabled, handleContextMenu, handleKeyDown, handleSelectStart]);

  return {
    isBlocked,
    blockCount,
    lastBlockedAction,
  };
}