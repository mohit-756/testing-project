import React, { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Navbar from "./Navbar";
import HelpSupportButton from "../components/HelpSupportButton";

export default function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(() => (typeof window !== "undefined" ? window.innerWidth >= 1024 : true));
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-slate-950 font-sans">
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close sidebar"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-40 bg-slate-950/60 lg:hidden"
        />
      )}
      <Sidebar 
        isOpen={sidebarOpen} 
        onClose={() => setSidebarOpen(false)}
        collapsed={sidebarCollapsed}
        onMouseEnter={() => {
          if (window.innerWidth >= 1024) setSidebarCollapsed(false);
        }}
        onMouseLeave={() => {
          if (window.innerWidth >= 1024) setSidebarCollapsed(true);
        }}
      />
      <div 
        className={`transition-all duration-300 ${sidebarCollapsed ? "lg:pl-16" : "lg:pl-64"}`}
      >
        <Navbar toggleSidebar={() => setSidebarOpen((open) => !open)} />
        <main className="p-6 lg:p-8">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
      <HelpSupportButton supportEmail="support@quadranttech.com" />
    </div>
  );
}