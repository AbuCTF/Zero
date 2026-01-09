<script lang="ts">
	import { auth, ApiError } from '$lib/api';
	import { goto } from '$app/navigation';

	let email = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);

	async function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		loading = true;

		try {
			await auth.login(email, password);
			goto('/admin');
		} catch (err) {
			if (err instanceof ApiError) {
				error = err.message;
			} else {
				error = 'An unexpected error occurred';
			}
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Login — ZeroPool</title>
</svelte:head>

<div class="min-h-screen bg-background flex items-center justify-center px-6">
	<div class="w-full max-w-xs">
		<div class="text-center mb-8">
			<a href="/" class="inline-flex items-center gap-2 text-foreground mb-4">
				<div class="w-10 h-10 rounded-xl bg-foreground flex items-center justify-center">
					<svg class="w-5 h-5 text-background" viewBox="0 0 24 24" fill="none">
						<path d="M12 2L2 7l10 5 10-5-10-5z" fill="currentColor" opacity="0.3"/>
						<path d="M2 17l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
						<path d="M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
					</svg>
				</div>
			</a>
			<h1 class="text-lg font-semibold text-foreground tracking-tight">Sign in</h1>
			<p class="text-sm text-foreground-muted mt-1">Enter your credentials</p>
		</div>

		<form onsubmit={handleSubmit} class="space-y-4">
			{#if error}
				<div class="p-3 text-xs bg-destructive/10 text-destructive rounded text-mono">
					{error}
				</div>
			{/if}

			<div>
				<label for="email" class="input-label">Email</label>
				<input
					type="email"
					id="email"
					bind:value={email}
					class="input"
					placeholder="you@example.com"
					required
					disabled={loading}
				/>
			</div>

			<div>
				<label for="password" class="input-label">Password</label>
				<input
					type="password"
					id="password"
					bind:value={password}
					class="input"
					placeholder="••••••••"
					required
					disabled={loading}
				/>
			</div>

			<button type="submit" class="btn-primary w-full" disabled={loading}>
				{#if loading}
					<svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
					</svg>
					Signing in...
				{:else}
					Sign in
				{/if}
			</button>
		</form>

		<p class="text-center text-xs text-foreground-muted mt-6">
			<a href="/" class="hover:text-foreground transition-colors">← Back to home</a>
		</p>
	</div>
</div>
