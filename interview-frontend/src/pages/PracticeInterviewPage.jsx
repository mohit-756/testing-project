import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Award, ArrowRight, Clock, MessageSquare, Play, RotateCcw,
  ShieldCheck, Target, Zap, CheckCircle2, AlertCircle,
  TrendingUp, Brain, Mic, ChevronRight, BarChart3,
} from "lucide-react";
import { candidateApi } from "../services/api";
import { cn } from "../utils/utils";

// ── Simple local answer scorer ────────────────────────────────────────────
function scoreLocalAnswer(question, answer) {
  if (!answer || answer.trim().length < 10) return { score: 0, grade: "Skipped", feedback: "No answer provided.", breakdown: { relevance: 0, depth: 0, clarity: 0 } };

  const words = answer.trim().split(/\s+/);
  const wc = words.length;

  // Relevance: keyword overlap with question
  const qWords = new Set(question.toLowerCase().split(/\W+/).filter((w) => w.length > 3));
  const aWords = new Set(answer.toLowerCase().split(/\W+/).filter((w) => w.length > 3));
  const overlap = [...qWords].filter((w) => aWords.has(w)).length;
  const relevance = Math.min(100, Math.round((overlap / Math.max(qWords.size, 1)) * 100 + 20));

  // Depth: word count & action verbs
  const actionVerbs = ["built", "implemented", "designed", "created", "improved", "reduced", "increased", "led", "managed", "developed", "deployed", "fixed", "analyzed", "optimized"];
  const verbHits = actionVerbs.filter((v) => answer.toLowerCase().includes(v)).length;
  const depth = Math.min(100, Math.round((wc < 10 ? 20 : wc < 30 ? 50 : wc < 60 ? 70 : 85) + verbHits * 5));

  // Clarity: unique word ratio, sentence structure
  const uniqueRatio = new Set(words.map((w) => w.toLowerCase())).size / wc;
  const clarity = Math.min(100, Math.round(uniqueRatio * 80 + (wc > 15 ? 20 : 0)));

  const overall = Math.round(relevance * 0.4 + depth * 0.35 + clarity * 0.25);
  const grade = overall >= 80 ? "Excellent" : overall >= 65 ? "Good" : overall >= 45 ? "Needs Work" : "Weak";

  const tips = [];
  if (relevance < 50) tips.push("Try to directly address what the question is asking.");
  if (depth < 50) tips.push("Add specific examples with measurable outcomes (e.g. 'reduced errors by 30%').");
  if (wc < 20) tips.push("Give a more detailed answer — aim for at least 3-4 sentences.");
  if (verbHits === 0) tips.push("Use action verbs like 'built', 'implemented', or 'improved' to show ownership.");
  if (clarity < 50) tips.push("Vary your word choice to avoid repetition.");
  if (tips.length === 0) tips.push("Great answer! Clear, specific, and well-structured.");

  return { score: overall, grade, feedback: tips[0], tips, breakdown: { relevance, depth, clarity } };
}

// ── Score badge ───────────────────────────────────────────────────────────
function GradeBadge({ grade, score }) {
  const styles = {
    Excellent: "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 border-emerald-200",
    Good: "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 border-blue-200",
    "Needs Work": "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 border-amber-200",
    Weak: "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border-red-200",
    Skipped: "bg-slate-100 dark:bg-slate-800 text-slate-500 border-slate-200",
  };
  return (
    <span className={cn("inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-black border", styles[grade] || styles.Skipped)}>
      {score > 0 && <span>{score}</span>}
      {grade}
    </span>
  );
}

// ── Breakdown bar ─────────────────────────────────────────────────────────
function BreakdownBar({ label, value, color }) {
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-[10px] font-bold text-slate-500 uppercase tracking-wider">
        <span>{label}</span><span>{value}%</span>
      </div>
      <div className="h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full transition-all duration-700", color)} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

