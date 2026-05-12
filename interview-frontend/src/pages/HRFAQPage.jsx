import { useState } from "react";
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

export default function HRFAQPage() {
  const [openIndex, setOpenIndex] = useState(null);

  const staticFAQs = [
    { question: "How do I create a new job description?", answer: "Go to JD Management → Click 'Add JD' or 'Create Job'. Fill in the job title, description, required skills (with weights 1-10), and interview settings. Save to publish." },
    { question: "How do I edit or update an existing job?", answer: "Go to JD Management, find the job you want to edit, and click the edit icon. Modify the details and save changes. Note: Changes won't affect ongoing interviews." },
    { question: "How do I set skill requirements and weights?", answer: "When creating/editing a JD, add skills and set weights (1-10). Higher weight = more important for the role. The AI uses these weights to calculate resume match scores." },
    { question: "How do I view and filter candidate applications?", answer: "Go to Candidates page. Use filters to narrow down by job, status, score range, or date. You can also search by name or email." },
    { question: "How do I review resumes and AI scores?", answer: "Click on any candidate to view their profile. You'll see their resume, AI-generated match score, skill breakdown, and application status." },
    { question: "How do I accept or reject candidates?", answer: "Go to Pipeline or Candidates. Select a candidate and choose 'Accept' or 'Reject'. You can add notes explaining your decision." },
    { question: "How do I schedule interviews for candidates?", answer: "Go to Candidates, find the candidate, and click the calendar icon. Select a date/time and send the interview invitation. The candidate receives an email." },
    { question: "How do I set interview dates and times?", answer: "When scheduling, you can choose from available slots or set a custom date/time. Make sure to consider the candidate's timezone." },
    { question: "How do I manage interview slots?", answer: "In the scheduling modal, view available slots for each candidate. You can configure slot duration in JD Management under interview settings." },
    { question: "How do I review completed interviews?", answer: "Go to Interview Reviews. Click on a completed interview to see AI scores, answer transcriptions, proctoring logs, and candidate performance." },
    { question: "How do I view proctoring logs and activity?", answer: "In Interview Reviews, click on a completed session. The proctoring tab shows tab switches, video/mic status, time per question, and any suspicious events." },
    { question: "How do I make hire/no-hire decisions?", answer: "In Interview Reviews, select a candidate and click 'Hire' or 'No Hire'. Add your notes and finalize the decision. This updates the candidate's status in Pipeline." },
    { question: "How do I move candidates through stages?", answer: "In Pipeline, drag and drop candidates between stages (Applied → Screening → Interview → Offer → Hired). Or click the candidate and select a new stage." },
    { question: "How do I use the kanban board?", answer: "Pipeline shows candidates in columns by stage. Drag cards to move candidates. Click a card to view details or change status." },
    { question: "How do I track candidate progress?", answer: "Use the Pipeline view to see all candidates and their current stage. Filter by job or search by name to find specific candidates." },
    { question: "What analytics are available?", answer: "Reports page shows hiring metrics: application counts, interview completion rates, selection rates, time-to-hire, and source effectiveness." },
    { question: "How do I generate reports?", answer: "Go to Reports. Select the report type, date range, and filters. Click 'Generate' or 'Export' to download data as CSV." },
    { question: "What metrics can be tracked?", answer: "Track: total applications, interview rates, offer acceptance rate, candidate sources, average scores, and pipeline conversion funnel." },
  ];

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="text-center space-y-4">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-2xl">
          <HelpCircle className="w-8 h-8 text-blue-600 dark:text-blue-400" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">HR FAQ</h1>
        <p className="text-slate-500">Common questions and guides for HR management</p>
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