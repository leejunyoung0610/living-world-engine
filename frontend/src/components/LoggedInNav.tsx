import { Link } from "react-router-dom";

export function LoggedInNav() {
  return (
    <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-sm">
      <nav className="mx-auto flex max-w-4xl items-center gap-6 px-4 py-3 text-sm font-medium">
        <Link to="/" className="text-slate-400 transition hover:text-white">
          홈
        </Link>
        <Link to="/worlds" className="text-slate-400 transition hover:text-white">
          내 월드
        </Link>
      </nav>
    </header>
  );
}
