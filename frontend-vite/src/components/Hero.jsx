import { ArrowRight, HelpCircle, Gauge, Lock, UserCheck, ShieldCheck, Camera, Contrast, RefreshCw, ScanFace, QrCode, CheckCircle2, Radio } from "lucide-react";
import { Pill } from "./ui";

const chips = [
  { icon: Gauge, label: "Fast 5-Second Check", color: "text-emerald-600" },
  { icon: ShieldCheck, label: "Catches Photo & Text Edits", color: "text-teal-600" },
  { icon: Lock, label: "100% Private & Tamper-Proof", color: "text-emerald-700" },
  { icon: UserCheck, label: "Instant Face Match", color: "text-emerald-600" },
];

export default function Hero() {
  return (
    <section className="relative w-full overflow-hidden bg-gradient-to-b from-[#b2f0c5] via-[#cbf5d7] to-[#e9ffec] pt-32 pb-24 px-4 sm:px-6">
      <div className="absolute top-12 left-1/2 -translate-x-1/2 w-[720px] h-[480px] bg-secondary-fixed/40 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute bottom-10 left-1/4 w-[360px] h-[360px] bg-[#8fe3a8]/50 blur-[100px] rounded-full pointer-events-none" />

      <div className="max-w-6xl mx-auto flex flex-col items-center text-center relative z-10">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-surface-container-lowest/80 backdrop-blur-md mb-8 shadow-sm border border-emerald-300/60">
          <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse" />
          <span className="font-label-sm uppercase tracking-wider text-primary">
            Smart Identity Protection • Instant & Effortless • v2.2
          </span>
        </div>

        <h1 className="font-headline-hero text-headline-hero-mobile md:text-headline-hero tracking-tight text-[#1a3826] max-w-4xl drop-shadow-sm">
          Instant Identity Check & Fake Document Detection
        </h1>

        <p className="font-body-lg text-on-surface-variant max-w-3xl mt-6 leading-relaxed">
          Verify ID cards, passports, and documents in just seconds. Our smart system
          instantly spots fakes, catches tampered photos or text, and matches faces —
          keeping verification safe, fast, and simple.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
          <a
            href="#testbench"
            className="group inline-flex items-center gap-3 px-8 py-3.5 rounded-full bg-primary hover:bg-[#143820] text-on-primary font-label-lg shadow-punch hover:-translate-y-0.5 transition-all"
          >
            <span className="font-bold">Check a Document</span>
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </a>
          <a
            href="#pipeline"
            className="inline-flex items-center gap-2 px-6 py-3.5 rounded-full bg-surface-container-lowest/90 backdrop-blur-md text-primary font-label-lg hover:bg-surface-container-lowest border border-emerald-200 shadow-sm transition-all"
          >
            <HelpCircle className="w-4 h-4" />
            <span className="font-semibold">See How It Works</span>
          </a>
        </div>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-2.5 text-xs text-primary">
          {chips.map(({ icon: Icon, label, color }) => (
            <span
              key={label}
              className="px-3.5 py-1.5 rounded-full bg-surface-container-lowest/80 backdrop-blur-sm border border-emerald-200 font-mono flex items-center gap-1.5 shadow-sm"
            >
              <Icon className={`w-4 h-4 ${color}`} />
              {label}
            </span>
          ))}
        </div>
      </div>

      <div className="relative w-full max-w-7xl mx-auto mt-12 flex justify-center items-center pointer-events-none select-none">
        <span className="font-headline-hero text-[120px] sm:text-[180px] md:text-[230px] lg:text-[290px] font-extrabold tracking-tighter watermark-text leading-none whitespace-nowrap uppercase">
          FORENSIC
        </span>
        <div className="absolute top-8 sm:top-12 md:top-14 z-20 w-[300px] sm:w-[330px] md:w-[360px] pointer-events-auto">
          <PhoneMockup />
        </div>
      </div>
    </section>
  );
}

