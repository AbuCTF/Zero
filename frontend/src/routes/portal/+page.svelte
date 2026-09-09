<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type Participant, type Event } from '$lib/api';
	import { formatDate } from '$lib/utils';

	let participant = $state<Participant | null>(null);
	let events = $state<Event[]>([]);
	let loading = $state(true);

	onMount(async () => {
		try {
			participant = await api.participant.me();
			events = await api.participant.events();
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	});

	const extra = $derived(participant?.extra_data ?? {});
	const firstName = $derived((participant?.name || '').trim().split(' ')[0] || 'there');
	const initial = $derived((participant?.name || participant?.email || '?').charAt(0).toUpperCase());
	const discordHandle = $derived(extra.discord_username as string | undefined);
	const profileComplete = $derived(
		Boolean(extra.country && extra.organization && extra.participant_type)
	);

	const statusMap: Record<string, { cls: string; text: string }> = {
		draft: { cls: 'chip-muted', text: 'Draft' },
		registration: { cls: 'chip-ok', text: 'Registration open' },
		live: { cls: 'chip-ok', text: 'Live now' },
		ended: { cls: 'chip-warn', text: 'Ended' },
		archived: { cls: 'chip-muted', text: 'Archived' }
	};
	function statusBadge(status: string) {
		return statusMap[status] ?? { cls: 'chip-muted', text: status };
	}
	function countdown(dateStr?: string): { value: number; unit: string } | null {
		if (!dateStr) return null;
		const diff = new Date(dateStr).getTime() - Date.now();
		if (diff <= 0) return null;
		const days = Math.floor(diff / 86_400_000);
		if (days >= 1) return { value: days, unit: days === 1 ? 'day' : 'days' };
		const hours = Math.max(1, Math.floor(diff / 3_600_000));
		return { value: hours, unit: hours === 1 ? 'hour' : 'hours' };
	}
	function eventDate(ev: Event): string {
		if (ev.event_start) return formatDate(ev.event_start);
		if (ev.registration_end) return `Registration closes ${formatDate(ev.registration_end)}`;
		return 'Date to be announced';
	}
	function discordUrl(ev: Event): string | undefined {
		return ev.settings?.discord_url as string | undefined;
	}
</script>

<svelte:head><title>Dashboard · H7CTF Portal</title></svelte:head>

{#snippet statusChip(kind: 'ok' | 'warn' | 'muted', label: string)}
	<span class={kind === 'ok' ? 'chip-ok' : kind === 'warn' ? 'chip-warn' : 'chip-muted'}>
		{#if kind !== 'muted'}
			<span class="h-1.5 w-1.5 rounded-full {kind === 'ok' ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
		{/if}
		{label}
	</span>
{/snippet}

{#snippet tile(href: string, title: string, sub: string, path: string)}
	<a href={href} class="surface-plain surface-link group flex items-center gap-3 p-4">
		<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/[0.04] text-foreground-muted transition-colors group-hover:bg-emerald-500/10 group-hover:text-emerald-400">
			<svg class="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.7"><path stroke-linecap="round" stroke-linejoin="round" d={path} /></svg>
		</span>
		<span class="min-w-0">
			<span class="block text-sm font-medium text-foreground">{title}</span>
			<span class="block text-xs text-foreground-muted">{sub}</span>
		</span>
	</a>
{/snippet}

{#if loading}
	<div class="space-y-5">
		<div class="skeleton h-32 w-full rounded-xl"></div>
		<div class="skeleton h-48 w-full rounded-xl"></div>
	</div>
{:else}
	<div class="fade-in space-y-5">
		<!-- Hero / command center -->
		<section class="surface p-6 sm:p-7">
			<div class="accent-bar"></div>
			<div class="flex items-center gap-4 sm:gap-5">
				<div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-emerald-500/10 text-xl font-semibold text-emerald-400 ring-1 ring-inset ring-emerald-500/20 sm:h-16 sm:w-16">
					{initial}
				</div>
				<div class="min-w-0">
					<div class="eyebrow">Participant</div>
					<h1 class="mt-1 truncate text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
						Welcome, {firstName}
					</h1>
					<div class="mt-0.5 truncate text-sm text-foreground-muted">{participant?.email}</div>
				</div>
			</div>
			<div class="mt-5 flex flex-wrap gap-2">
				{@render statusChip(participant?.email_verified ? 'ok' : 'warn', participant?.email_verified ? 'Email verified' : 'Email unverified')}
				{#if discordHandle}
					{@render statusChip('ok', `@${discordHandle}`)}
				{:else}
					{@render statusChip('muted', 'Discord not linked')}
				{/if}
				{#if profileComplete}
					{@render statusChip('ok', 'Profile complete')}
				{:else}
					<a href="/portal/profile" class="chip-warn transition-opacity hover:opacity-80">Complete profile →</a>
				{/if}
			</div>
		</section>

		<!-- Events -->
		<div>
			<div class="eyebrow mb-3">Your events</div>
			{#if events.length === 0}
				<div class="surface-plain empty-state">
					<p class="empty-state-title">No events yet</p>
					<p class="empty-state-text">You're not registered for any events right now.</p>
				</div>
			{:else}
				<div class="space-y-4">
					{#each events as ev}
						{@const badge = statusBadge(ev.status)}
						{@const cd = countdown(ev.event_start)}
						<section class="surface surface-link p-6">
							<div class="accent-bar"></div>
							<div class="flex flex-wrap items-start justify-between gap-5">
								<div class="min-w-0 flex-1">
									<div class="flex flex-wrap items-center gap-2.5">
										<h2 class="text-xl font-semibold tracking-tight text-foreground">{ev.name}</h2>
										<span class={badge.cls}>{badge.text}</span>
									</div>
									{#if ev.description}
										<p class="line-clamp-2 mt-2 max-w-xl text-sm leading-relaxed text-foreground-muted">{ev.description}</p>
									{/if}
									<div class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-sm text-foreground-muted">
										<span class="inline-flex items-center gap-1.5">
											<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.7"><path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3M4 11h16M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
											{eventDate(ev)}
										</span>
										{#if participant?.final_rank}
											<span>Rank <span class="font-medium text-foreground">#{participant.final_rank}</span></span>
										{/if}
									</div>
								</div>
								{#if cd}
									<div class="shrink-0 text-right">
										<div class="font-mono text-4xl font-semibold leading-none text-emerald-400 sm:text-5xl" style="font-variant-numeric: tabular-nums">{cd.value}</div>
										<div class="eyebrow mt-1.5">{cd.unit} to go</div>
									</div>
								{/if}
							</div>
							{#if discordUrl(ev) || (ev.status === 'live' && ev.ctfd_url)}
								<div class="mt-5 flex flex-wrap gap-2.5 border-t border-white/[0.06] pt-5">
									{#if ev.status === 'live' && ev.ctfd_url}
										<a href={ev.ctfd_url} target="_blank" rel="noopener" class="btn-accent btn-sm">Enter competition</a>
									{/if}
									{#if discordUrl(ev)}
										<a href={discordUrl(ev)} target="_blank" rel="noopener" class="btn-secondary btn-sm">Join Discord</a>
									{/if}
								</div>
							{/if}
						</section>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Quick actions -->
		<div>
			<div class="eyebrow mb-3">Quick actions</div>
			<div class="grid gap-3 sm:grid-cols-3">
				{@render tile('/portal/profile', 'Profile', 'View & edit', 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z')}
				{@render tile('/portal/prizes', 'Prizes', 'Claim rewards', 'M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7')}
				{@render tile('/portal/certificates', 'Certificates', 'Download', 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z')}
			</div>
		</div>
	</div>
{/if}
