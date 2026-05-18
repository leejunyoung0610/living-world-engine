import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";

const LINKS: { to: string; label: string; end?: boolean }[] = [
  { to: "/", label: "홈", end: true },
  { to: "/my", label: "마이페이지" },
];

function navClass(active: boolean) {
  return active ? "text-white" : "text-slate-400 transition hover:text-white";
}

export function LoggedInNav() {
  const { pathname } = useLocation();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);

  const mySection =
    pathname === "/my" ||
    pathname.startsWith("/worlds") ||
    /^\/play(\/|$)/.test(pathname);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  function isActive(to: string, end?: boolean): boolean {
    if (to === "/my") return mySection;
    if (end) return pathname === to;
    return pathname === to || pathname.startsWith(`${to}/`);
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    nav("/login");
  }

  return (
    <header className="sticky top-0 z-30 shrink-0 border-b border-slate-800/80 bg-slate-900/70 backdrop-blur-sm">
      <nav className="mx-auto flex max-w-4xl items-center justify-between gap-4 px-4 py-3 text-sm font-medium">
        <NavLink to="/" end className="text-white">
          <span className="font-semibold">Living World</span>
        </NavLink>

        <div className="hidden items-center gap-6 sm:flex">
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={() => navClass(isActive(l.to, l.end))}
            >
              {l.label}
            </NavLink>
          ))}
          <button
            type="button"
            onClick={logout}
            className="rounded-md border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-800"
          >
            로그아웃
          </button>
        </div>

        <button
          type="button"
          aria-label="메뉴"
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen((v) => !v)}
          className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-700 text-slate-300 hover:bg-slate-800 sm:hidden"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            {open ? (
              <>
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </>
            ) : (
              <>
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </>
            )}
          </svg>
        </button>
      </nav>

      {open && (
        <div id="mobile-nav" className="border-t border-slate-800 bg-slate-950/95 sm:hidden">
          <ul className="mx-auto flex max-w-4xl flex-col gap-1 px-2 py-2 text-sm font-medium">
            {LINKS.map((l) => (
              <li key={l.to}>
                <NavLink
                  to={l.to}
                  end={l.end}
                  className={() =>
                    `block rounded-md px-3 py-2 ${
                      isActive(l.to, l.end)
                        ? "bg-slate-800 text-white"
                        : "text-slate-300 hover:bg-slate-800"
                    }`
                  }
                >
                  {l.label}
                </NavLink>
              </li>
            ))}
            <li>
              <button
                type="button"
                onClick={logout}
                className="w-full rounded-md px-3 py-2 text-left text-slate-300 hover:bg-slate-800"
              >
                로그아웃
              </button>
            </li>
          </ul>
        </div>
      )}
    </header>
  );
}