function PhoneMockup() {
  return (
    <div className="relative mx-auto rounded-[3.25rem] p-3 bg-gradient-to-b from-[#1a3826] via-[#102418] to-[#07130b] shadow-[0_30px_90px_rgba(10,30,18,0.45)] border border-emerald-500/30">
      <div className="relative rounded-[2.85rem] overflow-hidden bg-black aspect-[9/19.2] flex flex-col justify-between p-3.5">
        {/* Dynamic island */}
        <div className="absolute top-2.5 left-1/2 -translate-x-1/2 w-28 h-6 bg-black rounded-full z-40 flex items-center justify-between px-2.5 border border-white/10">
          <div className="w-2.5 h-2.5 rounded-full bg-[#142d1f]" />
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="font-mono text-[9px] text-white/80">PORT-CAM 01</span>
          </div>
        </div>

        <div className="flex items-center justify-between text-white font-mono text-[12px] pt-1 px-3 z-30">
          <span className="font-bold">14:22 UTC</span>
          <div className="flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5" />
            <Lock className="w-3.5 h-3.5" />
          </div>
        </div>

        <div className="relative flex-1 rounded-2xl overflow-hidden mt-3 bg-gradient-to-br from-[#0c2618] via-[#091b11] to-[#040d08] flex flex-col justify-between p-3 border border-emerald-500/20">
          <div className="absolute inset-0 opacity-20 pointer-events-none bg-[radial-gradient(#8fe3a8_1px,transparent_1px)] [background-size:14px_14px]" />

          <div className="relative z-10 flex items-center justify-between">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/15 backdrop-blur-md border border-white/10">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span className="font-mono text-[10px] text-white uppercase tracking-wider">
                Passport / Aadhaar
              </span>
            </div>
            <div className="px-2 py-0.5 rounded bg-emerald-500/30 text-emerald-300 font-mono text-[9px] font-bold border border-emerald-400/40">
              GATE: PASSED
            </div>
          </div>

          <div className="relative my-auto rounded-xl p-3 bg-white/95 text-on-surface shadow-2xl border border-emerald-200">
            <div className="absolute left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-emerald-400 to-transparent animate-pulse shadow-[0_0_12px_#34d399]" />

            <div className="flex items-center justify-between pb-1.5 border-b border-emerald-100">
              <div className="flex items-center gap-1.5">
                <div className="w-4 h-4 rounded-full bg-primary flex items-center justify-center">
                  <ShieldCheck className="w-2.5 h-2.5 text-white" />
                </div>
                <span className="font-mono text-[10px] font-bold uppercase tracking-wider">
                  ICAO DOC 9303 • MRZ
                </span>
              </div>
              <span className="font-mono text-[9px] text-secondary font-bold">TYPE P &lt; IND</span>
            </div>

            <div className="flex gap-2.5 items-center mt-2">
              <div className="relative w-14 h-16 rounded-lg bg-surface-container-high flex-shrink-0 border border-emerald-500 overflow-hidden">
                <div className="w-full h-full bg-gradient-to-br from-emerald-200 to-emerald-100 flex items-center justify-center">
                  <ScanFace className="w-6 h-6 text-primary" />
                </div>
                <div className="absolute top-0 right-0 bg-emerald-600 text-white text-[8px] px-1 font-bold rounded-bl">
                  94.2%
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-mono text-[10px] font-bold truncate">SHARMA, ADITI</div>
                <div className="font-mono text-[9px] text-on-surface-variant">
                  P# Z9048122 • DOB 14/08/94
                </div>
                <div className="mt-1 font-mono text-[8px] bg-emerald-50 text-primary px-1.5 py-0.5 rounded border border-emerald-100 truncate">
                  P&lt;INDSHARMA&lt;&lt;ADITI&lt;&lt;&lt;&lt;&lt;
                </div>
              </div>
              <div className="w-11 h-11 rounded bg-white flex items-center justify-center border border-emerald-200 relative">
                <QrCode className="w-7 h-7 text-primary" />
                <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-emerald-500 rounded-full flex items-center justify-center text-[8px] text-white">
                  ✓
                </span>
              </div>
            </div>

            <div className="mt-2 pt-1.5 border-t border-emerald-100 grid grid-cols-2 gap-1 text-[8.5px] font-mono">
              <span className="text-secondary font-medium">Blur: 142.8 | Skew: 0.4°</span>
              <span className="text-right text-emerald-700 font-bold">Tamper: 0.04 (Clean)</span>
            </div>
          </div>

          <div className="relative z-10 flex flex-col gap-1.5">
            <div className="bg-black/75 backdrop-blur-md rounded-xl p-2 text-white border border-white/10 space-y-1">
              <div className="flex items-center justify-between text-[10px]">
                <span className="flex items-center gap-1 font-mono text-emerald-300">
                  <ScanFace className="w-3 h-3" /> Face Match: 94.2%
                </span>
                <span className="font-mono text-emerald-200 text-[9px]">buffalo_l 512-D</span>
              </div>
              <div className="flex items-center justify-between text-[9px] font-mono border-t border-white/10 pt-1 text-white/70">
                <span className="truncate">Blockchain: Fabric TX #8fbc4e</span>
                <span className="text-emerald-400 font-bold ml-1">COMMITTED</span>
              </div>
            </div>
            <div className="flex items-center justify-around py-0.5">
              <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center text-white">
                <Contrast className="w-3.5 h-3.5" />
              </div>
              <div className="w-9 h-9 rounded-full bg-white flex items-center justify-center shadow-lg">
                <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-white">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
              </div>
              <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center text-white">
                <RefreshCw className="w-3.5 h-3.5" />
              </div>
            </div>
          </div>
        </div>

        <div className="w-32 h-1 bg-white/40 rounded-full mx-auto mt-2" />
      </div>
    </div>
  );
}