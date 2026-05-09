import { startKakaoLogin } from "../api/auth";

/** 카카오 디자인 가이드의 노란색 + 검정 텍스트. */
export function KakaoLoginButton({ label = "카카오로 시작하기" }: { label?: string }) {
  return (
    <button
      type="button"
      onClick={startKakaoLogin}
      className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#FEE500] px-4 py-2.5 text-sm font-semibold text-[#191919] transition hover:brightness-95 active:brightness-90"
    >
      <KakaoMark />
      <span>{label}</span>
    </button>
  );
}

function KakaoMark() {
  return (
    <svg
      aria-hidden="true"
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
    >
      <path
        d="M9 2.25C5.27 2.25 2.25 4.66 2.25 7.63c0 1.92 1.27 3.6 3.18 4.55l-.65 2.4c-.05.2.16.36.34.25l2.86-1.9c.34.04.7.06 1.02.06 3.73 0 6.75-2.41 6.75-5.36S12.73 2.25 9 2.25z"
        fill="#191919"
      />
    </svg>
  );
}
