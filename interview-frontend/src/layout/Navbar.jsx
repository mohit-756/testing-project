import React, { useState } from "react";
import { Sun, Moon, Menu } from "lucide-react";
import { useAuth } from "../context/useAuth";

export default function Navbar({ toggleSidebar }) {
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains("dark"));
  const { user } = useAuth();

  const toggleTheme = () => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.remove("dark");
    } else {
      root.classList.add("dark");
    }
    setIsDark(!isDark);
  };

  const formatDate = () => {
    const date = new Date();
    const options = { weekday: "long", month: "short", day: "numeric" };
    return date.toLocaleDateString("en-US", options);
  };

  const getUserName = () => {
    return user?.name || "User";
  };

  return (
    <header
      className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-6 sticky top-0 z-40"
      role="banner"
    >
      {/* Left Side - Greeting */}
      <div className="flex items-center space-x-4">
        <button
          onClick={toggleSidebar}
          className="lg:hidden p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          aria-label="Toggle navigation menu"
        >
          <Menu size={20} />
        </button>
        <h1 className="text-xl md:text-2xl font-bold text-slate-900 dark:text-white">
          Hello, <span className="text-blue-600">{getUserName()}</span>
        </h1>
      </div>

      {/* Right Side - Date & Theme */}
      <div className="flex items-center space-x-4">
        <div className="hidden sm:flex items-center space-x-3 text-sm text-slate-500 dark:text-slate-400">
          <span>{formatDate()}</span>
        </div>
        <button
          onClick={toggleTheme}
          className="p-2 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 rounded-lg transition-all"
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {isDark ? <Sun size={20} /> : <Moon size={20} />}
        </button>
      </div>
    </header>
  );
}