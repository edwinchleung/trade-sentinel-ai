import Link from "next/link";
import { NavLiveIndicator } from "@/components/NavLiveIndicator";

const links = [
  { href: "/", label: "Home" },
  { href: "/context", label: "Context" },
  { href: "/smart-money", label: "Smart Money" },
  { href: "/digest", label: "Digest" },
  { href: "/screener", label: "Screener" },
  { href: "/risk", label: "Risk Check" },
  { href: "/briefing", label: "Briefing" },
  { href: "/journal", label: "Journal" },
  { href: "/watchlist", label: "Watchlist" },
];

export function Nav() {
  return (
    <nav className="border-b border-zinc-800 bg-zinc-950/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
        <Link href="/" className="font-semibold tracking-tight text-emerald-400">
          TradeSentinel AI
        </Link>
        <div className="flex flex-wrap gap-4 text-sm text-zinc-400">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="hover:text-zinc-100 transition-colors"
            >
              {l.label}
            </Link>
          ))}
        </div>
        <NavLiveIndicator />
      </div>
    </nav>
  );
}
