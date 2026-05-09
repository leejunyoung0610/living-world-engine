import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";

/**
 * 카카오 OAuth 콜백 — 백엔드가 ``#access_token=...`` 해시로 토큰을 실어 보낸다.
 * 토큰을 localStorage 에 저장 후 / 로 이동, 실패 시 /login 으로.
 */
export function OAuthCallbackPage() {
  const nav = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const hash = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(hash);
    const token = params.get("access_token");
    const err = params.get("error");
    if (err) {
      setError(decodeURIComponent(err));
      const t = setTimeout(() => nav("/login", { replace: true }), 1500);
      return () => clearTimeout(t);
    }
    if (!token) {
      setError("missing_token");
      const t = setTimeout(() => nav("/login", { replace: true }), 1500);
      return () => clearTimeout(t);
    }
    localStorage.setItem(TOKEN_KEY, token);
    history.replaceState(null, "", "/");
    nav("/", { replace: true });
  }, [nav]);

  return (
    <div className="page-shell">
      <div className="page-container-narrow py-16 text-center">
        {error ? (
          <p className="text-sm text-red-300">로그인 실패: {error} — 잠시 후 로그인 페이지로 이동합니다.</p>
        ) : (
          <p className="text-sm text-slate-400">로그인 완료 처리 중…</p>
        )}
      </div>
    </div>
  );
}
