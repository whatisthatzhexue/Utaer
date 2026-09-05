import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        watch: {
            // 忽略 .vs 文件夹，彻底避免 VS 锁文件冲突
            ignored: ['**/.vs/**']
        }
    }
})