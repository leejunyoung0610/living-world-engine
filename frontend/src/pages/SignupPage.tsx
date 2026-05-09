import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../api/client";
import { KakaoLoginButton } from "../components/KakaoLoginButton";

export function SignupPage() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await apiFetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          username,
          password,
          invite_code: inviteCode,
        }),
      });
      const data = (await res.json()) as { detail?: string | { msg: string }[] };
      if (!res.ok) {
        const d = data.detail;
        if (typeof d === "string") setError(d);
        else if (Array.isArray(d)) setError(d.map((x) => x.msg).join(", "));
        else setError("가입 실패");
        return;
      }
      nav("/login");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-12 sm:py-16">
      <h1 className="mb-2 text-2xl font-semibold text-white">회원가입</h1>
      <p className="mb-6 text-sm text-slate-400">
        서버에서 초대 코드 검증을 켠 경우에만 코드가 필수입니다. (로컬 기본은 꺼져 있을 수 있음)
      </p>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <input
          type="email"
          required
          placeholder="이메일"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white placeholder:text-slate-500"
        />
        <input
          type="text"
          required
          placeholder="사용자 이름"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white placeholder:text-slate-500"
        />
        <input
          type="password"
          required
          minLength={8}
          placeholder="비밀번호 (8자 이상)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white placeholder:text-slate-500"
        />
        <input
          type="text"
          placeholder="초대 코드 (베타 시 서버 설정에 따라 필수)"
          value={inviteCode}
          onChange={(e) => setInviteCode(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white placeholder:text-slate-500"
        />
        {error && <p className="text-sm text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-indigo-600 py-2 font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading ? "…" : "가입"}
        </button>
      </form>

      <div className="my-6 flex items-center gap-3">
        <span className="h-px flex-1 bg-slate-800" />
        <span className="text-xs text-slate-500">또는</span>
        <span className="h-px flex-1 bg-slate-800" />
      </div>
      <KakaoLoginButton />

      <p className="mt-4 text-sm text-slate-400">
        이미 계정이 있으면 <Link to="/login" className="text-indigo-400 underline">로그인</Link>
      </p>
    </div>
  );
}
