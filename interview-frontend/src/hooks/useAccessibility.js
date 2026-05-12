import { useCallback, useEffect, useRef, useState } from "react";

export function useFocusTrap(isActive = false) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!isActive || !containerRef.current) return;

    const container = containerRef.current;
    const focusableSelectors = [
      'button:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      'a[href]',
      '[tabindex]:not([tabindex="-1"])',
    ].join(', ');

    const focusableElements = container.querySelectorAll(focusableSelectors);
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    function handleKeyDown(e) {
      if (e.key !== "Tab") return;

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement?.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement?.focus();
        }
      }
    }

    container.addEventListener("keydown", handleKeyDown);
    firstElement?.focus();

    return () => container.removeEventListener("keydown", handleKeyDown);
  }, [isActive]);

  return containerRef;
}

export function useAnnounce() {
  const [message, setMessage] = useState("");
  const timeoutRef = useRef(null);

  const announce = useCallback((msg, priority = "polite") => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setMessage("");
    timeoutRef.current = setTimeout(() => {
      setMessage(JSON.stringify({ message: msg, priority }));
    }, 100);
  }, []);

  return { announce, announcement: message };
}

export function useKeyboardShortcut(keys, callback, preventDefault = true) {
  useEffect(() => {
    function handler(e) {
      const expected = Array.isArray(keys) ? keys : [keys];
      const matches = expected.every((key) => {
        if (key === "ctrl") return e.ctrlKey;
        if (key === "shift") return e.shiftKey;
        if (key === "alt") return e.altKey;
        if (key === "meta") return e.metaKey;
        return e.key.toLowerCase() === key.toLowerCase() || e.code.toLowerCase() === key.toLowerCase();
      });
      if (matches) {
        if (preventDefault) e.preventDefault();
        callback(e);
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [keys, callback, preventDefault]);
}

export function useReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const handler = (e) => setReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  return reducedMotion;
}