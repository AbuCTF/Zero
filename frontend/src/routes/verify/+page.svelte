<script lang="ts">
	import { publicApi } from '$lib/api';
	import { formatDate } from '$lib/utils';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';

	// Mode: 'loading', 'email', 'certificate'
	let mode = $state<'loading' | 'email' | 'certificate'>('loading');
	let token = $state<string | null>(null);

	// Email verification state
	let emailVerifying = $state(false);
	let emailResult = $state<{
		checked: boolean;
		success: boolean;
		message?: string;
		event?: {
			name?: string;
			discord_url?: string;
			event_url?: string;
		};
	}>({ checked: false, success: false });

	// Certificate verification state
	let code = $state('');
	let result = $state<{
		checked: boolean;
		valid: boolean;
		participant_name?: string;
		event_name?: string;
		rank?: number;
		issued_at?: string;
	}>({ checked: false, valid: false });
	let loading = $state(false);

	onMount(async () => {
		// Get URL params on client side
		const urlParams = new URLSearchParams(window.location.search);
		token = urlParams.get('token');
		const codeParam = urlParams.get('code');

		if (token) {
			mode = 'email';
			await verifyEmail();
		} else {
			mode = 'certificate';
			if (codeParam) {
				code = codeParam;
				await verify();
			}
		}
	});

	async function verifyEmail() {
		if (!token) return;
		
		emailVerifying = true;
		emailResult = { checked: false, success: false };

		try {
			const response = await fetch('/api/auth/verify-email', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ token }),
				credentials: 'include'
			});
			
			const data = await response.json();
			
			if (response.ok) {
				emailResult = { 
					checked: true, 
					success: true, 
					message: data.message || 'Email verified successfully!',
					event: data.event
				};
				// Don't auto-redirect - let user read the message and click
			} else {
				emailResult = { 
					checked: true, 
					success: false, 
					message: data.detail || 'Verification failed. The link may have expired.' 
				};
			}
		} catch {
			emailResult = { 
				checked: true, 
				success: false, 
				message: 'An error occurred during verification.' 
			};
		} finally {
			emailVerifying = false;
		}
	}

	async function verify() {
		if (!code.trim()) return;
		
		loading = true;
		result = { checked: false, valid: false };

		try {
			const data = await publicApi.verifyCertificate(code.trim());
			result = { checked: true, ...data };
		} catch {
			result = { checked: true, valid: false };
		} finally {
			loading = false;
		}
	}

	function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		verify();
	}
</script>

<svelte:head>
	<title>{mode === 'email' ? 'Verify Email' : 'Verify Certificate'} - ZeroPool</title>
</svelte:head>

