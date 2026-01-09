<script lang="ts">
	import { admin, type EmailProvider, ApiError } from '$lib/api';
	import { formatNumber, getProviderDisplayName, formatRelativeTime } from '$lib/utils';
	import { onMount } from 'svelte';

	let providers = $state<EmailProvider[]>([]);
	let loading = $state(true);
	let showAddModal = $state(false);
	let testingId = $state<string | null>(null);
	let testEmail = $state('');
	let testResult = $state<{ success: boolean; message: string } | null>(null);

	// Form state for adding provider
	let newProvider = $state({
		name: '',
		provider_type: 'smtp',
		config: {} as Record<string, string>,
		daily_limit: 300,
		hourly_limit: 50,
		minute_limit: 10,
		second_limit: 1,
		priority: 0
	});

	let saving = $state(false);
	let error = $state('');

	onMount(() => {
		loadProviders();
	});

	async function loadProviders() {
		loading = true;
		try {
			providers = await admin.providers.list();
		} catch (err) {
			console.error('Failed to load providers:', err);
		} finally {
			loading = false;
		}
	}

	async function toggleProvider(provider: EmailProvider) {
		try {
			await admin.providers.update(provider.id, { is_active: !provider.is_active });
			await loadProviders();
		} catch (err) {
			console.error('Failed to toggle provider:', err);
		}
	}

	async function deleteProvider(provider: EmailProvider) {
		if (!confirm(`Delete provider "${provider.name}"?`)) return;
		
		try {
			await admin.providers.delete(provider.id);
			await loadProviders();
		} catch (err) {
			console.error('Failed to delete provider:', err);
		}
	}

	async function testProvider(provider: EmailProvider) {
		if (!testEmail) {
			testResult = { success: false, message: 'Please enter a test email address' };
			return;
		}

		testingId = provider.id;
		testResult = null;

		try {
			const result = await admin.providers.test(provider.id, testEmail);
			testResult = {
				success: result.sent,
				message: result.sent ? 'Test email sent successfully!' : (result.error || 'Failed to send')
			};
		} catch (err) {
			testResult = {
				success: false,
				message: err instanceof ApiError ? err.message : 'Test failed'
			};
		} finally {
			testingId = null;
		}
	}

	async function addProvider() {
		error = '';
		saving = true;

		try {
			await admin.providers.create(newProvider);
			showAddModal = false;
			newProvider = {
				name: '',
				provider_type: 'smtp',
				config: {},
				daily_limit: 300,
				hourly_limit: 50,
				minute_limit: 10,
				second_limit: 1,
				priority: 0
			};
			await loadProviders();
		} catch (err) {
			error = err instanceof ApiError ? err.message : 'Failed to add provider';
		} finally {
			saving = false;
		}
	}

	const providerConfigs: Record<string, { label: string; fields: { key: string; label: string; type: string }[] }> = {
		smtp: {
			label: 'SMTP Server',
			fields: [
				{ key: 'host', label: 'Host', type: 'text' },
				{ key: 'port', label: 'Port', type: 'number' },
				{ key: 'username', label: 'Username', type: 'text' },
				{ key: 'password', label: 'Password', type: 'password' },
				{ key: 'from_email', label: 'From Email', type: 'email' },
				{ key: 'from_name', label: 'From Name', type: 'text' }
			]
		},
		brevo: {
			label: 'Brevo (Sendinblue)',
			fields: [
				{ key: 'api_key', label: 'API Key', type: 'password' },
				{ key: 'from_email', label: 'From Email', type: 'email' },
				{ key: 'from_name', label: 'From Name', type: 'text' }
			]
		},
		mailgun: {
			label: 'Mailgun',
			fields: [
				{ key: 'api_key', label: 'API Key', type: 'password' },
				{ key: 'domain', label: 'Domain', type: 'text' },
				{ key: 'from_email', label: 'From Email', type: 'email' },
				{ key: 'from_name', label: 'From Name', type: 'text' }
			]
		},
		aws_ses: {
			label: 'AWS SES',
			fields: [
				{ key: 'access_key_id', label: 'Access Key ID', type: 'text' },
				{ key: 'secret_access_key', label: 'Secret Access Key', type: 'password' },
				{ key: 'region', label: 'Region', type: 'text' },
				{ key: 'from_email', label: 'From Email', type: 'email' },
				{ key: 'from_name', label: 'From Name', type: 'text' }
			]
		},
		mailjet: {
			label: 'Mailjet',
			fields: [
				{ key: 'api_key', label: 'API Key', type: 'text' },
				{ key: 'api_secret', label: 'API Secret', type: 'password' },
				{ key: 'from_email', label: 'From Email', type: 'email' },
				{ key: 'from_name', label: 'From Name', type: 'text' }
			]
		},
		gmail: {
			label: 'Gmail SMTP',
			fields: [
				{ key: 'email', label: 'Gmail Address', type: 'email' },
				{ key: 'password', label: 'App Password', type: 'password' }
			]
		}
	};
