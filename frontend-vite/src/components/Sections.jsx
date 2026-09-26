import {
  Book, Plane, Fingerprint, CreditCard, BadgeCheck, Vote, UserCheck,
  CheckCircle2, Wand2, SpellCheck, Gavel, Search, ScanFace, ShieldCheck, Lock,
  Radar, Zap, Image as ImageIcon, User, Type, Stamp, History,
} from "lucide-react";
import { Card, Pill } from "./ui";

/* ─── Supported Documents ─── */
const docs = [
  { icon: Book, name: "Passport", sub: "International travel IDs" },
  { icon: Plane, name: "Visa", sub: "Entry & travel permits" },
  { icon: Fingerprint, name: "Aadhaar Card", sub: "Govt ID with QR code" },
  { icon: CreditCard, name: "PAN Card", sub: "Tax & identity card" },
  { icon: BadgeCheck, name: "Driving License", sub: "State driver licenses" },
  { icon: Vote, name: "Voter ID", sub: "Voter registration cards" },
  { icon: UserCheck, name: "Work Permits", sub: "Official employment passes" },
];

export function SupportedDocs() {
  return (
    <section className="w-full bg-[#11261a] text-white px-6 py-12 border-t border-emerald-900/50">
      <div className="max-w-6xl mx-auto flex flex-col items-center">
        <div className="text-center mb-6">
          <span className="font-label-sm uppercase tracking-widest text-secondary-container">
            Supported Documents
          </span>
          <p className="font-headline-sm text-lg md:text-xl mt-1">
            Works with all your everyday identity documents
          </p>
        </div>
        <div className="w-full grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          {docs.map(({ icon: Icon, name, sub }) => (
            <div
              key={name}
              className="flex flex-col items-center gap-1.5 p-3 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/10 transition-all text-center group cursor-pointer"
            >
              <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center text-emerald-300 group-hover:scale-110 transition-transform">
                <Icon className="w-6 h-6" />
              </div>
              <span className="font-label-sm text-xs font-bold text-white">{name}</span>
              <span className="font-mono text-[9px] text-white/60 leading-tight">{sub}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── 8-Layer Pipeline ─── */
const layers = [
  { n: "01", label: "Quality Check", title: "1. Clear Picture Check", body: "Checks if your photo is sharp, well-lit, and easy to read. Fixes dark or tilted angles automatically.", tag: "Sharpness & Angle Ready", icon: ImageIcon },
  { n: "02", label: "Auto-Clean", title: "2. Image Clean-up", body: "Cleans up shadows, sharpens blurry text, and brightens dim photos so nothing gets missed.", tag: "Auto-Brighten & Clarity", icon: Wand2 },
  { n: "03", label: "Reading", title: "3. Smart Text Reading", body: "Instantly reads names, dates, ID numbers, and codes accurately, even on wrinkled or damaged cards.", tag: "Fast & Accurate Reader", icon: SpellCheck },
  { n: "04", label: "Integrity", title: "4. Official Rules Check", body: "Checks that dates make sense, document numbers follow official government rules, and passes haven't expired.", tag: "Govt Rules & Validity", icon: Gavel },
  { n: "05", label: "Anti-Tamper", title: "5. Fake & Tamper Spotter", body: "Looks closely for replaced photos, altered names or numbers, fake government stamps, and digital photoshop edits.", tag: "5 Multi-Layer Clues", icon: Search },
  { n: "06", label: "Identity", title: "6. Face Match", body: "Compares the ID photo against a real-time selfie to make sure the person holding the card is the real owner.", tag: "99%+ Accurate Comparison", icon: ScanFace },
  { n: "07", label: "Verdict", title: "7. Clear Safety Score", body: "Gives a simple safety verdict: Approved, Needs a Quick Human Review, or Rejected — with plain explanations.", tag: "Clear & Plain Reasoning", icon: ShieldCheck },
  { n: "08", label: "Security", title: "8. Secure Record Keeping", body: "Creates a permanent, private, and tamper-proof safety receipt so your verification records can never be faked.", tag: "100% Private & Tamper-Proof", icon: Lock },
];

export function Pipeline() {
  return (
    <section id="pipeline" className="w-full bg-surface-container-low py-24 px-6 md:px-12">
      <div className="max-w-6xl mx-auto flex flex-col items-center text-center mb-16">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container text-primary font-label-sm uppercase tracking-wider mb-4 border border-emerald-200">
          <CheckCircle2 className="w-4 h-4" /> How It Works
        </div>
        <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface max-w-3xl tracking-tight">
          How We Verify Your Documents in 8 Simple Steps
        </h2>
        <p className="font-body-md text-on-surface-variant max-w-2xl mt-4">
          Every document goes through a fast, automated security check to confirm it is genuine and untampered.
        </p>
      </div>

      <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {layers.map(({ n, label, title, body, tag, icon: Icon }) => (
          <Card key={n} className="p-6 flex flex-col justify-between shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="w-8 h-8 rounded-full bg-surface-container-low text-primary font-bold text-sm flex items-center justify-center font-mono">
                  {n}
                </span>
                <span className="font-label-sm text-[10px] text-primary uppercase tracking-wider px-2 py-0.5 rounded-full bg-surface-container-low">
                  {label}
                </span>
              </div>
              <h3 className="font-headline-sm text-lg font-bold mb-2">{title}</h3>
              <p className="font-body-sm text-on-surface-variant leading-relaxed">{body}</p>
            </div>
            <div className="mt-6 pt-3 border-t border-emerald-100 font-mono text-[11px] text-secondary font-semibold flex items-center gap-1">
              <Icon className="w-3.5 h-3.5" /> {tag}
            </div>
          </Card>
        ))}
      </div>
    </section>
  );
}

/* ─── 5-Signal Tampering Fusion ─── */
const signals = [
  { weight: 45, title: "Edited Pixels & Photoshop", body: "Spots erased spots, cut-and-pasted parts, and subtle digital image retouching.", tag: "Image Retouching Check", icon: ImageIcon },
  { weight: 20, title: "Swapped Photos", body: "Detects pasted portraits, mismatched edges, and AI-generated faces.", tag: "Portrait & AI Face Check", icon: User },
  { weight: 15, title: "Altered Text & Numbers", body: "Catches mismatched fonts, uneven letters, and changed birth dates or names.", tag: "Font & Letter Alignment", icon: Type },
  { weight: 10, title: "Fake Stamps & Seals", body: "Verifies official government watermarks, crests, and holographic emblems.", tag: "Official Seal Verification", icon: Stamp },
  { weight: 10, title: "File History & Camera Data", body: "Checks the file's digital background to see if image-editing software was used.", tag: "Original File Verification", icon: History },
];

export function Signals() {
  return (
    <section id="engines" className="w-full bg-surface py-20 px-6 md:px-12">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-6">
          <div>
            <span className="font-label-sm text-secondary uppercase tracking-wider">Deep Dive</span>
            <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg mt-1">
              How We Catch Even the Cleverest Fakes
            </h2>
          </div>
          <p className="font-body-sm text-on-surface-variant max-w-md">
            Instead of relying on just one check, we inspect five distinct clues to guarantee your documents are original.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {signals.map(({ weight, title, body, tag, icon: Icon }) => (
            <div key={title} className="rounded-2xl bg-surface-container-low p-5 border border-emerald-100 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="font-mono text-xs font-bold text-primary bg-secondary-container px-2 py-0.5 rounded">
                    {weight}% INFLUENCE
                  </span>
                  <Icon className="w-5 h-5 text-primary" />
                </div>
                <h4 className="font-bold text-sm mb-1">{title}</h4>
                <p className="font-body-sm text-xs text-on-surface-variant">{body}</p>
              </div>
              <div className="mt-4 pt-3 border-t border-emerald-200/50">
                <div className="h-1.5 w-full bg-emerald-200 rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full" style={{ width: `${weight}%` }} />
                </div>
                <span className="font-mono text-[10px] text-secondary font-bold block mt-1">{tag}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── Privacy & Security ─── */
const privacy = [
  { icon: Radar, title: "Instant Fraud Alerts", body: "Stops identity thieves from using stolen cards in multiple places at the same time.", tag: "Real-Time Protection" },
  { icon: Lock, title: "Your Privacy Comes First", body: "We never store your personal data in public. Sensitive details are locked safely and auto-deleted in 90 days.", tag: "Safe & Private" },
  { icon: Zap, title: "Fast & Reliable", body: "Checks are completed in under 5 seconds with round-the-clock availability.", tag: "Ultra-Fast Response" },
];

export function Privacy() {
  return (
    <section id="blockchain" className="w-full bg-surface-container-low py-20 px-6 md:px-12">
      <div className="max-w-6xl mx-auto">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="font-label-sm text-secondary uppercase tracking-wider">Privacy & Security</span>
          <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg mt-2 tracking-tight">
            Bank-Grade Privacy & Fraud Prevention
          </h2>
          <p className="font-body-md text-on-surface-variant mt-3">
            Built to protect your sensitive personal details while keeping bad actors out.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {privacy.map(({ icon: Icon, title, body, tag }) => (
            <Card key={title} className="p-8 flex flex-col justify-between hover:shadow-xl transition-all">
              <div>
                <div className="w-12 h-12 rounded-2xl bg-surface-container-high flex items-center justify-center text-primary mb-6">
                  <Icon className="w-7 h-7" />
                </div>
                <h3 className="font-headline-sm text-xl font-bold mb-3">{title}</h3>
                <p className="font-body-md text-on-surface-variant leading-relaxed">{body}</p>
              </div>
              <div className="mt-6 pt-4 border-t border-emerald-100 flex items-center justify-between text-xs font-mono text-secondary font-bold">
                <span>{tag}</span>
                <CheckCircle2 className="w-4 h-4" />
              </div>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── Benchmarks ─── */
const stats = [
  { value: "Under 5s", label: "Typical Verification Time", sub: "Instant, automated results" },
  { value: "99.8%", label: "Fakes Caught Accurately", sub: "Tested on thousands of real-world scans" },
  { value: "99%+", label: "Accurate Face Matching", sub: "Matches live selfies with ID photos" },
  { value: "Zero Leaks", label: "No personal info stored publicly", sub: "Fully private & auto-deleted" },
];

export function Benchmarks() {
  return (
    <section id="benchmarks" className="w-full bg-surface-container-lowest py-20 px-6 md:px-12 border-y border-emerald-100">
      <div className="max-w-6xl mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {stats.map((s) => (
            <div key={s.label} className="flex flex-col items-center">
              <div className="font-headline-hero text-[44px] md:text-[54px] font-extrabold text-primary leading-tight">
                {s.value}
              </div>
              <div className="font-headline-sm mt-1">{s.label}</div>
              <div className="font-body-sm text-on-surface-variant mt-1">{s.sub}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}