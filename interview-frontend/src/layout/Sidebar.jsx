import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Users, ClipboardList, Settings, LogOut,
  BarChart3, Video, FileText, LayoutGrid, Download, Columns3
} from "lucide-react";
import { useAuth } from "../context/useAuth";
import { cn } from "../utils/utils";

export default function Sidebar({ isOpen = true, onClose, collapsed = false, onMouseEnter, onMouseLeave }) {
  const { user, logout } = useAuth();
  const isHR = user?.role === "hr";

  const hrLinks = [
    { name: "Dashboard",         path: "/hr",              icon: LayoutDashboard },
    { name: "Candidates",        path: "/hr/candidates",   icon: Users },
    { name: "Pipeline",          path: "/hr/pipeline",      icon: Columns3 },
    { name: "JD Management",     path: "/hr/jds",          icon: FileText },
    { name: "Score Matrix",      path: "/hr/matrix",        icon: LayoutGrid },
    { name: "Interview Reviews", path: "/hr/interviews",    icon: ClipboardList },
    { name: "Analytics",         path: "/hr/analytics",     icon: BarChart3 },
    { name: "Backup",            path: "/hr/backup",         icon: Download },
    { name: "Settings",          path: "/settings",         icon: Settings },
  ];

  const candidateLinks = [
    { name: "Dashboard",   path: "/candidate",        icon: LayoutDashboard },
    { name: "My Results",  path: "/interview/result",  icon: BarChart3 },
    { name: "Settings",    path: "/settings",          icon: Settings },
  ];

  const links = isHR ? hrLinks : candidateLinks;

  const handleKeyDown = (e, callback) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      callback();
    }
  };

  const sidebarClasses = cn(
    "h-screen bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col fixed left-0 top-0 z-50 transition-all duration-300 ease-out",
    "lg:transition-all lg:duration-300"
  );

  return (
    <>
      {/* Mobile Sidebar */}
      <nav
        aria-label={`${isHR ? "HR" : "Candidate"} navigation menu`}
        className={cn(
          sidebarClasses,
          "lg:hidden",
          isOpen ? "translate-x-0 w-64" : "-translate-x-full w-64"
        )}
      >
        <div className="p-6">
          <div className="flex items-center space-x-2">
            <div className="bg-blue-600 p-1.5 rounded-lg flex-shrink-0" aria-hidden="true">
              <Video className="text-white w-5 h-5" />
            </div>
            <span className="text-xl font-bold font-display tracking-tight dark:text-white whitespace-nowrap">
              Interview<span className="text-blue-600">Bot</span>
            </span>
          </div>
        </div>

        <ul className="flex-1 px-4 space-y-1 overflow-y-auto mt-2" role="list">
          {links.map((link) => (
            <li key={link.path}>
              <NavLink
                to={link.path}
                end={link.path === "/hr" || link.path === "/candidate"}
                onClick={() => onClose?.()}
                onKeyDown={(e) => handleKeyDown(e, () => onClose?.())}
                className={({ isActive }) =>
                  cn(
                    "flex items-center space-x-3 px-4 py-2.5 rounded-xl transition-all font-medium text-sm",
                    isActive
                      ? "bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400"
                      : "text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800/50"
                  )
                }
                aria-current={({ isActive }) => isActive ? "page" : undefined}
              >
                <link.icon size={18} aria-hidden="true" />
                <span>{link.name}</span>
              </NavLink>
            </li>
          ))}
        </ul>

        <div className="p-4 border-t border-slate-100 dark:border-slate-800">
          <div
            className="flex items-center p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 mb-3"
            role="region"
            aria-label="User profile"
          >
            <div
              className="w-9 h-9 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400 font-bold mr-3"
              aria-hidden="true"
            >
              {user?.name?.[0] || "U"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">{user?.name || "User"}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 capitalize">{user?.role || "Role"}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="flex items-center space-x-3 px-4 py-2.5 rounded-xl w-full text-slate-500 hover:bg-red-50 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-900/20 transition-all font-medium text-sm"
            aria-label="Logout"
          >
            <LogOut size={18} aria-hidden="true" />
            <span>Logout</span>
          </button>
        </div>
      </nav>

      {/* Desktop Hover-Expand Sidebar */}
      <nav
        aria-label={`${isHR ? "HR" : "Candidate"} navigation menu`}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        className={cn(
          "hidden lg:flex h-screen bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex-col fixed left-0 top-0 z-50",
          collapsed ? "w-16" : "w-64"
        )}
      >
        <div className={cn("p-4 flex items-center transition-all duration-300", collapsed ? "justify-center" : "space-x-2")}>
          <div className="bg-blue-600 p-1.5 rounded-lg flex-shrink-0" aria-hidden="true">
            <Video className="text-white w-5 h-5" />
          </div>
          <span 
            className={cn(
              "text-xl font-bold font-display tracking-tight dark:text-white whitespace-nowrap transition-all duration-300",
              collapsed ? "opacity-0 w-0" : "opacity-100"
            )}
          >
            Interview<span className="text-blue-600">Bot</span>
          </span>
        </div>

        <ul className="flex-1 px-2 overflow-y-auto mt-2 space-y-1" role="list">
          {links.map((link) => (
            <li key={link.path}>
              <NavLink
                to={link.path}
                end={link.path === "/hr" || link.path === "/candidate"}
                onClick={() => onClose?.()}
                onKeyDown={(e) => handleKeyDown(e, () => onClose?.())}
                className={({ isActive }) =>
                  cn(
                    "flex items-center rounded-xl transition-all duration-200 font-medium text-sm",
                    collapsed ? "justify-center px-2 py-3" : "px-4 py-2.5 space-x-3",
                    isActive
                      ? "bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400"
                      : "text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800/50"
                  )
                }
                aria-current={({ isActive }) => isActive ? "page" : undefined}
              >
                <link.icon size={18} aria-hidden="true" className="flex-shrink-0" />
                <span 
                  className={cn(
                    "whitespace-nowrap transition-all duration-300",
                    collapsed ? "opacity-0 w-0 overflow-hidden" : "opacity-100"
                  )}
                >
                  {link.name}
                </span>
              </NavLink>
            </li>
          ))}
        </ul>

        <div className="p-2 border-t border-slate-100 dark:border-slate-800">
          <div
            className={cn(
              "flex items-center rounded-xl bg-slate-50 dark:bg-slate-800/50 mb-2 transition-all duration-300",
              collapsed ? "justify-center p-2" : "p-3"
            )}
            role="region"
            aria-label="User profile"
          >
            <div
              className="w-9 h-9 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400 font-bold flex-shrink-0"
              aria-hidden="true"
            >
              {user?.name?.[0] || "U"}
            </div>
            <div 
              className={cn(
                "flex-1 min-w-0 transition-all duration-300",
                collapsed ? "opacity-0 w-0 overflow-hidden" : "opacity-100"
              )}
            >
              <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">{user?.name || "User"}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 capitalize">{user?.role || "Role"}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className={cn(
              "flex items-center rounded-xl w-full text-slate-500 hover:bg-red-50 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-900/20 transition-all font-medium text-sm",
              collapsed ? "justify-center px-2 py-3" : "px-4 py-2.5 space-x-3"
            )}
            aria-label="Logout"
          >
            <LogOut size={18} aria-hidden="true" className="flex-shrink-0" />
            <span 
              className={cn(
                "whitespace-nowrap transition-all duration-300",
                collapsed ? "opacity-0 w-0 overflow-hidden" : "opacity-100"
              )}
            >
              Logout
            </span>
          </button>
        </div>
      </nav>
    </>
  );
}