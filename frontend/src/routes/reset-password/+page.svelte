<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	let token = $derived($page.url.searchParams.get('token') || '');
	let password = $state('');
	let confirmPassword = $state('');
	let error = $state('');
	let success = $state(false);
	let loading = $state(false);

	async function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		
		if (password !== confirmPassword) {
			error = 'Passwords do not match';
			return;
		}
		
		if (password.length < 8) {
			error = 'Password must be at least 8 characters';
			return;
		}
		
		loading = true;

		try {
			await api.post('/auth/reset-password', { token, password });
			success = true;
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
	<title>Reset Password — ZeroPool</title>
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
			<h1 class="text-lg font-semibold text-foreground tracking-tight">Reset Password</h1>
			<p class="text-sm text-foreground-muted mt-1">Enter your new password</p>
		</div>

		{#if !token}
			<div class="p-4 bg-destructive/10 text-destructive rounded-lg text-sm text-center">
				Invalid or missing reset token. Please request a new password reset link.
			</div>
			<p class="text-center text-xs text-foreground-muted mt-6">
				<a href="/login" class="hover:text-foreground transition-colors">← Back to login</a>
			</p>
		{:else if success}
			<div class="p-4 bg-primary/10 text-primary rounded-lg text-sm text-center">
				<svg class="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
				</svg>
				Password reset successfully! You can now sign in with your new password.
			</div>
			<p class="text-center mt-6">
				<a href="/login" class="btn-primary inline-block px-6">Sign in</a>
			</p>
		{:else}
			<form onsubmit={handleSubmit} class="space-y-4">
				{#if error}
					<div class="p-3 text-xs bg-destructive/10 text-destructive rounded text-mono">
						{error}
					</div>
				{/if}

				<div>
					<label for="password" class="input-label">New Password</label>
					<input
						type="password"
						id="password"
						bind:value={password}
						class="input"
						placeholder="••••••••"
						required
						minlength="8"
						disabled={loading}
					/>
				</div>

				<div>
					<label for="confirm-password" class="input-label">Confirm Password</label>
					<input
						type="password"
						id="confirm-password"
						bind:value={confirmPassword}
						class="input"
						placeholder="••••••••"
						required
						minlength="8"
						disabled={loading}
					/>
				</div>

				<button type="submit" class="btn-primary w-full" disabled={loading}>
					{#if loading}
						<svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
						</svg>
						Resetting...
					{:else}
						Reset Password
					{/if}
				</button>
			</form>

			<p class="text-center text-xs text-foreground-muted mt-6">
				<a href="/login" class="hover:text-foreground transition-colors">← Back to login</a>
			</p>
		{/if}
	</div>
</div>
