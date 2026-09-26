import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import { SupportedDocs, Pipeline, Signals, Privacy, Benchmarks } from "./components/Sections";
import Footer from "./components/Footer";
import Wizard from "./components/wizard/Wizard";
import ScreeningHistory from "./components/ScreeningHistory";

export default function App() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="pt-16">
        <Hero />
        <SupportedDocs />
        <Pipeline />
        <Signals />

        <section id="testbench" className="w-full bg-surface py-20 px-6 md:px-12 border-t border-emerald-100">
          <div className="max-w-6xl mx-auto">
            <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-6">
              <div>
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-secondary-container text-primary font-label-sm uppercase tracking-wider mb-2 border border-emerald-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse" />
                  Try It Live
                </div>
                <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg">
                  Interactive Document Testing Lab
                </h2>
              </div>
              <p className="font-body-sm text-on-surface-variant max-w-md">
                See how our smart screening inspects documents and flags edits in real time.
              </p>
            </div>

            <Wizard />
          </div>
        </section>

        <ScreeningHistory />

        <Privacy />
        <Benchmarks />
      </main>
      <Footer />
    </div>
  );
}