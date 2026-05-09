import { useEffect, useState } from "react";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

const DISMISSED_KEY = "lw_pwa_install_dismissed";

/** PWA 설치 프롬프트 훅 — `beforeinstallprompt`가 한 번 발생한 뒤에만 동작. */
export function usePwaInstall(): {
  canInstall: boolean;
  promptInstall: () => Promise<void>;
  dismiss: () => void;
} {
  const [evt, setEvt] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(DISMISSED_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setEvt(e as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  return {
    canInstall: !!evt && !dismissed,
    async promptInstall() {
      if (!evt) return;
      try {
        await evt.prompt();
        await evt.userChoice;
      } finally {
        setEvt(null);
      }
    },
    dismiss() {
      setDismissed(true);
      try {
        localStorage.setItem(DISMISSED_KEY, "1");
      } catch {
        // ignore
      }
    },
  };
}
