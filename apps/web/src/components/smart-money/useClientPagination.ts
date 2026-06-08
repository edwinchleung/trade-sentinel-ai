"use client";

import { useEffect, useMemo, useState } from "react";

export const DEFAULT_PAGE_SIZE = 25;

type Options = {
  pageSize?: number;
  resetKey?: string;
};

export function useClientPagination<T>(rows: T[], options: Options = {}) {
  const pageSize = options.pageSize ?? DEFAULT_PAGE_SIZE;
  const resetKey = options.resetKey ?? "";
  const [page, setPage] = useState(0);

  useEffect(() => {
    setPage(0);
  }, [resetKey]);

  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const effectivePage = Math.min(page, Math.max(0, pageCount - 1));

  const pageRows = useMemo(
    () => rows.slice(effectivePage * pageSize, effectivePage * pageSize + pageSize),
    [rows, effectivePage, pageSize]
  );

  const rangeStart = rows.length === 0 ? 0 : effectivePage * pageSize + 1;
  const rangeEnd = Math.min((effectivePage + 1) * pageSize, rows.length);

  return {
    page: effectivePage,
    setPage,
    pageCount,
    pageRows,
    pageSize,
    rangeStart,
    rangeEnd,
    total: rows.length,
  };
}
