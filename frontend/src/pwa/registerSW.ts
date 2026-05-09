/**
 * 서비스 워커 등록 — `vite-plugin-pwa`(autoUpdate 모드).
 * 새 빌드가 활성화되면 한 번 새로고침해 최신을 적용.
 */
import { registerSW } from "virtual:pwa-register";

export function setupPwa(): void {
  if (typeof window === "undefined") return;
  // autoUpdate 모드: 새 SW 활성화 후 별도 prompt 없이 다음 네비게이션에서 적용됨.
  // 여기서는 콘솔에 신호만 남긴다 (향후 토스트로 교체 가능).
  registerSW({
    immediate: true,
    onRegisteredSW(swUrl) {
      // dev 빌드는 SW가 비활성. prod에서만 swUrl 존재.
      if (swUrl) {
        // eslint-disable-next-line no-console
        console.info("[PWA] SW registered:", swUrl);
      }
    },
    onRegisterError(err) {
      // eslint-disable-next-line no-console
      console.warn("[PWA] SW register error:", err);
    },
  });
}
