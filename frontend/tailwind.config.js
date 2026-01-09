/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	darkMode: 'class',
	theme: {
		extend: {
			colors: {
				// Using color function for opacity modifier support
				background: {
					DEFAULT: 'hsl(var(--background) / <alpha-value>)',
					secondary: 'hsl(var(--background-secondary) / <alpha-value>)',
					tertiary: 'hsl(var(--background-tertiary) / <alpha-value>)'
				},
				foreground: {
					DEFAULT: 'hsl(var(--foreground) / <alpha-value>)',
					muted: 'hsl(var(--foreground-muted) / <alpha-value>)'
				},
				border: {
					DEFAULT: 'hsl(var(--border) / <alpha-value>)',
					hover: 'hsl(var(--border-hover) / <alpha-value>)'
				},
				primary: {
					DEFAULT: 'hsl(var(--primary) / <alpha-value>)',
					foreground: 'hsl(var(--primary-foreground) / <alpha-value>)',
					hover: 'hsl(var(--primary-hover) / <alpha-value>)'
				},
				accent: {
					DEFAULT: 'hsl(var(--accent) / <alpha-value>)',
					foreground: 'hsl(var(--accent-foreground) / <alpha-value>)'
				},
				destructive: {
					DEFAULT: 'hsl(var(--destructive) / <alpha-value>)',
					foreground: 'hsl(var(--destructive-foreground) / <alpha-value>)'
				},
				success: {
					DEFAULT: 'hsl(var(--success) / <alpha-value>)',
					foreground: 'hsl(var(--success-foreground) / <alpha-value>)'
				},
				warning: {
					DEFAULT: 'hsl(var(--warning) / <alpha-value>)',
					foreground: 'hsl(var(--warning-foreground) / <alpha-value>)'
				},
				card: {
					DEFAULT: 'hsl(var(--card) / <alpha-value>)',
					foreground: 'hsl(var(--card-foreground) / <alpha-value>)'
				},
				input: {
					DEFAULT: 'hsl(var(--input) / <alpha-value>)',
					focus: 'hsl(var(--input-focus) / <alpha-value>)'
				},
				ring: 'hsl(var(--ring) / <alpha-value>)',
				muted: 'hsl(var(--foreground-muted) / <alpha-value>)'
			},
			fontFamily: {
				sans: [
					'Inter',
					'-apple-system',
					'BlinkMacSystemFont',
					'Segoe UI',
					'Roboto',
					'Helvetica Neue',
					'Arial',
					'sans-serif'
				],
				mono: ['JetBrains Mono', 'Fira Code', 'Monaco', 'Consolas', 'monospace']
			},
			fontSize: {
				xs: ['0.75rem', { lineHeight: '1rem' }],
				sm: ['0.875rem', { lineHeight: '1.25rem' }],
				base: ['1rem', { lineHeight: '1.5rem' }],
				lg: ['1.125rem', { lineHeight: '1.75rem' }],
				xl: ['1.25rem', { lineHeight: '1.75rem' }],
				'2xl': ['1.5rem', { lineHeight: '2rem' }],
				'3xl': ['1.875rem', { lineHeight: '2.25rem' }],
				'4xl': ['2.25rem', { lineHeight: '2.5rem' }]
			},
			borderRadius: {
				sm: '0.25rem',
				DEFAULT: '0.375rem',
				md: '0.5rem',
				lg: '0.75rem',
				xl: '1rem'
			},
			boxShadow: {
				sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
				DEFAULT: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
				md: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
				lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
				glow: '0 0 20px -5px hsl(var(--primary) / 0.3)'
			},
			animation: {
				'fade-in': 'fade-in 0.2s ease-out',
				'slide-in': 'slide-in 0.2s ease-out',
				'slide-up': 'slide-up 0.2s ease-out',
				spin: 'spin 1s linear infinite'
			},
			keyframes: {
				'fade-in': {
					'0%': { opacity: '0' },
					'100%': { opacity: '1' }
				},
				'slide-in': {
					'0%': { transform: 'translateX(-10px)', opacity: '0' },
					'100%': { transform: 'translateX(0)', opacity: '1' }
				},
				'slide-up': {
					'0%': { transform: 'translateY(10px)', opacity: '0' },
					'100%': { transform: 'translateY(0)', opacity: '1' }
				}
			}
		}
	},
	plugins: []
};
