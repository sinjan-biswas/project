import { useEffect, useState } from "react";
import StepTabs from "./StepTabs";
import Step1Upload from "./Step1Upload";
import Step2Liveness from "./Step2Liveness";
import Step3Results from "./Step3Results";

const SS_KEY = "screening_wizard_state";

const initial = {
  step: 1,
  screeningSessionId: null,
  stage1: null,     // /documents/validate response
  stage2: null,     // /documents/details response
  livenessSessionId: null,
  stage3: null,     // /screening/finalize response
  startedAt: null,
};

export default function Wizard() {
  const [state, setState] = useState(() => {
    try {
      const raw = sessionStorage.getItem(SS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        // Session TTL is 30 min on backend. Drop if older.
        if (parsed.startedAt && Date.now() - parsed.startedAt < 25 * 60 * 1000) {
          return parsed;
        }
      }
    } catch {}
    return initial;
  });

  useEffect(() => {
    try { sessionStorage.setItem(SS_KEY, JSON.stringify(state)); } catch {}
  }, [state]);

  const goTo = (step) => setState((s) => ({ ...s, step }));
  const patch = (partial) => setState((s) => ({ ...s, ...partial }));

  const reset = () => {
    try { sessionStorage.removeItem(SS_KEY); } catch {}
    setState({ ...initial, startedAt: Date.now() });
  };

  return (
    <div className="w-full">
      <StepTabs current={state.step} onJump={goTo} />

      {state.step === 1 && (
        <Step1Upload
          state={state}
          onComplete={(stage1, stage2, screeningSessionId) =>
            patch({ stage1, stage2, screeningSessionId, step: 2, startedAt: state.startedAt || Date.now() })
          }
        />
      )}

      {state.step === 2 && (
        <Step2Liveness
          screeningSessionId={state.screeningSessionId}
          stage1={state.stage1}
          onComplete={(livenessSessionId) =>
            patch({ livenessSessionId, step: 3 })
          }
          onBack={() => goTo(1)}
        />
      )}

      {state.step === 3 && (
        <Step3Results
          screeningSessionId={state.screeningSessionId}
          livenessSessionId={state.livenessSessionId}
          stage1={state.stage1}
          stage2={state.stage2}
          onFinal={(stage3) => patch({ stage3 })}
          onBack={() => goTo(2)}
          onRestart={reset}
        />
      )}
    </div>
  );
}