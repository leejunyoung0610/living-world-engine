import { apiFetch, apiUrl } from "./client";

export interface MeResponse {
  email: string;
  username: string;
  auth_provider: "local" | "kakao";
  has_password: boolean;
  kakao_linked: boolean;
}

export const SESSION_EXPIRED = "SESSION_EXPIRED";

export async function fetchMe(token: string): Promise<MeResponse> {
  const res = await apiFetch("/api/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401) throw new Error(SESSION_EXPIRED);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as MeResponse;
}

/** 브라우저를 카카오 인가 페이지로 보낸다. 백엔드가 302 로 리다이렉트. */
export function startKakaoLogin(): void {
  window.location.href = apiUrl("/api/auth/kakao/authorize");
}
