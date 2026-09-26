export function Button({ children, variant = "primary", size = "md", className = "", ...props }) {
  const base =
    "inline-flex items-center justify-center gap-2 font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none";
  const sizes = {
    sm: "px-4 py-2 text-[13px] rounded-full",
    md: "px-5 py-2.5 text-label-lg rounded-full",
    lg: "px-8 py-3.5 text-label-lg rounded-full",
  };
  const variants = {
    primary:
      "bg-primary text-on-primary shadow-punch hover:bg-[#143820] hover:-translate-y-0.5",
    secondary:
      "bg-surface-container-lowest text-primary border border-emerald-200 shadow-sm hover:bg-surface-container-lowest",
    ghost:
      "bg-surface-container-high text-on-surface hover:bg-surface-container",
    outline:
      "bg-transparent text-on-surface border border-outline-variant hover:bg-surface-container-low",
  };
  return (
    <button className={`${base} ${sizes[size]} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Pill({ children, tone = "neutral", className = "" }) {
  const tones = {
    neutral: "bg-surface-container-high text-on-surface-variant",
    success: "bg-emerald-100 text-emerald-800",
    warn: "bg-amber-100 text-amber-800",
    danger: "bg-red-100 text-red-800",
    primary: "bg-secondary-container text-primary",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-mono text-[10px] font-bold uppercase tracking-wide ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function Card({ children, className = "", ...props }) {
  return (
    <div
      className={`bg-surface-container-lowest rounded-2xl border border-[#c3e2c9] shadow-sm ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}