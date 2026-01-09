// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		interface Error {
			message: string;
			code?: string;
		}
		interface Locals {
			user: {
				id: string;
				email: string;
				username: string;
				name: string | null;
				role: 'admin' | 'organizer' | 'viewer';
			} | null;
		}
		interface PageData {
			user?: App.Locals['user'];
		}
		interface PageState {}
		interface Platform {}
	}
}

export {};
