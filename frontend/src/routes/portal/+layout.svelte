<script lang="ts">
	import type { Snippet } from 'svelte';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { api, type Participant } from '$lib/api';

	interface Props {
		children: Snippet;
	}
	let { children }: Props = $props();

	let participant = $state<Participant | null>(null);
	let loading = $state(true);
	let sidebarOpen = $state(false);

	const currentPath = $derived($page.url.pathname);
	const initial = $derived((participant?.name || participant?.email || '?').charAt(0).toUpperCase());

	onMount(checkAuth);

	async function checkAuth() {
		try {
			participant = await api.participant.me();
		} catch {
			goto('/portal/login');
		} finally {
			loading = false;
		}
	}

	async function handleLogout() {
		try {
			await api.participant.logout();
		} catch {
			/* ignore */
		}
		goto('/');
	}

	const navItems = [
		{ href: '/portal', label: 'Dashboard', icon: 'home' },
		{ href: '/portal/profile', label: 'Profile', icon: 'user' },
		{ href: '/portal/prizes', label: 'Prizes', icon: 'gift' },
		{ href: '/portal/certificates', label: 'Certificates', icon: 'document' }
	];

	function isActive(href: string): boolean {
		return href === '/portal' ? currentPath === '/portal' : currentPath.startsWith(href);
	}
</script>

{#snippet icon(name: string)}
	{#if name === 'home'}
		<svg class="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.7"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
	{:else if name === 'user'}
		<svg class="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.7"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
	{:else if name === 'gift'}
		<svg class="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.7"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" /></svg>
	{:else if name === 'document'}
		<svg class="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.7"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
	{/if}
{/snippet}

{#snippet sidebarInner()}
	<div class="flex h-full flex-col">
		<div class="flex items-center justify-between border-b border-white/[0.06] px-5 py-[17px]">
			<a href="/" class="block"><img src="/logo.png" alt="ZeroPool" class="h-7 w-auto" /></a>
			<button class="btn-ghost btn-sm !px-1.5 lg:hidden" onclick={() => (sidebarOpen = false)} aria-label="Close menu">
				<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
			</button>
		</div>
		<div class="eyebrow px-5 pb-2 pt-5">Menu</div>
		<nav class="flex-1 px-3 pb-4">
			<ul class="space-y-1">
				{#each navItems as item}
					{@const active = isActive(item.href)}
					<li>
						<a
							href={item.href}
							onclick={() => (sidebarOpen = false)}
							class="relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-150 {active
								? 'bg-brass/[0.08] text-brass'
								: 'text-foreground-muted hover:bg-white/[0.03] hover:text-foreground'}"
						>
							{#if active}
								<span class="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-brass"></span>
							{/if}
							{@render icon(item.icon)}
							<span class="font-medium">{item.label}</span>
						</a>
					</li>
				{/each}
			</ul>
		</nav>
		{#if participant}
			<div class="border-t border-white/[0.06] p-3">
				<div class="flex items-center gap-3 rounded-lg px-2 py-2">
					<div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brass/10 text-sm font-semibold text-brass ring-1 ring-inset ring-brass/20">
						{initial}
					</div>
					<div class="min-w-0 flex-1">
						<div class="truncate text-sm font-medium text-foreground">
							{participant.name || participant.username || 'Participant'}
						</div>
						<div class="truncate text-xs text-foreground-muted">{participant.email}</div>
					</div>
				</div>
				<button
					onclick={handleLogout}
					class="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-foreground-muted transition-all duration-150 hover:bg-white/[0.03] hover:text-foreground"
				>
					<svg class="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.7"><path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
					<span class="font-medium">Sign out</span>
				</button>
			</div>
		{/if}
	</div>
{/snippet}

{#if loading}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<div class="flex items-center gap-2.5 text-sm text-foreground-muted">
			<span class="h-4 w-4 animate-spin rounded-full border-2 border-brass/30 border-t-brass"></span>
			<span class="text-mono">Loading…</span>
		</div>
	</div>
{:else}
	<div class="min-h-screen bg-background">
		<!-- Mobile top bar -->
		<header class="sticky top-0 z-30 flex items-center justify-between border-b border-white/[0.06] bg-card/80 px-4 py-3 backdrop-blur-xl lg:hidden">
			<button class="btn-ghost btn-sm !px-1.5" onclick={() => (sidebarOpen = true)} aria-label="Open menu">
				<svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" /></svg>
			</button>
			<img src="/logo.png" alt="ZeroPool" class="h-6 w-auto" />
			<div class="flex h-7 w-7 items-center justify-center rounded-lg bg-brass/10 text-xs font-semibold text-brass ring-1 ring-inset ring-brass/20">{initial}</div>
		</header>

		<!-- Desktop sidebar -->
		<aside class="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-white/[0.06] bg-card lg:flex">
			{@render sidebarInner()}
		</aside>

		<!-- Mobile drawer -->
		{#if sidebarOpen}
			<button class="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden" onclick={() => (sidebarOpen = false)} aria-label="Close menu"></button>
			<aside class="fade-in fixed inset-y-0 left-0 z-50 w-64 border-r border-white/[0.06] bg-card lg:hidden">
				{@render sidebarInner()}
			</aside>
		{/if}

		<!-- Main content -->
		<main class="lg:pl-64">
			<div class="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
				{@render children()}
			</div>
		</main>
	</div>
{/if}
