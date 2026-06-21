import { defineConfig, type Plugin } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import { transformWithEsbuild } from 'vite'

// Vitest/esbuild skips .d.ts files by default; this plugin re-enables them as
// runtime modules so constants defined in src/types/*.d.ts are importable in tests.
const dtsAsTs: Plugin = {
  name: 'dts-as-ts',
  enforce: 'pre',
  async transform(code: string, id: string) {
    if (!id.endsWith('.d.ts')) return null
    return transformWithEsbuild(code, id.replace('.d.ts', '.ts'), { loader: 'ts' })
  },
}

export default defineConfig({
  plugins: [dtsAsTs, react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    passWithNoTests: true,
    env: {
      NEXT_PUBLIC_API_BASE_URL: 'http://localhost:8000',
    },
    coverage: {
      provider: 'v8',
      include: ['src/**'],
      exclude: [
        'src/types/**',
        'src/app/**',
        'src/styles/**',
        'src/stories/**',
        'src/__tests__/**',
        // App chrome/shell — no business logic; require Next.js routing mocks to test
        'src/components/layout/**',
        // Root barrel — re-exports only; actual components tested via sub-directory barrels
        'src/components/index.ts',
      ],
      thresholds: {
        branches: 80,
        functions: 80,
        lines: 80,
        statements: 80,
      },
    },
  },
  resolve: {
    alias: { '@': resolve(__dirname, './src') },
    extensions: ['.d.ts', '.mjs', '.js', '.mts', '.ts', '.jsx', '.tsx', '.json'],
  },
})
