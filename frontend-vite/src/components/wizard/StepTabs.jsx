const steps = [
  { n: 1, title: "Step 1: Choose Document", subtitle: "Upload or Select Sample" },
  { n: 2, title: "Step 2: Take Live Selfie", subtitle: "Fast Real Person Check" },
  { n: 3, title: "Step 3: See Instant Results", subtitle: "Simple Safety Report" },
];

export default function StepTabs({ current, onJump }) {
  return (
    <div className="mb-8 rounded-2xl bg-surface-container-low p-3 md:p-4 border border-emerald-200 shadow-sm">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {steps.map((s) => {
          const active = s.n === current;
          const done = s.n < current;
          return (
            <button
              key={s.n}
              type="button"
              onClick={() => (done || active) && onJump(s.n)}
              className={`flex items-center gap-3 p-3 rounded-xl text-left transition-all ${
                active
                  ? "bg-surface-container-high border-2 border-primary"
                  : done
                  ? "bg-secondary-container/50 border border-secondary/30 hover:bg-secondary-container"
                  : "bg-surface-container-lowest border border-outline-variant/30 hover:bg-surface-container-low"
              }`}
            >
              <div
                className={`w-8 h-8 rounded-full font-bold text-xs flex items-center justify-center font-mono shrink-0 ${
                  active
                    ? "bg-primary text-on-primary"
                    : done
                    ? "bg-secondary text-on-secondary"
                    : "bg-surface-container-high text-primary"
                }`}
              >
                {String(s.n).padStart(2, "0")}
              </div>
              <div className="min-w-0">
                <div className="font-label-sm text-xs font-bold text-on-surface truncate">
                  {s.title}
                </div>
                <div className="font-mono text-[10px] text-on-surface-variant truncate">
                  {s.subtitle}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}