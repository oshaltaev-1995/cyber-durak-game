import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    hookTimeout: 15_000,
    maxWorkers: 4,
    setupFiles: ['./vitest.setup.ts'],
    testTimeout: 10_000,
  },
});
