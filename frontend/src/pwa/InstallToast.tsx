import { usePwaInstall } from "./usePwaInstall";

/** 화면 우하단 가벼운 설치 토스트 — `beforeinstallprompt`가 와야만 노출됨 */
export function InstallToast() {
  const { canInstall, promptInstall, dismiss } = usePwaInstall();
  if (!canInstall) return null;

  return (
    <div
      role="dialog"
      aria-label="앱 설치"
      className="fixed inset-x-3 bottom-3 z-40 flex flex-wrap items-center gap-3 rounded-xl border border-slate-700 bg-slate-900/95 p-3 shadow-lg backdrop-blur-sm sm:inset-x-auto sm:right-6 sm:bottom-6 sm:max-w-sm"
    >
      <p className="flex-1 text-sm text-slate-200">
        Living World를 홈 화면에 설치하시겠어요?
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => void promptInstall()}
          className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500"
        >
          설치
        </button>
        <button
          type="button"
          onClick={dismiss}
          className="rounded-md border border-slate-600 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
        >
          나중에
        </button>
      </div>
    </div>
  );
}
