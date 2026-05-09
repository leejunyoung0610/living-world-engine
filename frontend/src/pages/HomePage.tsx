import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch, TOKEN_KEY } from "../api/client";
import { LoggedInNav } from "../components/LoggedInNav";

type Me = { email: string; username: string };

export function HomePage() {
  const nav = useNavigate();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      nav("/login");
      return;
    }
    (async () => {
      const res = await apiFetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      if (!res.ok) {
        setError("프로필을 불러오지 못했습니다.");
        return;
      }
      setMe((await res.json()) as Me);
    })();
  }, [nav]);

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    nav("/login");
  }

  if (error) {
    return <p className="px-4 py-8 text-red-400">{error}</p>;
  }
  if (!me) {
    return <p className="px-4 py-8 text-slate-400">불러오는 중…</p>;
  }

  return (
    <div className="page-shell">
      <LoggedInNav />
      <div className="page-container-narrow">
        <h1 className="text-2xl font-semibold text-white">Living World Engine</h1>
        <p className="mt-4 text-slate-300">
          안녕하세요, <strong>{me.username}</strong>님 ({me.email})
        </p>
        <p className="mt-2 text-sm text-slate-500">UGC MVP — 인증 + 월드 · 플레이</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            to="/my"
            className="inline-flex rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
          >
            마이페이지
          </Link>
          <button
            type="button"
            onClick={logout}
            className="inline-flex rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
          >
            로그아웃
          </button>
        </div>
      </div>
    </div>
  );
}