export default function PracticeInterviewPage() {
  const [data, setData] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [timeLeft, setTimeLeft] = useState(90);
  const [isFinished, setIsFinished] = useState(false);
  const [answers, setAnswers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);
  const [currentFeedback, setCurrentFeedback] = useState(null);
  const [timerPaused, setTimerPaused] = useState(false);

  const questions = data?.practice?.questions || [];
  const activeQuestion = questions[currentIndex] || null;
  const tips = useMemo(() => data?.resume_advice?.rewrite_tips || [], [data]);

  async function loadPracticeKit() {
    setLoading(true); setError("");
    try {
      const response = await candidateApi.practiceKit();
      setData(response);
      setCurrentIndex(0); setAnswer(""); setTimeLeft(90);
      setIsFinished(false); setAnswers([]); setShowFeedback(false); setCurrentFeedback(null);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { loadPracticeKit(); }, []);

  // Submit answer and show feedback before advancing
  const handleSubmitAnswer = useCallback(() => {
    if (!activeQuestion || timerPaused) return;
    setTimerPaused(true);
    const result = scoreLocalAnswer(activeQuestion.text, answer);
    setCurrentFeedback(result);
    setShowFeedback(true);
  }, [activeQuestion, answer, timerPaused]);

  const handleNext = useCallback(() => {
    if (!activeQuestion) return;
    const result = currentFeedback || scoreLocalAnswer(activeQuestion.text, answer);
    setAnswers((prev) => [...prev, { q: activeQuestion.text, a: answer, topic: activeQuestion.topic, type: activeQuestion.type, ...result }]);
    setShowFeedback(false); setCurrentFeedback(null);
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((i) => i + 1);
      setAnswer(""); setTimeLeft(90); setTimerPaused(false);
    } else {
      setIsFinished(true);
    }
  }, [activeQuestion, answer, currentFeedback, currentIndex, questions.length]);

  // Timer
  useEffect(() => {
    if (loading || isFinished || !activeQuestion || timerPaused || showFeedback) return;
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) { handleSubmitAnswer(); return 90; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [activeQuestion, handleSubmitAnswer, isFinished, loading, timerPaused, showFeedback]);

  // ── Finished screen ───────────────────────────────────────────────────
  if (!loading && isFinished) {
    const scored = answers.filter((a) => a.score > 0);
    const avgScore = scored.length ? Math.round(scored.reduce((s, a) => s + a.score, 0) / scored.length) : 0;
    const grades = answers.reduce((acc, a) => { acc[a.grade] = (acc[a.grade] || 0) + 1; return acc; }, {});

    return (
      <div className="space-y-8 animate-in fade-in zoom-in duration-300 pb-12">
        {/* Hero result */}
        <div className="bg-white dark:bg-slate-900 rounded-[40px] border border-slate-200 dark:border-slate-800 shadow-sm p-10 text-center relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-50/50 via-transparent to-emerald-50/30 dark:from-blue-900/10 dark:to-emerald-900/5 pointer-events-none" />
          <div className="relative">
            <div className="w-24 h-24 rounded-[32px] bg-gradient-to-br from-emerald-400 to-blue-600 flex items-center justify-center mx-auto shadow-2xl shadow-emerald-100 dark:shadow-none mb-6">
              <Award size={48} className="text-white" />
            </div>
            <h1 className="text-4xl font-black text-slate-900 dark:text-white font-display">Practice Complete!</h1>
            <p className="text-slate-500 dark:text-slate-400 mt-2 text-lg">Here's your performance summary</p>

            <div className="flex items-center justify-center gap-8 mt-8">
              <div className="text-center">
                <div className="text-5xl font-black text-blue-600">{avgScore}</div>
                <div className="text-xs font-black text-slate-400 uppercase tracking-widest mt-1">Avg Score</div>
              </div>
              <div className="w-px h-16 bg-slate-200 dark:bg-slate-700" />
              <div className="text-center">
                <div className="text-5xl font-black text-slate-900 dark:text-white">{answers.length}</div>
                <div className="text-xs font-black text-slate-400 uppercase tracking-widest mt-1">Questions</div>
              </div>
              <div className="w-px h-16 bg-slate-200 dark:bg-slate-700" />
              <div className="text-center">
                <div className="text-5xl font-black text-emerald-600">{grades["Excellent"] || 0}</div>
                <div className="text-xs font-black text-slate-400 uppercase tracking-widest mt-1">Excellent</div>
              </div>
            </div>
          </div>
        </div>

        {/* Answer review */}
        <div className="space-y-4">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <BarChart3 size={20} className="text-blue-600" /> Answer Review
          </h2>
          {answers.map((item, idx) => (
            <div key={idx} className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 space-y-3">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <span className="w-7 h-7 bg-blue-50 dark:bg-blue-900/30 rounded-xl flex items-center justify-center text-blue-600 text-xs font-black">{idx + 1}</span>
                  <p className="text-sm font-bold text-slate-900 dark:text-white">{item.q}</p>
                </div>
                <GradeBadge grade={item.grade} score={item.score} />
              </div>
              {item.a ? (
                <>
                  <p className="text-sm text-slate-500 dark:text-slate-400 italic bg-slate-50 dark:bg-slate-800 rounded-xl px-4 py-3">"{item.a}"</p>
                  <div className="grid grid-cols-3 gap-3">
                    <BreakdownBar label="Relevance" value={item.breakdown?.relevance || 0} color="bg-blue-500" />
                    <BreakdownBar label="Depth" value={item.breakdown?.depth || 0} color="bg-emerald-500" />
                    <BreakdownBar label="Clarity" value={item.breakdown?.clarity || 0} color="bg-purple-500" />
                  </div>
                  <p className="text-xs text-slate-500 flex items-start gap-1.5">
                    <TrendingUp size={12} className="mt-0.5 flex-shrink-0 text-blue-500" />
                    {item.feedback}
                  </p>
                </>
              ) : (
                <p className="text-sm text-slate-400 italic">No answer recorded</p>
              )}
            </div>
          ))}
        </div>

        <div className="flex gap-4">
          <button type="button" onClick={loadPracticeKit} className="flex-1 flex items-center justify-center gap-2 py-4 border-2 border-slate-200 dark:border-slate-700 rounded-2xl font-bold text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-all">
            <RotateCcw size={18} /><span>Practice Again</span>
          </button>
          <Link to="/candidate" className="flex-1 flex items-center justify-center gap-2 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl font-bold shadow-lg shadow-blue-200 dark:shadow-none transition-all">
            <span>Back to Dashboard</span><ArrowRight size={18} />
          </Link>
        </div>
      </div>
    );
  }

  if (loading) return <p className="center muted">Loading practice kit…</p>;
  if (error && !data) return <p className="alert error">{error}</p>;
  if (!questions.length) return (
    <div className="space-y-6">
      {error && <p className="alert error">{error}</p>}
      <div className="bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm text-center">
        <Brain size={48} className="mx-auto text-slate-300 dark:text-slate-600 mb-4" />
        <h3 className="text-xl font-bold text-slate-900 dark:text-white">No practice kit yet</h3>
        <p className="text-slate-500 dark:text-slate-400 mt-2">Upload a resume and select a JD from the candidate dashboard first.</p>
        <Link to="/candidate" className="mt-6 inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-bold rounded-xl">Go to Dashboard</Link>
      </div>
    </div>
  );

  const timeColor = timeLeft < 15 ? "text-red-500" : timeLeft < 30 ? "text-amber-500" : "text-blue-600";

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 p-2.5 rounded-2xl text-white shadow-lg shadow-blue-200 dark:shadow-none"><Play size={20} fill="white" /></div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white font-display">AI Practice Mode</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">{data?.jd?.title || "Selected JD"} · {questions.length} questions with live feedback</p>
          </div>
        </div>
        <div className={cn("flex items-center gap-2 bg-white dark:bg-slate-900 px-5 py-3 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm font-mono font-black text-2xl", timeColor)}>
          <Clock size={18} className={timeColor} />
          {String(Math.floor(timeLeft / 60)).padStart(2, "0")}:{String(timeLeft % 60).padStart(2, "0")}
        </div>
      </div>

      {/* Progress dots */}
      <div className="flex items-center gap-1.5">
        {questions.map((_, i) => (
          <div key={i} className={cn("h-1.5 rounded-full transition-all duration-500",
            i === currentIndex ? "bg-blue-600 w-8" : i < currentIndex ? "bg-emerald-500 w-4" : "bg-slate-200 dark:bg-slate-700 w-4"
          )} />
        ))}
        <span className="ml-2 text-[10px] font-black text-slate-400 uppercase tracking-widest">
          {currentIndex + 1} / {questions.length}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main question area */}
        <div className="lg:col-span-2 space-y-4">

          {/* Question card */}
          <div className="bg-white dark:bg-slate-900 rounded-[32px] border border-slate-200 dark:border-slate-800 shadow-sm p-8 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1 h-full bg-blue-600 rounded-r" />
            <div className="pl-4">
              <div className="flex items-center gap-2 mb-4">
                <span className="px-2.5 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-lg text-[10px] font-black uppercase tracking-widest border border-blue-100 dark:border-blue-800/50">
                  {activeQuestion?.type || "Question"}
                </span>
                <span className="px-2.5 py-1 bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 rounded-lg text-[10px] font-black uppercase tracking-widest border border-slate-100 dark:border-slate-700">
                  {activeQuestion?.difficulty || "medium"}
                </span>
              </div>
              <h2 className="text-xl md:text-2xl font-bold text-slate-900 dark:text-white leading-tight">
                {activeQuestion?.text}
              </h2>
              <p className="text-xs text-slate-400 mt-3">{activeQuestion?.topic}</p>
            </div>
          </div>

          {/* Feedback overlay — shown after submitting */}
          {showFeedback && currentFeedback && (
            <div className={cn(
              "rounded-3xl border p-6 space-y-4 animate-in slide-in-from-bottom-2 duration-300",
              currentFeedback.score >= 80 ? "bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800"
              : currentFeedback.score >= 50 ? "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800"
              : "bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800"
            )}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {currentFeedback.score >= 65 ? <CheckCircle2 size={22} className="text-emerald-600 dark:text-emerald-400" /> : <AlertCircle size={22} className="text-amber-600 dark:text-amber-400" />}
                  <div>
                    <p className="font-black text-slate-900 dark:text-white text-lg">Score: {currentFeedback.score}/100</p>
                    <GradeBadge grade={currentFeedback.grade} score={currentFeedback.score} />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <BreakdownBar label="Relevance" value={currentFeedback.breakdown.relevance} color="bg-blue-500" />
                <BreakdownBar label="Depth" value={currentFeedback.breakdown.depth} color="bg-emerald-500" />
                <BreakdownBar label="Clarity" value={currentFeedback.breakdown.clarity} color="bg-purple-500" />
              </div>

              <ul className="space-y-1.5">
                {currentFeedback.tips.map((tip, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
                    <ChevronRight size={14} className="mt-0.5 flex-shrink-0 text-blue-500" />
                    {tip}
                  </li>
                ))}
              </ul>

              <button
                type="button"
                onClick={handleNext}
                className="w-full flex items-center justify-center gap-2 py-3.5 bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-black rounded-2xl hover:opacity-90 transition-all"
              >
                {currentIndex === questions.length - 1 ? "Finish & See Results" : "Next Question"}
                <ArrowRight size={16} />
              </button>
            </div>
          )}

          {/* Answer textarea */}
          {!showFeedback && (
            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-black text-slate-500 dark:text-slate-400 uppercase tracking-widest flex items-center gap-2">
                  <MessageSquare size={14} className="text-blue-500" /> Your Answer
                </h4>
                <span className="text-[10px] font-black text-slate-400">{answer.split(/\s+/).filter(Boolean).length} words</span>
              </div>
              <textarea
                className="w-full h-40 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-4 text-sm text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-blue-500 transition-all resize-none"
                placeholder="Type your practice answer here… aim for 3-5 sentences with specific examples."
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
              />
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setAnswer("")}
                  className="px-5 py-3 border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 font-bold rounded-2xl text-sm transition-all"
                >
                  Clear
                </button>
                <button
                  type="button"
                  onClick={handleSubmitAnswer}
                  className="flex-1 flex items-center justify-center gap-2 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-2xl shadow-lg shadow-blue-200 dark:shadow-none transition-all"
                >
                  <Zap size={16} />
                  {currentIndex === questions.length - 1 ? "Submit & Get Feedback" : "Submit & Get Feedback"}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Tips */}
          <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <h4 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <Target size={16} className="text-blue-600" /> Answer Tips
            </h4>
            <ul className="space-y-3">
              {(tips.length ? tips.slice(0, 3) : [
                "Start with the action you took, not the background.",
                "Include one measurable outcome (%, time, users, $).",
                "Mention the skill from the JD somewhere in your answer.",
              ]).map((tip, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                  <div className="w-4 h-4 rounded-md bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 font-black text-[9px] flex-shrink-0 mt-0.5">{i + 1}</div>
                  {tip}
                </li>
              ))}
            </ul>
          </div>

          {/* Session progress */}
          <div className="bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <h4 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <BarChart3 size={16} className="text-emerald-500" /> Session Progress
            </h4>
            <div className="space-y-3">
              {answers.map((a, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-[10px] font-black text-slate-400 w-6">Q{i + 1}</span>
                  <div className="flex-1 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div className={cn("h-full rounded-full", a.score >= 80 ? "bg-emerald-500" : a.score >= 50 ? "bg-blue-500" : a.score > 0 ? "bg-amber-500" : "bg-slate-300")} style={{ width: `${a.score}%` }} />
                  </div>
                  <span className="text-[10px] font-black text-slate-500 w-8 text-right">{a.score > 0 ? `${a.score}%` : "—"}</span>
                </div>
              ))}
              {answers.length === 0 && <p className="text-xs text-slate-400 italic">Answer questions to see progress here</p>}
            </div>
          </div>

          {/* Context */}
          <div className="bg-slate-900 dark:bg-slate-800 p-6 rounded-3xl text-white">
            <ShieldCheck size={28} className="mb-3 text-blue-400" />
            <p className="text-xs font-black text-slate-400 uppercase tracking-widest mb-1">Practice Context</p>
            <p className="font-bold">{data?.jd?.title || "Selected JD"}</p>
            <p className="text-sm text-slate-400 mt-2">Score preview: <span className="text-white font-black">{Math.round(Number(data?.score_preview || 0))}%</span></p>
            <p className="text-sm text-slate-400">{questions.length} questions total</p>
          </div>
        </div>
      </div>
    </div>
  );
}
