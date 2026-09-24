<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type Participant } from '$lib/api';

	let participant = $state<Participant | null>(null);
	let loading = $state(true);
	let saving = $state(false);
	let message = $state<{ type: 'success' | 'error'; text: string } | null>(null);

	let resendingVerif = $state(false);
	let verifNote = $state('');
	let linkingDiscord = $state(false);
	let discordNote = $state<{ type: 'ok' | 'err'; text: string } | null>(null);

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

	async function resendVerif() {
		if (resendingVerif) return;
		resendingVerif = true;
		verifNote = '';
		try {
			const r = await api.participant.resendVerification();
			verifNote = r.message || 'Verification email sent — check your inbox and spam.';
		} catch (e: any) {
			verifNote = e?.message || 'Could not resend just now — try again shortly.';
		} finally {
			resendingVerif = false;
		}
	}

	function linkDiscord() {
		if (linkingDiscord) return;
		discordNote = null;
		const w = window.open(
			'/api/auth/discord/authorize?origin=' + encodeURIComponent(window.location.origin),
			'discord-link',
			'width=520,height=760'
		);
		if (!w) {
			discordNote = { type: 'err', text: 'Popup blocked — allow popups for this site and try again.' };
			return;
		}
		linkingDiscord = true;
		const timer = setTimeout(() => {
			if (linkingDiscord) {
				linkingDiscord = false;
				if (!discordNote) discordNote = { type: 'err', text: "Discord didn't finish connecting — try again." };
			}
		}, 90000);
		const handler = async (ev: MessageEvent) => {
			if (ev.origin !== window.location.origin) return;
			const d: any = ev.data || {};
			if (d.type === 'discord_verified') {
				window.removeEventListener('message', handler);
				clearTimeout(timer);
				try {
					const r = await api.participant.linkDiscord(d.token);
					discordNote = { type: 'ok', text: r.message || 'Discord linked.' };
					participant = await api.participant.me();
					hydrate(participant);
				} catch (e: any) {
					discordNote = { type: 'err', text: e?.message || 'Could not link that Discord account.' };
				} finally {
					linkingDiscord = false;
				}
			} else if (d.type === 'discord_error') {
				window.removeEventListener('message', handler);
				clearTimeout(timer);
				linkingDiscord = false;
				discordNote = {
					type: 'err',
					text:
						d.error === 'account_too_new'
							? 'That Discord account is too new to link.'
							: d.error === 'no_code' || d.error === 'access_denied'
								? 'Discord connection was cancelled.'
								: 'Discord connection failed — please retry.'
				};
			}
		};
		window.addEventListener('message', handler);
	}
</script>

<svelte:head><title>Profile · H7CTF Portal</title></svelte:head>

<div class="mb-6">
	<div class="eyebrow">Account</div>
	<h1 class="mt-1 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">Profile</h1>
	<p class="mt-1 text-sm text-foreground-muted">Your details and verified identity.</p>
</div>

{#if loading}
	<div class="space-y-5">
		<div class="skeleton h-24 w-full rounded-xl"></div>
		<div class="skeleton h-40 w-full rounded-xl"></div>
		<div class="skeleton h-64 w-full rounded-xl"></div>
	</div>
{:else if participant}
	<div class="fade-in space-y-5">
		<section class="surface p-6">
			<div class="flex items-center gap-4 sm:gap-5">
				<div class="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-2xl font-semibold text-primary ring-1 ring-inset ring-primary/20">
					{initial}
				</div>
				<div class="min-w-0">
					<div class="truncate text-lg font-semibold text-foreground">
						{name || participant.username || 'Participant'}
					</div>
					<div class="truncate text-sm text-foreground-muted">{participant.email}</div>
				</div>
			</div>
		</section>

		<section class="surface-plain p-6">
			<div class="eyebrow mb-4">Verified identity</div>
			<div class="divide-y divide-white/[0.06]">
				<div class="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 py-3">
					<span class="text-sm text-foreground-muted">Email</span>
					<span class="flex min-w-0 flex-wrap items-center justify-end gap-2.5">
						<span class="truncate text-sm font-medium text-foreground text-mono">{participant.email}</span>
						{#if participant.email_verified}
							<span class="chip-ok shrink-0"><span class="h-1.5 w-1.5 rounded-full bg-primary"></span> Verified</span>
						{:else}
							<span class="chip-warn shrink-0">Unverified</span>
							<button onclick={resendVerif} disabled={resendingVerif} class="btn-ghost btn-sm">
								{resendingVerif ? 'Sending…' : 'Resend'}
							</button>
						{/if}
					</span>
				</div>
				{#if verifNote}
					<p class="pb-2.5 text-right text-xs text-primary">{verifNote}</p>
				{/if}
				<div class="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 py-3">
					<span class="text-sm text-foreground-muted">Discord</span>
					<span class="flex min-w-0 flex-wrap items-center justify-end gap-2.5">
						{#if discordHandle}
							<span class="truncate text-sm font-medium text-foreground text-mono">@{discordHandle}</span>
							<span class="chip-ok shrink-0"><span class="h-1.5 w-1.5 rounded-full bg-primary"></span> Connected</span>
						{:else}
							<span class="text-sm text-foreground-muted">Not linked</span>
							<button onclick={linkDiscord} disabled={linkingDiscord} class="btn-secondary btn-sm">
								{linkingDiscord ? 'Connecting…' : 'Link Discord'}
							</button>
						{/if}
					</span>
				</div>
				{#if discordNote}
					<p class="pb-2.5 text-right text-xs {discordNote.type === 'ok' ? 'text-primary' : 'text-destructive'}">{discordNote.text}</p>
				{/if}
			</div>
			<p class="mt-4 text-xs leading-relaxed text-foreground-muted">
				Your email is your account identity. Linking Discord lets you sign in to the competition with it.
			</p>
		</section>

		<section class="surface-plain p-6">
			<div class="eyebrow mb-4">Your details</div>
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

			<div class="mt-6 flex flex-wrap items-center gap-3 border-t border-white/[0.06] pt-5">
				<button class="btn-accent" onclick={save} disabled={saving || !dirty}>
					{saving ? 'Saving…' : 'Save changes'}
				</button>
				{#if message}
					<span class="text-sm {message.type === 'success' ? 'text-primary' : 'text-destructive'}">
						{message.text}
					</span>
				{/if}
			</div>
		</section>
	</div>
{/if}
