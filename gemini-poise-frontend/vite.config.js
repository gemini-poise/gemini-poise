import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path';

export default defineConfig(({command, mode}) => {
    // eslint-disable-next-line no-undef
    const env = loadEnv(mode, process.cwd(), 'ALTEREM_');
    const port = parseInt(env.ALTEREM_PORT || '3000', 10);

    if (command === 'build') {
        console.log('Building the application...');
    }

    return {
        envPrefix: "ALTEREM_",
        plugins: [react(), tailwindcss()],
        resolve: {
            alias: {
                // eslint-disable-next-line no-undef
                '@': path.resolve(__dirname, 'src'),
            },
        },
        server: {
            host: true,
            port: port,
            hmr: {
                overlay: true,
            },
            proxy: {
                '/api': {
                    target: 'http://127.0.0.1:8000',
                    changeOrigin: true,
                    // rewrite: (path) => path.replace(/^\/api/, '') // 如果后端没有 /api 前缀，需要重写路径
                },
            },
        }

    };
});
