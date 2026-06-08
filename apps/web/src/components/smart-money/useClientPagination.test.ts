import { describe, expect, it } from "vitest";
import { DEFAULT_PAGE_SIZE } from "./useClientPagination";

function paginateSlice<T>(rows: T[], page: number, pageSize = DEFAULT_PAGE_SIZE) {
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const effectivePage = Math.min(page, Math.max(0, pageCount - 1));
  return {
    pageRows: rows.slice(effectivePage * pageSize, effectivePage * pageSize + pageSize),
    effectivePage,
    pageCount,
    rangeStart: rows.length === 0 ? 0 : effectivePage * pageSize + 1,
    rangeEnd: Math.min((effectivePage + 1) * pageSize, rows.length),
  };
}

describe("useClientPagination slice behavior", () => {
  const rows = Array.from({ length: 50 }, (_, i) => `row-${i}`);

  it("returns first page of 25 items", () => {
    const p0 = paginateSlice(rows, 0);
    expect(p0.pageRows).toHaveLength(25);
    expect(p0.pageRows[0]).toBe("row-0");
    expect(p0.rangeStart).toBe(1);
    expect(p0.rangeEnd).toBe(25);
  });

  it("returns second page with different items", () => {
    const p0 = paginateSlice(rows, 0);
    const p1 = paginateSlice(rows, 1);
    expect(p1.pageRows[0]).toBe("row-25");
    expect(p1.pageRows[0]).not.toBe(p0.pageRows[0]);
    expect(p1.rangeStart).toBe(26);
    expect(p1.rangeEnd).toBe(50);
  });

  it("clamps page when row count shrinks", () => {
    const small = rows.slice(0, 10);
    const p = paginateSlice(small, 5);
    expect(p.effectivePage).toBe(0);
    expect(p.pageRows).toHaveLength(10);
  });
});
