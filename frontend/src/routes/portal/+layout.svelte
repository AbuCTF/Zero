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
		<svg class="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
	{:else if name === 'user'}
		<svg class="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
	{:else if name === 'gift'}
		<svg class="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" /></svg>
	{:else if name === 'document'}
		<svg class="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
	{/if}
{/snippet}

{#snippet sidebarInner()}
	<div class="flex h-full flex-col">
		<div class="flex items-center justify-between border-b border-border px-5 py-[18px]">
			<a href="/" class="block"><img src="/logo.png" alt="ZeroPool" class="h-7 w-auto" /></a>
			<button
				class="btn-ghost btn-sm !px-1.5 lg:hidden"
				onclick={() => (sidebarOpen = false)}
				aria-label="Close menu"
			>
				<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
			</button>
		</div>
		<div class="px-5 pb-2 pt-4 text-label">Participant Portal</div>
		<nav class="flex-1 px-3 pb-4">
			<ul class="space-y-0.5">
				{#each navItems as item}
					<li>
						<a
							href={item.href}
							onclick={() => (sidebarOpen = false)}
							class="sidebar-link {isActive(item.href) ? 'active' : ''}"
						>
							{@render icon(item.icon)}
							{item.label}
						</a>
					</li>
				{/each}
			</ul>
		</nav>
		{#if participant}
			<div class="border-t border-border p-3">
				<div class="flex items-center gap-3 px-2 py-1.5">
					<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-medium text-foreground">
						{initial}
					</div>
					<div class="min-w-0 flex-1">
						<div class="truncate text-sm font-medium text-foreground">
							{participant.name || participant.username || 'Participant'}
						</div>
						<div class="truncate text-xs text-foreground-muted">{participant.email}</div>
					</div>
				</div>
				<button onclick={handleLogout} class="sidebar-link mt-1 w-full">
					<svg class="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
					Sign out
				</button>
			</div>
		{/if}
	</div>
{/snippet}

{#if loading}
	<div class="flex min-h-screen items-center justify-center bg-background">
		<div class="text-mono animate-pulse text-sm text-foreground-muted">Loading…</div>
	</div>
{:else}
	<div class="min-h-screen bg-background">
		<!-- Mobile top bar -->
		<header class="sticky top-0 z-30 flex items-center justify-between border-b border-border bg-card px-4 py-3 lg:hidden">
			<button class="btn-ghost btn-sm !px-1.5" onclick={() => (sidebarOpen = true)} aria-label="Open menu">
				<svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" /></svg>
			</button>
			<img src="/logo.png" alt="ZeroPool" class="h-6 w-auto" />
			<div class="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-xs font-medium">{initial}</div>
		</header>

		<!-- Desktop sidebar -->
		<aside class="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-border bg-card lg:flex">
			{@render sidebarInner()}
		</aside>

		<!-- Mobile drawer -->
		{#if sidebarOpen}
			<button
				class="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
				onclick={() => (sidebarOpen = false)}
				aria-label="Close menu"
			></button>
			<aside class="fade-in fixed inset-y-0 left-0 z-50 w-64 border-r border-border bg-card lg:hidden">
				{@render sidebarInner()}
			</aside>
		{/if}

		<!-- Main content -->
		<main class="lg:pl-64">
			<div class="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
				{@render children()}
			</div>
		</main>
	</div>
{/if}
