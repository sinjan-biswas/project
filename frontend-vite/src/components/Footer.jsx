import { Shield, Circle } from "lucide-react";

const cols = [
  {
    title: "Forensic Engines",
    items: ["TamperNet ResNet18 CNN", "PaddleOCR & TrOCR Dual-Engine", "InsightFace buffalo_l Biometrics", "Real-ESRGAN & Zero-DCE"],
  },
  {
    title: "Standards & Ledger",
    items: ["Hyperledger Fabric Channels", "ICAO 9303 MRZ Compliance", "UIDAI 2048-Bit RSA Specs", "Zero-PII Private Data Collections"],
  },
  {
    title: "Developer Ecosystem",
    items: ["FastAPI REST & gRPC Specs", "Diagnostic Sandbox", "ONNX & PyTorch Inference", "Benchmarking Reports"],
  },
];

export default function Footer() {
  return (
    <footer className="w-full bg-[#11261a] text-secondary-fixed pt-16 pb-12 border-t border-emerald-950">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="flex flex-wrap items-center justify-between gap-4 pb-12 border-b border-emerald-900/40">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center">
              <Shield className="w-4 h-4 text-on-primary" />
            </div>
            <div>
              <span className="font-headline-sm text-white block">
                Secure<span className="text-secondary-fixed">ID</span>
              </span>
              <span className="font-body-sm text-emerald-300/70">
                Instant Identity Check & Fake Document Detection • v2.2
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/10 backdrop-blur-md">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-body-sm text-secondary-fixed">
              Hyperledger Fabric: screening-channel-global • Operational
            </span>
          </div>
        </div>

        <div className="grid gap-8 py-12 grid-cols-1 sm:grid-cols-3">
          {cols.map((col) => (
            <div key={col.title} className="flex flex-col gap-3">
              <span className="font-label-lg text-emerald-300 font-bold uppercase tracking-wider">
                {col.title}
              </span>
              {col.items.map((item) => (
                <a key={item} href="#" className="font-body-sm text-emerald-200/80 hover:text-white transition-colors">
                  {item}
                </a>
              ))}
            </div>
          ))}
        </div>

        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 font-body-sm text-emerald-300/60">
          <div>© 2024 Secure ID • Engineered for Sinjan Biswas Project & SIH • All rights reserved.</div>
          <div className="flex items-center gap-6">
            <a href="#" className="hover:text-white">Zero-Retention Privacy</a>
            <a href="#" className="hover:text-white">Terms</a>
            <a href="#" className="hover:text-white">Border Security Protocol</a>
          </div>
        </div>
      </div>
    </footer>
  );
}