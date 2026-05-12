import { Inbox, Users, FileText, ClipboardList, BarChart3, Search, FolderOpen } from "lucide-react";

const ICONS = {
  default: Inbox,
  candidates: Users,
  jd: FileText,
  interviews: ClipboardList,
  analytics: BarChart3,
  search: Search,
  folder: FolderOpen,
};

export default function EmptyState({ 
  icon = "default", 
  title = "No data found", 
  description, 
  action: ActionComponent 
}) {
  const IconComponent = ICONS[icon] || ICONS.default;
  
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mb-4">
        <IconComponent size={28} className="text-slate-400 dark:text-slate-500" />
      </div>
      <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-300 mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm mb-4">{description}</p>
      )}
      {ActionComponent && <ActionComponent />}
    </div>
  );
}