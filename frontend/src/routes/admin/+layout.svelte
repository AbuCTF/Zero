<script lang="ts">
	import { auth, ApiError } from '$lib/api';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	let { children } = $props();

	let user = $state<App.Locals['user'] | null>(null);
	let loading = $state(true);
	let sidebarOpen = $state(false);

	onMount(async () => {
		try {
			const response = await auth.me();
			user = response.user;
			// If no user (e.g., authenticated as participant only), redirect
			if (!user) {
				goto('/login');
			}
		} catch (err) {
			if (err instanceof ApiError && err.status === 401) {
				goto('/login');
			}
		} finally {
			loading = false;
		}
	});

	async function logout() {
		try {
			await auth.logout();
			goto('/login');
		} catch {
			goto('/login');
		}
	}

	const navItems = [
		{ href: '/admin', label: 'Dashboard', icon: 'home' },
		{ href: '/admin/events', label: 'Events', icon: 'calendar' },
		{ href: '/admin/providers', label: 'Email Providers', icon: 'mail' },
		{ href: '/admin/templates', label: 'Templates', icon: 'file-text' },
		{ href: '/admin/campaigns', label: 'Campaigns', icon: 'send' },
		{ href: '/admin/certificates', label: 'Certificates', icon: 'award' }
	];

	function isActive(href: string): boolean {
		if (href === '/admin') {
			return $page.url.pathname === '/admin';
		}
		return $page.url.pathname.startsWith(href);
	}
</script>

<svelte:head>
	<title>Admin - ZeroPool</title>
</svelte:head>

{#if loading}
	<div class="min-h-screen bg-background flex items-center justify-center">
		<svg class="animate-spin h-8 w-8 text-foreground-muted" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
			<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
			<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
		</svg>
	</div>
{:else if !user}
	<div class="min-h-screen bg-background flex items-center justify-center">
		<p class="text-foreground-muted">Redirecting to login...</p>
	</div>
{:else}
	<div class="min-h-screen bg-background flex">
		<!-- Sidebar -->
		<aside class="hidden lg:flex lg:flex-col w-56 border-r border-border bg-background">
			<!-- Logo -->
			<div class="p-4 border-b border-border">
				<a href="/admin" class="flex items-center gap-2 text-foreground">
					<div class="w-8 h-8 rounded-xl bg-foreground flex items-center justify-center">
						<svg class="w-4 h-4 text-background" viewBox="0 0 24 24" fill="none">
							<path d="M12 2L2 7l10 5 10-5-10-5z" fill="currentColor" opacity="0.3"/>
							<path d="M2 17l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
							<path d="M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
						</svg>
					</div>
					<span class="text-sm font-semibold tracking-tight">ZeroPool</span>
				</a>
			</div>

			<!-- Navigation -->
			<nav class="flex-1 p-2 space-y-0.5">
				{#each navItems as item}
					<a
						href={item.href}
						class="sidebar-link {isActive(item.href) ? 'active' : ''}"
					>
						{#if item.icon === 'home'}
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>
							</svg>
						{:else if item.icon === 'calendar'}
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
							</svg>
						{:else if item.icon === 'mail'}
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
							</svg>
						{:else if item.icon === 'file-text'}
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
							</svg>
						{:else if item.icon === 'send'}
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
							</svg>
						{:else if item.icon === 'award'}
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"></path>
							</svg>
						{/if}
						<span class="text-[13px]">{item.label}</span>
					</a>
				{/each}
			</nav>

			<!-- User -->
			<div class="p-3 border-t border-border">
				<div class="flex items-center gap-2">
					<div class="w-7 h-7 rounded bg-accent flex items-center justify-center text-xs font-medium text-foreground text-mono">
						{user.username.charAt(0).toUpperCase()}
					</div>
					<div class="flex-1 min-w-0">
						<p class="text-xs font-medium text-foreground truncate">{user.username}</p>
					</div>
					<button
						onclick={logout}
						class="p-1 text-foreground-muted hover:text-foreground rounded hover:bg-accent transition-colors"
						title="Logout"
					>
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
						</svg>
					</button>
				</div>
			</div>
		</aside>

		<!-- Mobile header -->
		<div class="lg:hidden fixed top-0 left-0 right-0 z-50 bg-background border-b border-border">
			<div class="flex items-center justify-between p-4">
				<button
					onclick={() => sidebarOpen = !sidebarOpen}
					class="p-2 -ml-2 text-foreground-muted hover:text-foreground"
				>
					<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
					</svg>
				</button>
				<span class="font-semibold text-foreground">ZeroPool</span>
				<button onclick={logout} class="p-2 -mr-2 text-foreground-muted hover:text-foreground">
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
					</svg>
				</button>
			</div>
		</div>

		<!-- Mobile sidebar overlay -->
		{#if sidebarOpen}
			<div class="lg:hidden fixed inset-0 z-40">
				<div class="absolute inset-0 bg-black/50" onclick={() => sidebarOpen = false}></div>
				<aside class="absolute left-0 top-0 bottom-0 w-64 bg-background-secondary border-r border-border">
					<div class="p-4 border-b border-border">
						<span class="text-xl font-semibold text-foreground">ZeroPool</span>
					</div>
					<nav class="p-4 space-y-1">
						{#each navItems as item}
							<a
								href={item.href}
								class="sidebar-link {isActive(item.href) ? 'active' : ''}"
								onclick={() => sidebarOpen = false}
							>
								{item.label}
							</a>
						{/each}
					</nav>
				</aside>
			</div>
		{/if}

		<!-- Main content -->
		<main class="flex-1 lg:pt-0 pt-16 overflow-auto">
			{@render children()}
		</main>
	</div>
{/if}
