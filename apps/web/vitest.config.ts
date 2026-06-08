import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    environment: "node",
    include: [
      "src/lib/insiderFeedFilters.test.ts",
      "src/components/InsiderFeedDateRange.test.ts",
      "src/components/smart-money/buildFeedPageEntries.test.ts",
      "src/components/smart-money/useClientPagination.test.ts",
    ],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
