<script lang="ts">
	import { auth, ApiError, api } from '$lib/api';
	import { goto } from '$app/navigation';

	let email = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);
	
	// Forgot password state
	let showForgotPassword = $state(false);
	let forgotEmail = $state('');
	let forgotLoading = $state(false);
	let forgotMessage = $state('');
	let forgotError = $state('');

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
	
	async function handleForgotPassword(e: SubmitEvent) {
		e.preventDefault();
		forgotError = '';
		forgotMessage = '';
		forgotLoading = true;
		
		try {
			await api.post('/auth/forgot-password', { email: forgotEmail });
			forgotMessage = 'If an account exists with this email, you will receive a password reset link.';
		} catch (err) {
			if (err instanceof ApiError) {
				forgotError = err.message;
			} else {
				forgotError = 'An unexpected error occurred';
			}
		} finally {
			forgotLoading = false;
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
			
			<div class="text-right">
				<button 
					type="button" 
					onclick={() => { showForgotPassword = true; forgotEmail = email; }}
					class="text-xs text-primary hover:underline"
				>
					Forgot password?
				</button>
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

<!-- Forgot Password Modal -->
{#if showForgotPassword}
	<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
		<div class="bg-card rounded-xl shadow-xl w-full max-w-sm">
			<div class="px-6 py-4 border-b border-border flex items-center justify-between">
				<h2 class="text-lg font-semibold">Reset Password</h2>
				<button onclick={() => { showForgotPassword = false; forgotMessage = ''; forgotError = ''; }} class="btn btn-ghost btn-sm">
					<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>
			
			<form onsubmit={handleForgotPassword} class="p-6 space-y-4">
				{#if forgotMessage}
					<div class="p-3 text-sm bg-primary/10 text-primary rounded-lg">
						{forgotMessage}
					</div>
				{:else}
					<p class="text-sm text-foreground-muted">
						Enter your email address and we'll send you a link to reset your password.
					</p>
					
					{#if forgotError}
						<div class="p-3 text-xs bg-destructive/10 text-destructive rounded">
							{forgotError}
						</div>
					{/if}
					
					<div>
						<label for="forgot-email" class="input-label">Email</label>
						<input
							type="email"
							id="forgot-email"
							bind:value={forgotEmail}
							class="input"
							placeholder="you@example.com"
							required
							disabled={forgotLoading}
						/>
					</div>
					
					<button type="submit" class="btn-primary w-full" disabled={forgotLoading}>
						{#if forgotLoading}
							Sending...
						{:else}
							Send Reset Link
						{/if}
					</button>
				{/if}
			</form>
		</div>
	</div>
{/if}
