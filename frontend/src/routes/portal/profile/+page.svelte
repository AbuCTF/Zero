<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type Participant } from '$lib/api';

	let participant = $state<Participant | null>(null);
	let loading = $state(true);
	let saving = $state(false);
	let message = $state<{ type: 'success' | 'error'; text: string } | null>(null);

	let name = $state('');
	let country = $state('');
	let organization = $state('');
	let participantType = $state('');

	onMount(async () => {
		try {
			participant = await api.participant.me();
			hydrate(participant);
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	});

	function hydrate(p: Participant) {
		const x = p.extra_data ?? {};
		name = p.name ?? '';
		country = (x.country as string) ?? '';
		organization = (x.organization as string) ?? '';
		participantType = (x.participant_type as string) ?? '';
	}

	const extra = $derived(participant?.extra_data ?? {});
	const discordHandle = $derived(extra.discord_username as string | undefined);
	const initial = $derived((name || participant?.email || '?').charAt(0).toUpperCase());

	const dirty = $derived(
		participant != null &&
			(name.trim() !== (participant.name ?? '') ||
				country.trim() !== ((extra.country as string) ?? '') ||
				organization.trim() !== ((extra.organization as string) ?? '') ||
				participantType !== ((extra.participant_type as string) ?? ''))
	);

	async function save() {
		if (!name.trim()) {
			message = { type: 'error', text: 'Name cannot be empty.' };
			return;
		}
		saving = true;
		message = null;
		try {
			const updated = await api.participant.updateProfile({
				name: name.trim(),
				metadata: {
					country: country.trim(),
					organization: organization.trim(),
					participant_type: participantType
				}
			});
			participant = updated;
			hydrate(updated);
			message = { type: 'success', text: 'Profile saved.' };
		} catch (e) {
			message = { type: 'error', text: (e as Error)?.message || 'Could not save. Please try again.' };
		} finally {
			saving = false;
		}
	}
</script>

<svelte:head><title>Profile · H7CTF Portal</title></svelte:head>

<div class="page-header">
	<h1 class="text-display">Profile</h1>
	<p class="page-subtitle">Your details and verified identity.</p>
</div>

{#if loading}
	<div class="space-y-4">
		<div class="skeleton h-24 w-full rounded-lg"></div>
		<div class="skeleton h-64 w-full rounded-lg"></div>
	</div>
{:else if participant}
	<div class="space-y-6">
		<!-- Identity header -->
		<div class="card flex items-center gap-4">
			<div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-accent text-xl font-medium text-foreground">
				{initial}
			</div>
			<div class="min-w-0">
				<div class="truncate text-lg font-semibold text-foreground">
					{name || participant.username || 'Participant'}
				</div>
				<div class="truncate text-sm text-foreground-muted">{participant.email}</div>
			</div>
		</div>

		<!-- Verified identity (read-only) -->
		<div class="card">
			<div class="text-label mb-4">Verified identity</div>
			<div class="data-row">
				<span class="data-label">Email</span>
				<span class="flex items-center gap-2">
					<span class="data-value">{participant.email}</span>
					{#if participant.email_verified}
						<span class="badge-success">Verified</span>
					{:else}
						<span class="badge-warning">Unverified</span>
					{/if}
				</span>
			</div>
			<div class="data-row">
				<span class="data-label">Discord</span>
				<span class="flex items-center gap-2">
					{#if discordHandle}
						<span class="data-value">@{discordHandle}</span>
						<span class="badge-success">Connected</span>
					{:else}
						<span class="data-value text-foreground-muted">Not linked</span>
					{/if}
				</span>
			</div>
			<p class="mt-3 text-xs text-foreground-muted">
				Email and Discord are verified at registration and can't be changed here.
			</p>
		</div>

		<!-- Editable details -->
		<div class="card">
			<div class="text-label mb-4">Your details</div>
			<div class="space-y-4">
				<div>
					<label for="name" class="input-label">Full name</label>
					<input id="name" class="input" bind:value={name} maxlength="120" placeholder="Your name" />
				</div>
				<div class="grid gap-4 sm:grid-cols-2">
					<div>
						<label for="org" class="input-label">College / Organization</label>
						<input id="org" class="input" bind:value={organization} maxlength="200" placeholder="College or company" />
					</div>
					<div>
						<label for="country" class="input-label">Country</label>
						<input id="country" class="input" bind:value={country} maxlength="64" placeholder="Country" />
					</div>
				</div>
				<div>
					<label for="ptype" class="input-label">You are a…</label>
					<select id="ptype" class="input" bind:value={participantType}>
						<option value="">Prefer not to say</option>
						<option value="student">Student</option>
						<option value="professional">Professional</option>
					</select>
				</div>
			</div>

			<div class="mt-5 flex flex-wrap items-center gap-3">
				<button class="btn-primary" onclick={save} disabled={saving || !dirty}>
					{saving ? 'Saving…' : 'Save changes'}
				</button>
				{#if message}
					<span class="text-sm {message.type === 'success' ? 'text-success' : 'text-destructive'}">
						{message.text}
					</span>
				{/if}
			</div>
		</div>
	</div>
{/if}
