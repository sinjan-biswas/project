import { ShieldCheck, ArrowRight, Gavel } from "lucide-react";

const links = [
  { label: "How It Works", href: "#pipeline" },
  { label: "Fake Detection", href: "#engines" },
  { label: "Tamper Proof", href: "#blockchain" },
  { label: "Try It Live", href: "#testbench", badge: "Free" },
  { label: "Accuracy", href: "#benchmarks" },
  { label: "For Developers", href: "#api-specs" },
];

export default function Navbar() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 pt-4 px-4">
      <div className="h-16 max-w-[1400px] mx-auto px-5 lg:px-6 glass shadow-soft border border-emerald-100 rounded-full flex items-center justify-between gap-4">
        {/* Brand */}
        <a href="#" className="flex items-center gap-2.5 shrink-0">
          <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-primary to-[#2a593e] flex items-center justify-center shadow-punch">
            <ShieldCheck className="w-4 h-4 text-on-primary" />
          </div>
          <span className="font-headline-sm text-on-surface tracking-tight whitespace-nowrap">
            Secure<span className="text-secondary font-bold">ID</span>
          </span>
        </a>

        {/* Nav links */}
        <nav className="hidden lg:flex items-center gap-5 xl:gap-6">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-[13px] font-semibold text-on-surface-variant hover:text-on-surface transition-colors whitespace-nowrap flex items-center gap-1.5"
            >
              {l.label}
              {l.badge && (
                <span className="bg-secondary-container text-secondary text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-full leading-none">
                  {l.badge}
                </span>
              )}
            </a>
          ))}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-3 shrink-0">
          <a
            href="#testbench"
            className="hidden xl:inline-flex items-center gap-1.5 text-[13px] font-semibold text-on-surface-variant hover:text-on-surface whitespace-nowrap"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse" />
            Try Demo
          </a>
          <a
            href="#testbench"
            className="bg-primary hover:bg-[#143820] text-on-primary px-4 py-2 rounded-full text-[13px] font-semibold shadow-punch hover:-translate-y-0.5 transition-all flex items-center gap-1.5 whitespace-nowrap"
          >
            Check a Document
            <ArrowRight className="w-3.5 h-3.5" />
          </a>
          <div className="hidden md:flex w-8 h-8 rounded-full bg-surface-container-high items-center justify-center text-primary shrink-0">
            <Gavel className="w-3.5 h-3.5" />
          </div>
        </div>
      </div>
    </header>
  );
}