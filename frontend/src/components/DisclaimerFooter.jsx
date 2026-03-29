import { Info } from 'lucide-react';

export default function DisclaimerFooter() {
  return (
    <footer className="px-5 py-2.5 mt-auto">
      <div className="flex items-center gap-1.5 group">
        <Info className="w-3 h-3 text-slate-500/60 flex-shrink-0 group-hover:text-slate-500/80 transition-colors" />
        <span className="text-[11px] text-slate-500/60 group-hover:text-slate-500/80 transition-colors">
          For educational purposes only. Not SEBI-registered investment advice.
        </span>
      </div>
    </footer>
  );
}
