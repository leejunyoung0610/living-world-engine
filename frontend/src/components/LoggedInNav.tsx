import { NavLink, useLocation } from "react-router-dom";

function navClass(active: boolean) {
  return active ? "text-white" : "text-slate-400 transition hover:text-white";
}

export function LoggedInNav() {
  const { pathname } = useLocation();
  const mySection =
    pathname === "/my" || pathname.startsWith("/worlds") || /^\/play\/[^/]+/.test(pathname);

  return (
    <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-sm">
      <nav className="mx-auto flex max-w-4xl items-center gap-6 px-4 py-3 text-sm font-medium">
        <NavLink to="/" end className={({ isActive }) => navClass(isActive)}>
          홈
        </NavLink>
        <NavLink to="/explore" className={({ isActive }) => navClass(isActive)}>
          탐색
        </NavLink>
        <NavLink to="/my" className={() => navClass(mySection)}>
          마이페이지
        </NavLink>
      </nav>
    </header>
  );
}
