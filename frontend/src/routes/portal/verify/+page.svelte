<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	let loading = $state(true);
	let error = $state('');
	let success = $state(false);

	const token = $derived($page.url.searchParams.get('token'));

	onMount(async () => {
		if (!token) {
			error = 'No access token provided.';
			loading = false;
			return;
		}
		try {
			const response = await fetch(`/api/participants/verify-magic-link?token=${encodeURIComponent(token)}`, {
				method: 'POST',
				credentials: 'include'
			});
			const data = await response.json();
			if (response.ok && data.success) {
				success = true;
				setTimeout(() => goto('/portal'), 1400);
			} else {
				error = data.detail || 'Invalid or expired access link.';
			}
		} catch (e: any) {
			error = e.message || 'Failed to verify access link.';
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head><title>Signing in · H7CTF Portal</title></svelte:head>

<div class="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-10">
	<div class="pointer-events-none absolute left-1/2 top-[-10%] h-[440px] w-[760px] -translate-x-1/2 rounded-full bg-brass/[0.07] blur-[130px]"></div>

	<div class="relative w-full max-w-md text-center">
		<div class="surface p-8">
			<div class="accent-bar"></div>
			{#if loading}
				<div class="mx-auto flex h-14 w-14 items-center justify-center">
					<span class="h-9 w-9 animate-spin rounded-full border-2 border-brass/25 border-t-brass"></span>
				</div>
				<h2 class="mt-4 text-lg font-semibold text-foreground">Signing you in</h2>
				<p class="mt-1.5 text-sm text-foreground-muted">One moment…</p>
			{:else if success}
				<div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brass/10 text-brass ring-1 ring-inset ring-brass/20">
					<svg class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>
				</div>
				<h2 class="mt-4 text-lg font-semibold text-foreground">You're in</h2>
				<p class="mt-1.5 text-sm text-foreground-muted">Taking you to your dashboard…</p>
			{:else}
				<div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-destructive/10 text-destructive ring-1 ring-inset ring-destructive/20">
					<svg class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
				</div>
				<h2 class="mt-4 text-lg font-semibold text-foreground">Link didn't work</h2>
				<p class="mx-auto mt-1.5 max-w-xs text-sm leading-relaxed text-foreground-muted">{error}</p>
				<a href="/portal/login" class="btn-accent mt-5 inline-flex">Request a new link</a>
			{/if}
		</div>
	</div>
</div>