<div class="min-h-screen bg-background flex items-center justify-center px-4">
	<div class="w-full max-w-md">
		<div class="text-center mb-8">
			<a href="/" class="text-2xl font-semibold text-foreground">
				ZeroPool
			</a>
			<p class="text-sm text-foreground-muted mt-2">
				{mode === 'email' ? 'Email Verification' : mode === 'certificate' ? 'Certificate Verification' : 'Verification'}
			</p>
		</div>

		{#if mode === 'loading'}
			<!-- Loading state -->
			<div class="card">
				<div class="flex flex-col items-center py-8">
					<svg class="animate-spin h-8 w-8 text-primary mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
					</svg>
					<p class="text-foreground-muted">Loading...</p>
				</div>
			</div>
		{:else if mode === 'email'}
			<!-- Email Verification -->
			<div class="card">
				{#if emailVerifying}
					<div class="flex flex-col items-center py-8">
						<svg class="animate-spin h-8 w-8 text-primary mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
						</svg>
						<p class="text-foreground-muted">Verifying your email...</p>
					</div>
				{:else if emailResult.checked}
					{#if emailResult.success}
						<div class="p-6 text-center">
							<div class="w-16 h-16 mx-auto mb-4 bg-success/20 rounded-full flex items-center justify-center">
								<svg class="w-8 h-8 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
								</svg>
							</div>
							<h2 class="text-xl font-semibold text-foreground mb-2">You're All Set!</h2>
							<p class="text-foreground-muted mb-6">
								Your email has been verified successfully.
								{#if emailResult.event?.name}
									Welcome to <strong>{emailResult.event.name}</strong>!
								{/if}
							</p>
							
							<!-- Action Buttons -->
							<div class="space-y-3">
								<a href="/portal" class="btn-primary w-full inline-flex items-center justify-center gap-2">
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>
									</svg>
									Go to Dashboard
								</a>
								
								{#if emailResult.event?.event_url}
									<a 
										href={emailResult.event.event_url} 
										target="_blank" 
										rel="noopener noreferrer"
										class="btn-outline w-full inline-flex items-center justify-center gap-2"
									>
										<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
										</svg>
										Visit Event Platform
									</a>
								{/if}
								
								{#if emailResult.event?.discord_url}
									<a 
										href={emailResult.event.discord_url} 
										target="_blank" 
										rel="noopener noreferrer"
										class="btn-ghost w-full inline-flex items-center justify-center gap-2 text-[#5865F2] hover:bg-[#5865F2]/10"
									>
										<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
											<path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
										</svg>
										Join Discord Server
									</a>
								{/if}
							</div>
							
							<p class="text-xs text-foreground-muted mt-6">
								You can access your certificates and prizes anytime from the dashboard.
							</p>
						</div>
					{:else}
						<div class="p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
							<div class="flex items-center gap-2 mb-3">
								<svg class="w-5 h-5 text-destructive" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
								</svg>
								<span class="font-medium text-destructive">Verification Failed</span>
							</div>
							<p class="text-sm text-foreground-muted">
								{emailResult.message}
							</p>
						</div>
					{/if}
				{/if}
			</div>
		{:else}
			<!-- Certificate Verification -->
			<div class="card">
				<form onsubmit={handleSubmit} class="mb-6">
					<label for="code" class="block text-sm font-medium text-foreground mb-1.5">
						Verification Code
					</label>
					<div class="flex gap-2">
						<input
							type="text"
							id="code"
							bind:value={code}
							class="input flex-1"
							placeholder="Enter certificate code"
							disabled={loading}
						/>
						<button type="submit" class="btn-primary" disabled={loading || !code.trim()}>
							{#if loading}
								<svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
									<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
									<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
								</svg>
							{:else}
								Verify
							{/if}
						</button>
					</div>
				</form>

				{#if result.checked}
					{#if result.valid}
						<div class="p-4 bg-success/10 border border-success/20 rounded-lg">
							<div class="flex items-center gap-2 mb-3">
								<svg class="w-5 h-5 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
								</svg>
								<span class="font-medium text-success">Valid Certificate</span>
							</div>
							<dl class="space-y-2 text-sm">
								<div class="flex justify-between">
									<dt class="text-foreground-muted">Participant</dt>
									<dd class="text-foreground font-medium">{result.participant_name}</dd>
								</div>
								<div class="flex justify-between">
									<dt class="text-foreground-muted">Event</dt>
									<dd class="text-foreground">{result.event_name}</dd>
								</div>
								{#if result.rank}
									<div class="flex justify-between">
										<dt class="text-foreground-muted">Rank</dt>
										<dd class="text-foreground">#{result.rank}</dd>
									</div>
								{/if}
								{#if result.issued_at}
									<div class="flex justify-between">
										<dt class="text-foreground-muted">Issued</dt>
										<dd class="text-foreground">{formatDate(result.issued_at)}</dd>
									</div>
								{/if}
							</dl>
						</div>
					{:else}
						<div class="p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
							<div class="flex items-center gap-2">
								<svg class="w-5 h-5 text-destructive" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
								</svg>
								<span class="font-medium text-destructive">Invalid Certificate</span>
							</div>
							<p class="text-sm text-foreground-muted mt-2">
								This verification code does not match any certificate in our system.
							</p>
						</div>
					{/if}
				{/if}
			</div>
		{/if}

		<p class="text-center text-sm text-foreground-muted mt-6">
			<a href="/" class="hover:text-foreground transition-colors">
				Back to home
			</a>
		</p>
	</div>
</div>
