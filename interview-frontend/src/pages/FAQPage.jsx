import { useState } from "react";
import { useAuth } from "../context/useAuth";
import { Minus, Plus, HelpCircle } from "lucide-react";

function FAQItem({ question, answer, onToggle, isOpen }) {
  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
      >
        <span className="font-medium text-slate-900 dark:text-white">{question}</span>
        {isOpen ? <Minus size={18} className="text-slate-500" /> : <Plus size={18} className="text-slate-500" />}
      </button>
      {isOpen && answer && (
        <div className="px-4 pb-4 text-sm text-slate-600 dark:text-slate-400 leading-relaxed border-t border-slate-100 dark:border-slate-800 pt-3 mt-2">
          {answer}
        </div>
      )}
    </div>
  );
}

export default function FAQPage() {
  const { user } = useAuth();
  const isHR = user?.role === "hr";
  const [openIndex, setOpenIndex] = useState(null);

  const staticFAQs = isHR ? [
    { question: "How do I post a new job?", answer: "Go to JD Management → Add JD. Fill in the job title, description, required skills (with weights), and interview settings. Save to publish." },
    { question: "What do the candidate scores mean?", answer: "Resume Score: AI match based on skills in JD. Interview Score: Quality of candidate's answers. Final Score: Combined HR review. Score breakdown shows behavioral, communication, and technical scores." },
    { question: "How do I schedule interviews?", answer: "Go to Candidates, find a candidate, and click the calendar icon. You can set a specific date/time, and the candidate receives an email invitation." },
    { question: "How do I review completed interviews?", answer: "Go to Interview Reviews. You'll see all completed sessions with AI scores, proctoring events (tab switches, etc.), and can add your final decision." },
    { question: "Can I export candidate data?", answer: "Go to Candidates or Pipeline. Look for export options (typically a download button). You can export as CSV for external analysis." },
    { question: "How does proctoring work?", answer: "Our system tracks: tab switches, video/mic status, and time spent per question. Suspicious events are flagged in Interview Reviews." },
    { question: "What skill weights should I use?", answer: "Set weights 1-10 for each required skill. Higher weight = more important for the role. The AI calculates match scores based on these weights." },
    { question: "How do I make a final decision?", answer: "Go to Interview Reviews → Select candidate → Mark as Selected/Rejected with notes. This updates the candidate's status in Pipeline." },
  ] : [
    { question: "How do I upload my resume?", answer: "Go to your Dashboard, click the upload button, and select your resume file (PDF or DOCX). The AI will analyze it and give you a match score for each job." },
    { question: "How does resume scoring work?", answer: "We analyze your resume against the job description skills and requirements. Your score shows how well your skills match the position. Higher scores = better match." },
    { question: "When will I get interview results?", answer: "After completing your interview, HR reviews your answers and scores. The decision appears in your Dashboard under 'My Results'. This usually takes 1-3 business days." },
    { question: "Can I retake an interview?", answer: "Each job usually allows one interview attempt. Check your Dashboard - if an interview is marked 'Ready' or 'In Progress', you can start or resume it." },
    { question: "How do I practice for interviews?", answer: "Go to your Dashboard and look for practice session options. You can practice with sample questions to improve your confidence before the real interview." },
    { question: "What do my scores mean?", answer: "Resume Score: How well your skills match the job. Interview Score: Your response quality during the interview. Final Score: Combined HR review. Scores above 65% are typically strong." },
    { question: "How do I change my applied job?", answer: "On your Dashboard, use the job selector dropdown to switch between jobs you've applied to. Each job has its own resume and interview process." },
    { question: "My resume won't upload - what should I do?", answer: "Make sure it's a PDF or DOCX file under 5MB. If it still fails, try a different file format or contact support." },
  ];

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="text-center space-y-4">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-2xl">
          <HelpCircle className="w-8 h-8 text-blue-600 dark:text-blue-400" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Frequently Asked Questions</h1>
        <p className="text-slate-500">Common questions about applying and interviewing</p>
      </div>

      <div className="space-y-3">
        {staticFAQs.map((faq, index) => (
          <FAQItem
            key={index}
            question={faq.question}
            answer={faq.answer}
            isOpen={openIndex === index}
            onToggle={() => setOpenIndex(openIndex === index ? null : index)}
          />
        ))}
      </div>
    </div>
  );
}