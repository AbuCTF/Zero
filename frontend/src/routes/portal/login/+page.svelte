<script lang="ts">
	import { api } from '$lib/api';

	let email = $state('');
	let loading = $state(false);
	let error = $state('');
	let sent = $state(false);

	let showEventPicker = $state(false);
	let availableEvents = $state<Array<{ id: string; name: string; slug: string }>>([]);

	let resendingLink = $state(false);
	let resendingVerif = $state(false);
	let linkNote = $state('');
	let verifNote = $state('');

	async function handleSubmit(selectedEventId?: string) {
		if (!email) return;
		loading = true;
		error = '';
		try {
			const result = await api.participant.requestAccess(email, selectedEventId);
			if (result.requires_event_selection && result.events) {
				availableEvents = result.events;
				showEventPicker = true;
			} else {
				sent = true;
			}
		} catch (e: any) {
			error = e.message || 'Could not send the link. Please try again.';
		} finally {
			loading = false;
		}
	}

	async function resendLink() {
		if (resendingLink) return;
		resendingLink = true;
		linkNote = '';
		try {
			await api.participant.requestAccess(email);
			linkNote = 'Sent again — give it a minute, and check your spam folder.';
		} catch (e: any) {
			linkNote = e?.message || 'Could not resend just now — try again shortly.';
		} finally {
			resendingLink = false;
		}
	}

	async function resendVerification() {
		if (resendingVerif) return;
		resendingVerif = true;
		verifNote = '';
		try {
			const r = await api.auth.resendVerification({ email });
			verifNote = r.message || 'If your email still needs verifying, a link is on its way.';
		} catch (e: any) {
			verifNote = e?.message || 'Could not send a verification email just now.';
		} finally {
			resendingVerif = false;
		}
	}

	function useDifferentEmail() {
		sent = false;
		showEventPicker = false;
		availableEvents = [];
		linkNote = '';
		verifNote = '';
		error = '';
	}

	function goBack() {
		showEventPicker = false;
		availableEvents = [];
	}
</script>

<svelte:head><title>Sign in · H7CTF Portal</title></svelte:head>

<div class="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-10">
	<div class="relative w-full max-w-md">
		<div class="mb-8 text-center">
			<a href="/" class="inline-block"><img src="/logo.png" alt="ZeroPool" class="mx-auto h-9 w-auto" /></a>
			<h1 class="mt-6 text-2xl font-semibold tracking-tight text-foreground">Participant Portal</h1>
			<p class="mt-1.5 text-sm text-foreground-muted">Sign in with a magic link — no password needed.</p>
		</div>

		<div class="surface p-6 sm:p-7">
			{#if sent}
				<div class="py-2 text-center">
					<div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary ring-1 ring-inset ring-primary/20">
						<svg class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.7"><path stroke-linecap="round" stroke-linejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
					</div>
					<h2 class="mt-4 text-lg font-semibold text-foreground">Check your email</h2>
					<p class="mt-1.5 text-sm leading-relaxed text-foreground-muted">
						If <span class="font-medium text-foreground text-mono">{email}</span> is registered and verified,
						a login link is on its way. It expires in 1&nbsp;hour.
					</p>

					<div class="mt-5">
						<button onclick={resendLink} disabled={resendingLink} class="btn-secondary btn-sm w-full">
							{resendingLink ? 'Resending…' : 'Resend login link'}
						</button>
						{#if linkNote}<p class="mt-2 text-xs text-foreground-muted">{linkNote}</p>{/if}
					</div>

					<div class="mt-5 rounded-xl border border-border bg-background-secondary/50 p-4 text-left">
						<p class="text-xs font-medium text-foreground">Didn't get a login link?</p>
						<p class="mt-1 text-xs leading-relaxed text-foreground-muted">
							You'll only receive one once your email is verified. If you never verified it, resend the verification email first.
						</p>
						<button onclick={resendVerification} disabled={resendingVerif} class="btn-ghost btn-sm mt-2.5 -ml-2">
							{resendingVerif ? 'Sending…' : 'Resend verification email'}
						</button>
						{#if verifNote}<p class="mt-1.5 text-xs text-primary">{verifNote}</p>{/if}
					</div>

					<button onclick={useDifferentEmail} class="btn-ghost btn-sm mt-4">← Use a different email</button>
				</div>
			{:else if showEventPicker}
				<div class="space-y-4">
					<div class="text-center">
						<h2 class="text-lg font-semibold text-foreground">Select an event</h2>
						<p class="mt-1 text-sm text-foreground-muted">You're registered for a few — which one?</p>
					</div>
					<div class="space-y-2">
						{#each availableEvents as ev}
							<button
								onclick={() => handleSubmit(ev.id)}
								disabled={loading}
								class="surface-plain surface-link flex w-full items-center justify-between gap-2 p-4 text-left disabled:opacity-50"
							>
								<span class="min-w-0">
									<span class="block truncate text-sm font-medium text-foreground">{ev.name}</span>
									<span class="block truncate text-xs text-foreground-muted text-mono">{ev.slug}</span>
								</span>
								<svg class="h-4 w-4 shrink-0 text-foreground-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" /></svg>
							</button>
						{/each}
					</div>
					<button onclick={goBack} class="btn-ghost w-full">← Back</button>
				</div>
			{:else}
				{#if error}
					<div class="mb-4 rounded-lg border border-destructive/25 bg-destructive/10 px-4 py-3 text-sm text-destructive">
						{error}
					</div>
				{/if}
				<form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
					<div>
						<label for="email" class="input-label">Email address</label>
						<input id="email" type="email" bind:value={email} class="input" placeholder="you@example.com" required />
						<p class="mt-1.5 text-xs text-foreground-muted">The email you registered with.</p>
					</div>
					<button type="submit" disabled={loading} class="btn-accent w-full">
						{loading ? 'Sending…' : 'Send magic link'}
					</button>
				</form>
			{/if}
		</div>

		<p class="mt-6 text-center text-sm text-foreground-muted">
			<a href="/" class="transition-colors hover:text-foreground">← Back to home</a>
		</p>
	</div>
</div>
