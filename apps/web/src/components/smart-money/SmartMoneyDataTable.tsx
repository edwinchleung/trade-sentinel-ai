"use client";

import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  sticky?: boolean;
};

export function SmartMoneyDataTable({ children, sticky = false }: Props) {
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-800">
      <table className={`w-full text-sm ${sticky ? "[&_thead]:sticky [&_thead]:top-0 [&_thead]:z-10" : ""}`}>
        {children}
      </table>
    </div>
  );
}

export function SmartMoneyTableHead({ children }: { children: ReactNode }) {
  return (
    <thead className="bg-zinc-900/80 text-zinc-500 text-left">{children}</thead>
  );
}

export function SmartMoneyTableBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>;
}