</script>

<div class="p-6 lg:p-8">
	<div class="flex items-center justify-between mb-8">
		<div>
			<h1 class="text-2xl font-semibold text-foreground">Email Providers</h1>
			<p class="text-sm text-foreground-muted mt-1">
				Configure and manage your email sending providers
			</p>
		</div>
		<button class="btn-primary" onclick={() => showAddModal = true}>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
			</svg>
			Add Provider
		</button>
	</div>

	<!-- Test Email Input -->
	<div class="card mb-6">
		<label for="testEmail" class="block text-sm font-medium text-foreground mb-1.5">
			Test Email Address
		</label>
		<div class="flex gap-2 max-w-md">
			<input
				type="email"
				id="testEmail"
				bind:value={testEmail}
				class="input flex-1"
				placeholder="your@email.com"
			/>
		</div>
		<p class="text-xs text-foreground-muted mt-1.5">
			Enter your email to test provider connections
		</p>
		{#if testResult}
			<div class="mt-2 text-sm {testResult.success ? 'text-success' : 'text-destructive'}">
				{testResult.message}
			</div>
		{/if}
	</div>

	<!-- Providers List -->
	{#if loading}
		<div class="space-y-4">
			{#each [1, 2, 3] as _}
				<div class="card animate-pulse">
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-4">
							<div class="w-10 h-10 bg-accent rounded"></div>
							<div>
								<div class="h-5 w-32 bg-accent rounded mb-2"></div>
								<div class="h-3 w-24 bg-accent rounded"></div>
							</div>
						</div>
						<div class="h-8 w-20 bg-accent rounded"></div>
					</div>
				</div>
			{/each}
		</div>
	{:else if providers.length === 0}
		<div class="card text-center py-12">
			<svg class="w-12 h-12 text-foreground-muted mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
			</svg>
			<p class="text-foreground-muted mb-4">No email providers configured</p>
			<button class="btn-primary" onclick={() => showAddModal = true}>
				Add your first provider
			</button>
		</div>
	{:else}
		<div class="space-y-4">
			{#each providers as provider}
				<div class="card">
					<div class="flex items-start justify-between">
						<div class="flex items-start gap-4">
							<div class="w-10 h-10 rounded-lg bg-accent flex items-center justify-center">
								<svg class="w-5 h-5 text-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
								</svg>
							</div>
							<div>
								<div class="flex items-center gap-2">
									<h3 class="font-medium text-foreground">{provider.name}</h3>
									<span class="badge-muted">{getProviderDisplayName(provider.provider_type)}</span>
									{#if !provider.is_active}
										<span class="badge-warning">Disabled</span>
									{:else if !provider.is_healthy}
										<span class="badge-destructive">Unhealthy</span>
									{:else if provider.available}
										<span class="badge-success">Active</span>
									{:else}
										<span class="badge-warning">Rate Limited</span>
									{/if}
								</div>
								<div class="flex items-center gap-4 mt-2 text-sm text-foreground-muted">
									<span>Daily: {formatNumber(provider.daily_used ?? 0)} / {formatNumber(provider.daily_limit)}</span>
									<span>Hourly: {formatNumber(provider.hourly_used ?? 0)} / {formatNumber(provider.hourly_limit)}</span>
									<span>Priority: {provider.priority}</span>
								</div>
								{#if provider.last_error}
									<p class="mt-2 text-sm text-destructive">
										Last error: {provider.last_error}
										{#if provider.last_error_at}
											({formatRelativeTime(provider.last_error_at)})
										{/if}
									</p>
								{/if}
							</div>
						</div>
						<div class="flex items-center gap-2">
							<button
								class="btn-secondary text-sm"
								onclick={() => testProvider(provider)}
								disabled={testingId === provider.id || !testEmail}
							>
								{#if testingId === provider.id}
									<svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
										<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
										<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
									</svg>
								{:else}
									Test
								{/if}
							</button>
							<button
								class="btn-secondary text-sm"
								onclick={() => toggleProvider(provider)}
							>
								{provider.is_active ? 'Disable' : 'Enable'}
							</button>
							<button
								class="btn-ghost text-sm text-destructive"
								onclick={() => deleteProvider(provider)}
							>
								Delete
							</button>
						</div>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<!-- Add Provider Modal -->
{#if showAddModal}
	<div class="fixed inset-0 z-50 flex items-center justify-center p-4">
		<div class="absolute inset-0 bg-black/50" onclick={() => showAddModal = false}></div>
		<div class="relative bg-background border border-border rounded-lg w-full max-w-lg max-h-[90vh] overflow-auto">
			<div class="p-6 border-b border-border">
				<h2 class="text-lg font-semibold text-foreground">Add Email Provider</h2>
			</div>
			<form onsubmit={(e) => { e.preventDefault(); addProvider(); }} class="p-6 space-y-4">
				{#if error}
					<div class="p-3 text-sm bg-destructive/10 text-destructive rounded-md">
						{error}
					</div>
				{/if}

				<div>
					<label for="providerName" class="block text-sm font-medium text-foreground mb-1.5">
						Provider Name
					</label>
					<input
						type="text"
						id="providerName"
						bind:value={newProvider.name}
						class="input"
						placeholder="My SMTP Server"
						required
					/>
				</div>

				<div>
					<label for="providerType" class="block text-sm font-medium text-foreground mb-1.5">
						Provider Type
					</label>
					<select
						id="providerType"
						bind:value={newProvider.provider_type}
						class="input"
						onchange={() => newProvider.config = {}}
					>
						{#each Object.entries(providerConfigs) as [key, config]}
							<option value={key}>{config.label}</option>
						{/each}
					</select>
				</div>

				<!-- Dynamic config fields -->
				{#each providerConfigs[newProvider.provider_type].fields as field}
					<div>
						<label for={field.key} class="block text-sm font-medium text-foreground mb-1.5">
							{field.label}
						</label>
						<input
							type={field.type}
							id={field.key}
							bind:value={newProvider.config[field.key]}
							class="input"
							required
						/>
					</div>
				{/each}

				<div class="grid grid-cols-2 gap-4">
					<div>
						<label for="dailyLimit" class="block text-sm font-medium text-foreground mb-1.5">
							Daily Limit
						</label>
						<input
							type="number"
							id="dailyLimit"
							bind:value={newProvider.daily_limit}
							class="input"
							min="1"
						/>
					</div>
					<div>
						<label for="hourlyLimit" class="block text-sm font-medium text-foreground mb-1.5">
							Hourly Limit
						</label>
						<input
							type="number"
							id="hourlyLimit"
							bind:value={newProvider.hourly_limit}
							class="input"
							min="1"
						/>
					</div>
				</div>

				<div>
					<label for="priority" class="block text-sm font-medium text-foreground mb-1.5">
						Priority (lower = higher priority)
					</label>
					<input
						type="number"
						id="priority"
						bind:value={newProvider.priority}
						class="input"
						min="0"
					/>
				</div>

				<div class="flex justify-end gap-3 pt-4">
					<button type="button" class="btn-secondary" onclick={() => showAddModal = false}>
						Cancel
					</button>
					<button type="submit" class="btn-primary" disabled={saving}>
						{#if saving}
							Saving...
						{:else}
							Add Provider
						{/if}
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}
