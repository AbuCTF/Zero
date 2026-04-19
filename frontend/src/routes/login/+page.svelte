<script lang="ts">
	import { auth, ApiError, api } from '$lib/api';
	import { goto } from '$app/navigation';

	let email = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);
	let showPassword = $state(false);

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
	<title>Sign in — ZeroPool</title>
</svelte:head>

<div class="min-h-screen bg-background flex flex-col">
	<!-- Subtle ambient glow at top -->
	<div class="fixed inset-0 pointer-events-none" aria-hidden="true">
		<div class="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px]"
			style="background: radial-gradient(ellipse at 50% 0%, hsl(var(--foreground) / 0.04), transparent 70%);"></div>
	</div>

	<div class="flex-1 flex flex-col items-center justify-center px-6 relative">
		<!-- Logo -->
		<a href="/" class="mb-12 block opacity-80 hover:opacity-100 transition-opacity duration-200" aria-label="Home">
			<img src="/logo.png" alt="ZeroPool" class="h-7 w-auto" />
		</a>

		<div class="w-full max-w-[320px]">
			<div class="mb-7">
				<h1 class="text-xl font-semibold tracking-tight text-foreground">Sign in</h1>
				<p class="text-sm text-foreground-muted mt-1">Admin panel access</p>
			</div>

			<form onsubmit={handleSubmit} class="space-y-4">
				{#if error}
					<div class="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/20 text-destructive text-xs rounded-md">
						<svg class="w-3.5 h-3.5 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
						</svg>
						<span class="font-mono">{error}</span>
					</div>
				{/if}

				<div class="space-y-1.5">
					<label for="email" class="input-label">Email</label>
					<input
						type="email"
						id="email"
						bind:value={email}
						class="input"
						placeholder="you@example.com"
						autocomplete="email"
						required
						disabled={loading}
					/>
				</div>

				<div class="space-y-1.5">
					<div class="flex items-center justify-between">
						<label for="password" class="input-label">Password</label>
						<button
							type="button"
							onclick={() => { showForgotPassword = true; forgotEmail = email; }}
							class="text-[10px] font-mono text-foreground-muted hover:text-foreground tracking-wide transition-colors"
						>
							Forgot?
						</button>
					</div>
					<div class="relative">
						<input
							type={showPassword ? 'text' : 'password'}
							id="password"
							bind:value={password}
							class="input pr-9"
							placeholder="••••••••"
							autocomplete="current-password"
							required
							disabled={loading}
						/>
						<button
							type="button"
							onclick={() => showPassword = !showPassword}
							class="absolute right-2.5 top-1/2 -translate-y-1/2 text-foreground-muted/60 hover:text-foreground-muted transition-colors"
							tabindex="-1"
							aria-label={showPassword ? 'Hide password' : 'Show password'}
						>
							{#if showPassword}
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/>
								</svg>
							{:else}
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
								</svg>
							{/if}
						</button>
					</div>
				</div>

				<button type="submit" class="btn-primary w-full mt-1" disabled={loading}>
					{#if loading}
						<svg class="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
						</svg>
						Signing in...
					{:else}
						Sign in →
					{/if}
				</button>
			</form>

			<p class="text-center text-xs text-foreground-muted/40 mt-8">
				<a href="/" class="hover:text-foreground-muted transition-colors">← Back to home</a>
			</p>
		</div>
	</div>
</div>

<!-- Forgot Password Modal -->
{#if showForgotPassword}
	<div
		class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center z-50 p-4"
		onclick={(e) => { if (e.target === e.currentTarget) { showForgotPassword = false; forgotMessage = ''; forgotError = ''; } }}
	>
		<div class="bg-card border border-border rounded-xl shadow-2xl w-full max-w-sm fade-in">
			<div class="px-5 py-4 border-b border-border flex items-center justify-between">
				<h2 class="text-sm font-semibold tracking-tight">Reset password</h2>
				<button
					onclick={() => { showForgotPassword = false; forgotMessage = ''; forgotError = ''; }}
					class="text-foreground-muted hover:text-foreground transition-colors p-1 -mr-1"
				>
					<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>

			<form onsubmit={handleForgotPassword} class="p-5 space-y-4">
				{#if forgotMessage}
					<div class="p-3 text-sm bg-success/10 text-success rounded-md border border-success/20 leading-relaxed">
						{forgotMessage}
					</div>
					<button type="button" onclick={() => { showForgotPassword = false; forgotMessage = ''; }} class="btn-secondary w-full">
						Done
					</button>
				{:else}
					<p class="text-sm text-foreground-muted leading-relaxed">
						Enter your email and we'll send you a reset link.
					</p>

					{#if forgotError}
						<div class="p-3 text-xs bg-destructive/10 text-destructive rounded-md border border-destructive/20 font-mono">
							{forgotError}
						</div>
					{/if}

					<div class="space-y-1.5">
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

					<div class="flex gap-2">
						<button type="button" onclick={() => showForgotPassword = false} class="btn-secondary flex-1">
							Cancel
						</button>
						<button type="submit" class="btn-primary flex-1" disabled={forgotLoading}>
							{forgotLoading ? 'Sending...' : 'Send link'}
						</button>
					</div>
				{/if}
			</form>
		</div>
	</div>
{/if}
