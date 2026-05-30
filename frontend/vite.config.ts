import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'
import { transformWithEsbuild } from 'vite'

// Vitest/esbuild skips .d.ts files by default; this plugin re-enables them as
// runtime modules so constants defined in src/types/*.d.ts are importable.
// Scoped to src/types/ only — transforming third-party .d.ts files (e.g. Ladle's
// internal app.d.ts) strips their `declare` statements and produces broken output.
const dtsAsTs: Plugin = {
  name: 'dts-as-ts',
  enforce: 'pre',
  async transform(code: string, id: string) {
    if (!id.endsWith('.d.ts')) return null
    if (!id.includes('/src/types/') && !id.includes('\\src\\types\\')) return null
    return transformWithEsbuild(code, id.replace('.d.ts', '.ts'), { loader: 'ts' })
  },
}

export default defineConfig({
  plugins: [dtsAsTs, tailwindcss(), react()],
  resolve: {
    alias: { '@': resolve(__dirname, './src') },
    extensions: ['.mjs', '.js', '.mts', '.ts', '.jsx', '.tsx', '.json', '.d.ts'],
  },
})
