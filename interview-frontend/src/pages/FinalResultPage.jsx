import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";

export default function FinalResultPage() {
  const navigate = useNavigate();

  useEffect(() => {
    navigate("/candidate");
  }, [navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900">
      <div className="text-center">
        <div className="animate-spin w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto mb-4" />
        <p className="text-slate-600 dark:text-slate-400">Redirecting to your applications...</p>
        <a href="/candidate" className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
          Go to Dashboard <ArrowRight size={16} />
        </a>
      </div>
    </div>
  );
}