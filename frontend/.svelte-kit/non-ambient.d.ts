
// this file is generated — do not edit it


declare module "svelte/elements" {
	export interface HTMLAttributes<T> {
		'data-sveltekit-keepfocus'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-noscroll'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-preload-code'?:
			| true
			| ''
			| 'eager'
			| 'viewport'
			| 'hover'
			| 'tap'
			| 'off'
			| undefined
			| null;
		'data-sveltekit-preload-data'?: true | '' | 'hover' | 'tap' | 'off' | undefined | null;
		'data-sveltekit-reload'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-replacestate'?: true | '' | 'off' | undefined | null;
	}
}

export {};


declare module "$app/types" {
	export interface AppTypes {
		RouteId(): "/" | "/admin" | "/admin/campaigns" | "/admin/certificates" | "/admin/events" | "/admin/events/new" | "/admin/events/[id]" | "/admin/providers" | "/admin/templates" | "/events" | "/events/[slug]" | "/login" | "/portal" | "/portal/certificates" | "/portal/login" | "/portal/prizes" | "/portal/verify" | "/verify";
		RouteParams(): {
			"/admin/events/[id]": { id: string };
			"/events/[slug]": { slug: string }
		};
		LayoutParams(): {
			"/": { id?: string; slug?: string };
			"/admin": { id?: string };
			"/admin/campaigns": Record<string, never>;
			"/admin/certificates": Record<string, never>;
			"/admin/events": { id?: string };
			"/admin/events/new": Record<string, never>;
			"/admin/events/[id]": { id: string };
			"/admin/providers": Record<string, never>;
			"/admin/templates": Record<string, never>;
			"/events": { slug?: string };
			"/events/[slug]": { slug: string };
			"/login": Record<string, never>;
			"/portal": Record<string, never>;
			"/portal/certificates": Record<string, never>;
			"/portal/login": Record<string, never>;
			"/portal/prizes": Record<string, never>;
			"/portal/verify": Record<string, never>;
			"/verify": Record<string, never>
		};
		Pathname(): "/" | "/admin" | "/admin/" | "/admin/campaigns" | "/admin/campaigns/" | "/admin/certificates" | "/admin/certificates/" | "/admin/events" | "/admin/events/" | "/admin/events/new" | "/admin/events/new/" | `/admin/events/${string}` & {} | `/admin/events/${string}/` & {} | "/admin/providers" | "/admin/providers/" | "/admin/templates" | "/admin/templates/" | "/events" | "/events/" | `/events/${string}` & {} | `/events/${string}/` & {} | "/login" | "/login/" | "/portal" | "/portal/" | "/portal/certificates" | "/portal/certificates/" | "/portal/login" | "/portal/login/" | "/portal/prizes" | "/portal/prizes/" | "/portal/verify" | "/portal/verify/" | "/verify" | "/verify/";
		ResolvedPathname(): `${"" | `/${string}`}${ReturnType<AppTypes['Pathname']>}`;
		Asset(): "/favicon.svg" | "/logo.png" | string & {};
	}
}