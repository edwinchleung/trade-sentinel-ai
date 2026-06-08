"use client";

type Props = {
  page: number;
  pageCount: number;
  rangeStart: number;
  rangeEnd: number;
  total: number;
  onPageChange: (page: number) => void;
};

export function SmartMoneyPagination({
  page,
  pageCount,
  rangeStart,
  rangeEnd,
  total,
  onPageChange,
}: Props) {
  if (pageCount <= 1) return null;

  return (
    <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500">
      <button
        type="button"
        disabled={page === 0}
        onClick={() => onPageChange(Math.max(0, page - 1))}
        className="rounded border border-zinc-700 px-2 py-1 hover:border-zinc-500 disabled:opacity-40"
      >
        Previous
      </button>
      <span>
        Showing {rangeStart}–{rangeEnd} of {total}
        {" · "}
        Page {page + 1} of {pageCount}
      </span>
      <button
        type="button"
        disabled={page >= pageCount - 1}
        onClick={() => onPageChange(Math.min(pageCount - 1, page + 1))}
        className="rounded border border-zinc-700 px-2 py-1 hover:border-zinc-500 disabled:opacity-40"
      >
        Next
      </button>
    </div>
  );
}
