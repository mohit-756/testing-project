import { useState } from "react";
import { useLocation, Link } from "react-router-dom";
import { HelpCircle, X, Mail, ExternalLink, Lightbulb, FileText, Upload, Calendar, Users, BarChart3, Settings, CheckCircle2 } from "lucide-react";

const helpTips = {
  // Candidate pages
  "/candidate": {
    tips: [
      { icon: Upload, text: "Upload your resume in PDF or DOCX format" },
      { icon: FileText, text: "Select a job to see matching resume score" },
      { icon: Calendar, text: "Schedule your interview after being shortlisted" },
    ],
  },
  "/interview/result": {
    tips: [
      { icon: BarChart3, text: "Check your application status here" },
      { icon: CheckCircle2, text: "Review feedback to improve next time" },
    ],
  },
  "/settings": {
    tips: [
      { icon: Settings, text: "Update your name, email, and password" },
      { icon: HelpCircle, text: "Find answers in Help & FAQ tab" },
    ],
  },
  // HR pages
  "/hr": {
    tips: [
      { icon: Users, text: "View and manage all candidates" },
      { icon: BarChart3, text: "Check analytics for hiring pipeline" },
    ],
  },
  "/hr/candidates": {
    tips: [
      { icon: Users, text: "Click candidate name to view full profile" },
      { icon: Calendar, text: "Schedule interview from calendar icon" },
      { icon: FileText, text: "View resume scores and match percentage" },
    ],
  },
  "/hr/jds": {
    tips: [
      { icon: FileText, text: "Create job descriptions with skill weights" },
      { icon: Settings, text: "Set minimum scores to qualify candidates" },
    ],
  },
  "/hr/interviews": {
    tips: [
      { icon: CheckCircle2, text: "Review completed interview sessions" },
      { icon: BarChart3, text: "View AI scores and proctoring events" },
    ],
  },
  "/hr/pipeline": {
    tips: [
      { icon: Users, text: "Drag candidates between stages" },
      { icon: Calendar, text: "Schedule interviews from candidate cards" },
    ],
  },
  "/hr/analytics": {
    tips: [
      { icon: BarChart3, text: "Track hiring metrics and conversion rates" },
    ],
  },
};

const pageNames = {
  "/candidate": "Dashboard",
  "/interview/result": "My Results",
  "/settings": "Settings",
  "/hr": "Dashboard",
  "/hr/candidates": "Candidates",
  "/hr/jds": "Job Descriptions",
  "/hr/interviews": "Interviews",
  "/hr/pipeline": "Pipeline",
  "/hr/analytics": "Analytics",
  "/hr/matrix": "Score Matrix",
};

export default function HelpSupportButton({ supportEmail = "support@quadranttech.com", faqUrl = "/settings" }) {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();

  // Get current page tips or use default
  const currentPageTips = helpTips[location.pathname] || null;
  const pageName = pageNames[location.pathname] || null;

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {isOpen && (
        <div className="absolute bottom-14 right-0 w-80 bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 p-4 animate-fadeIn">
          <button
            onClick={() => setIsOpen(false)}
            className="absolute top-3 right-3 p-1 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500"
          >
            <X size={16} />
          </button>

          {/* Context-aware Tips */}
          {currentPageTips && (
            <div className="mb-4">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                {pageName} Quick Tips
              </h4>
              <div className="space-y-2">
                {currentPageTips.tips.map((tip, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                    <tip.icon size={14} className="text-blue-500 mt-0.5 flex-shrink-0" />
                    <span>{tip.text}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* General Help Options */}
          <div className="border-t border-slate-100 dark:border-slate-800 pt-3 space-y-2">
            <a
              href={`mailto:${supportEmail}?subject=Interview%20Support%20Request`}
              className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              <Mail size={14} />
              <span>Email Support</span>
            </a>
            <Link
              to={faqUrl}
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              <HelpCircle size={14} />
              <span>View Full FAQ</span>
            </Link>
          </div>
        </div>
      )}

      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-full shadow-lg hover:shadow-xl transition-all hover:scale-105"
        aria-label="Help?"
      >
        <HelpCircle size={18} />
        <span className="hidden sm:inline">Help</span>
      </button>
    </div>
  );
}