<script lang="ts">
	import { publicApi } from '$lib/api';
	import { formatDate } from '$lib/utils';

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
	<title>Verify Certificate - ZeroPool</title>
</svelte:head>

<div class="min-h-screen bg-background flex items-center justify-center px-4">
	<div class="w-full max-w-md">
		<div class="text-center mb-8">
			<a href="/" class="text-2xl font-semibold text-foreground">
				ZeroPool
			</a>
			<p class="text-sm text-foreground-muted mt-2">
				Certificate Verification
			</p>
		</div>

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

		<p class="text-center text-sm text-foreground-muted mt-6">
			<a href="/" class="hover:text-foreground transition-colors">
				Back to home
			</a>
		</p>
	</div>
</div>
