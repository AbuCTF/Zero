import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 3000,
		host: '0.0.0.0',
		proxy: {
			'/api': {
				target: process.env.API_URL || 'http://api:8000',
				changeOrigin: true
			},
			'/uploads': {
				target: process.env.API_URL || 'http://api:8000',
				changeOrigin: true
			}
		}
	}
});
