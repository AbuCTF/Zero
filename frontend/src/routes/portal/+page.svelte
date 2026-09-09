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
	const discordHandle = $derived(extra.discord_username as string | undefined);
	const profileComplete = $derived(
		Boolean(extra.country && extra.organization && extra.participant_type)
	);

	// Full literal class names (Tailwind must see them in source to keep the component classes)
	const statusMap: Record<string, { cls: string; text: string }> = {
		draft: { cls: 'badge-muted', text: 'Draft' },
		registration: { cls: 'badge-primary', text: 'Registration open' },
		live: { cls: 'badge-success', text: 'Live' },
		ended: { cls: 'badge-warning', text: 'Ended' },
		archived: { cls: 'badge-muted', text: 'Archived' }
	};
	function statusBadge(status: string) {
		return statusMap[status] ?? { cls: 'badge-muted', text: status };
	}

	function timeUntil(dateStr?: string): string | null {
		if (!dateStr) return null;
		const diff = new Date(dateStr).getTime() - Date.now();
		if (diff <= 0) return null;
		const days = Math.floor(diff / 86_400_000);
		const hours = Math.floor((diff % 86_400_000) / 3_600_000);
		if (days >= 1) return `in ${days} day${days === 1 ? '' : 's'}`;
		if (hours >= 1) return `in ${hours} hour${hours === 1 ? '' : 's'}`;
		return 'soon';
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

<div class="page-header">
	<h1 class="text-display">
		Welcome{participant?.name ? `, ${participant.name.split(' ')[0]}` : ''}
	</h1>
	<p class="page-subtitle">Your registrations, profile, prizes, and certificates.</p>
</div>

{#if loading}
	<div class="space-y-4">
		<div class="skeleton h-24 w-full rounded-lg"></div>
		<div class="skeleton h-40 w-full rounded-lg"></div>
	</div>
{:else}
	<div class="space-y-6">
		<!-- Account status -->
		<div class="card">
			<div class="text-label mb-3">Account status</div>
			<div class="flex flex-wrap gap-2">
				<span class={participant?.email_verified ? 'badge-success' : 'badge-warning'}>
					{participant?.email_verified ? 'Email verified' : 'Email unverified'}
				</span>
				{#if discordHandle}
					<span class="badge-success">Discord @{discordHandle}</span>
				{:else}
					<span class="badge-muted">Discord not linked</span>
				{/if}
				{#if profileComplete}
					<span class="badge-success">Profile complete</span>
				{:else}
					<a href="/portal/profile" class="badge-warning hover:opacity-80">Complete your profile →</a>
				{/if}
			</div>
		</div>

		<!-- Events -->
		<div>
			<div class="text-label mb-3">Your events</div>
			{#if events.length === 0}
				<div class="card empty-state">
					<p class="empty-state-title">No events yet</p>
					<p class="empty-state-text">You're not registered for any events right now.</p>
				</div>
			{:else}
				<div class="space-y-3">
					{#each events as ev}
						{@const badge = statusBadge(ev.status)}
						{@const countdown = timeUntil(ev.event_start)}
						<div class="card-hover">
							<div class="flex flex-wrap items-start justify-between gap-3">
								<div class="min-w-0">
									<div class="flex flex-wrap items-center gap-2">
										<h2 class="text-title">{ev.name}</h2>
										<span class={badge.cls}>{badge.text}</span>
									</div>
									{#if ev.description}
										<p class="line-clamp-2 mt-1 text-sm text-foreground-muted">{ev.description}</p>
									{/if}
									<div class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-foreground-muted">
										<span>{eventDate(ev)}</span>
										{#if countdown}<span class="text-foreground">· starts {countdown}</span>{/if}
										{#if participant?.final_rank}
											<span>· Rank <span class="font-medium text-foreground">#{participant.final_rank}</span></span>
										{/if}
									</div>
								</div>
								<div class="flex shrink-0 gap-2">
									{#if discordUrl(ev)}
										<a href={discordUrl(ev)} target="_blank" rel="noopener" class="btn-secondary btn-sm">Discord</a>
									{/if}
									{#if ev.status === 'live' && ev.ctfd_url}
										<a href={ev.ctfd_url} target="_blank" rel="noopener" class="btn-primary btn-sm">Enter</a>
									{/if}
								</div>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Quick links -->
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
			<a href="/portal/profile" class="card-hover text-center">
				<div class="text-sm font-medium text-foreground">Profile</div>
				<div class="mt-0.5 text-xs text-foreground-muted">View &amp; edit</div>
			</a>
			<a href="/portal/prizes" class="card-hover text-center">
				<div class="text-sm font-medium text-foreground">Prizes</div>
				<div class="mt-0.5 text-xs text-foreground-muted">Claim rewards</div>
			</a>
			<a href="/portal/certificates" class="card-hover text-center">
				<div class="text-sm font-medium text-foreground">Certificates</div>
				<div class="mt-0.5 text-xs text-foreground-muted">Download</div>
			</a>
		</div>
	</div>
{/if}
