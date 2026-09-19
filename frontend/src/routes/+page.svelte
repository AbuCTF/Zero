<script lang="ts">
	import { events } from '$lib/api';
	import { formatDate } from '$lib/utils';

	let eventList = $state<Awaited<ReturnType<typeof events.list>>>({
		success: false,
		total: 0,
		page: 1,
		per_page: 20,
		pages: 0,
		events: []
	});

	let loading = $state(true);

	$effect(() => {
		loadEvents();
	});

	async function loadEvents() {
		try {
			eventList = await events.list();
		} catch (error) {
			console.error('Failed to load events:', error);
		} finally {
			loading = false;
		}
	}

	function getLiveEvents() {
		return eventList.events.filter(e => e.status === 'live');
	}

	function getUpcomingEvents() {
		return eventList.events.filter(e => e.status === 'upcoming' || e.status === 'registration');
	}

	function getPastEvents() {
		return eventList.events.filter(e => e.status === 'ended' || e.status === 'archived' || e.status === 'completed');
	}

	function getTotalParticipants() {
		return eventList.events.reduce((sum, e) => sum + (e.participant_count || 0), 0);
	}

	function getEventStatusLabel(event: typeof eventList.events[0]) {
		// Check if import-only
		if (event.is_import_only) {
			return { text: 'PARTICIPANT PORTAL', class: 'text-primary', dot: 'bg-primary' };
		}
		if (event.status === 'live') {
			return { text: 'LIVE NOW', class: 'text-success', dot: 'bg-success animate-pulse' };
		}
		if (event.status === 'registration') {
			return { text: 'REGISTRATION OPEN', class: 'text-warning', dot: 'bg-warning' };
		}
		if (event.status === 'upcoming') {
			return { text: 'COMING SOON', class: 'text-foreground-muted', dot: 'bg-foreground-muted' };
		}
		return { text: 'ENDED', class: 'text-foreground-muted', dot: 'bg-foreground-muted/50' };
	}

	function getRelativeTime(dateStr: string) {
		const date = new Date(dateStr);
		const now = new Date();
		const diff = date.getTime() - now.getTime();
		const days = Math.ceil(diff / (1000 * 60 * 60 * 24));

		if (days < 0) return `${Math.abs(days)}d ago`;
		if (days === 0) return 'Today';
		if (days === 1) return 'Tomorrow';
		if (days < 7) return `In ${days}d`;
		return `In ${Math.ceil(days / 7)}w`;
	}
</script>

<svelte:head>
	<title>ZeroPool</title>
	<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
</svelte:head>

<div class="min-h-screen bg-background font-sans">
	<!-- Navigation -->
	<nav class="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-xl border-b border-border/40">
		<div class="max-w-6xl mx-auto px-4 sm:px-6">
			<div class="flex items-center justify-between h-16">
				<a href="/" class="flex items-center group">
					<img src="/logo.png" alt="ZeroPool" class="h-9 w-auto group-hover:scale-105 transition-transform" />
				</a>
				<div class="flex items-center gap-1 sm:gap-3">
					<a href="/verify" class="px-2 sm:px-4 py-2 text-xs sm:text-sm font-medium text-foreground-muted hover:text-foreground transition-colors">
						Verify
					</a>
					<a href="/portal/login" class="ml-1 sm:ml-2 px-4 sm:px-5 py-2 rounded-full text-xs sm:text-sm font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-all">
						Portal
					</a>
				</div>
			</div>
		</div>
	</nav>

	<!-- Hero Section -->
	<section class="relative pt-32 pb-20 px-6 overflow-hidden">
		<!-- gold radial hero glow (W26 signature) -->
		<div
			class="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/4 w-[900px] max-w-[140vw] h-[560px]"
			style="background: radial-gradient(closest-side, hsl(var(--primary) / 0.18), transparent 72%);"
		></div>
		<div class="relative max-w-4xl mx-auto text-center">
			<h1 class="text-5xl sm:text-6xl lg:text-7xl font-bold leading-[1.05] tracking-tight mb-6">
				<span class="text-foreground">Pool Your</span><br/>
				<span class="bg-gradient-to-br from-primary via-primary to-primary/60 bg-clip-text text-transparent">Free Emails</span>
			</h1>
			<p class="text-lg sm:text-xl text-foreground-muted max-w-2xl mx-auto leading-relaxed mb-10">
				Aggregate free-tier SMTP services from Mailgun, Brevo, SendGrid &amp; Google App Passwords. Built for students and indie hackers who refuse to pay for basic email.
			</p>

			<div class="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
				<a href="/portal/login" class="group px-8 py-3.5 rounded-full text-base font-semibold bg-primary text-primary-foreground hover:bg-primary/90 hover:-translate-y-0.5 transition-all shadow-lg shadow-primary/25 hover:shadow-xl hover:shadow-primary/30 flex items-center gap-2">
					Open Portal
					<svg class="w-4 h-4 group-hover:translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"/>
					</svg>
				</a>
				<a href="/verify" class="px-8 py-3.5 rounded-full text-base font-semibold border border-primary/40 text-foreground hover:bg-primary hover:text-primary-foreground hover:border-primary transition-all">
					Verify Certificate
				</a>
			</div>

			<!-- Stats -->
			<div class="grid grid-cols-3 gap-6 max-w-lg mx-auto">
				<div class="text-center">
					<div class="text-3xl sm:text-4xl font-bold text-foreground tabular-nums">
						{#if loading}
							<span class="inline-block w-8 h-8 rounded bg-accent animate-pulse"></span>
						{:else}
							{eventList.total}
						{/if}
					</div>
					<div class="text-sm text-foreground-muted mt-1">Events</div>
				</div>
				<div class="text-center">
					<div class="text-3xl sm:text-4xl font-bold text-primary tabular-nums">
						{#if loading}
							<span class="inline-block w-8 h-8 rounded bg-accent animate-pulse"></span>
						{:else}
							{getLiveEvents().length}
						{/if}
					</div>
					<div class="text-sm text-foreground-muted mt-1">Live</div>
				</div>
				<div class="text-center">
					<div class="text-3xl sm:text-4xl font-bold text-foreground tabular-nums">
						{#if loading}
							<span class="inline-block w-12 h-8 rounded bg-accent animate-pulse"></span>
						{:else}
							{getTotalParticipants().toLocaleString()}
						{/if}
					</div>
					<div class="text-sm text-foreground-muted mt-1">Users</div>
				</div>
			</div>
		</div>
	</section>

	<!-- Events Section -->
	{#if !loading && eventList.events.length > 0}
		<section class="py-16 px-6 border-t border-border/40">
			<div class="max-w-5xl mx-auto">
				<div class="flex items-center justify-between mb-8">
					<h2 class="text-2xl font-bold text-foreground">Events</h2>
					{#if getLiveEvents().length > 0}
						<div class="flex items-center gap-2 text-sm text-success">
							<span class="w-2 h-2 rounded-full bg-success animate-pulse"></span>
							{getLiveEvents().length} live now
						</div>
					{/if}
				</div>

				<div class="space-y-3">
					{#each [...getLiveEvents(), ...getUpcomingEvents(), ...getPastEvents()] as event, i}
						{@const statusInfo = getEventStatusLabel(event)}
						<a
							href="/events/{event.slug}"
							class="event-row group flex items-center gap-6 p-5 rounded-xl bg-card border border-border/50 hover:border-primary/40 hover:bg-card/80 transition-all"
							style="animation-delay: {i * 50}ms"
						>
							<!-- Status Badge -->
							<div class="flex-shrink-0 w-36">
								<div class="flex items-center gap-2 text-xs font-medium tracking-wide {statusInfo.class}">
									<span class="w-1.5 h-1.5 rounded-full {statusInfo.dot}"></span>
									{statusInfo.text}
								</div>
							</div>

							<!-- Event Info -->
							<div class="flex-1 min-w-0">
								<h3 class="font-semibold text-foreground group-hover:text-primary transition-colors truncate">
									{event.name}
								</h3>
								{#if event.description}
									<p class="text-sm text-foreground-muted truncate mt-0.5">{event.description}</p>
								{/if}
							</div>

							<!-- Meta -->
							<div class="flex-shrink-0 flex items-center gap-6 text-sm text-foreground-muted">
								{#if event.event_start}
									<span class="hidden sm:block tabular-nums">{getRelativeTime(event.event_start)}</span>
								{/if}
								<div class="flex items-center gap-1.5 tabular-nums">
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
									</svg>
									{event.participant_count || 0}
								</div>
								<svg class="w-5 h-5 text-foreground-muted group-hover:text-primary group-hover:translate-x-0.5 transition-all" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
								</svg>
							</div>
						</a>
					{/each}
				</div>
			</div>
		</section>
	{/if}

	<!-- Loading State -->
	{#if loading}
		<section class="py-16 px-6">
			<div class="max-w-5xl mx-auto">
				<div class="space-y-3">
					{#each [1, 2, 3] as _}
						<div class="flex items-center gap-6 p-5 rounded-xl border border-border/50 bg-card">
							<div class="w-36">
								<div class="h-4 w-24 rounded bg-accent animate-pulse"></div>
							</div>
							<div class="flex-1">
								<div class="h-5 w-48 rounded bg-accent animate-pulse mb-2"></div>
								<div class="h-4 w-64 rounded bg-accent animate-pulse"></div>
							</div>
							<div class="flex items-center gap-6">
								<div class="h-4 w-12 rounded bg-accent animate-pulse"></div>
								<div class="h-4 w-8 rounded bg-accent animate-pulse"></div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</section>
	{/if}

	<!-- Empty State -->
	{#if !loading && eventList.events.length === 0}
		<section class="py-24 px-6">
			<div class="max-w-md mx-auto text-center">
				<div class="w-16 h-16 mx-auto mb-6 rounded-2xl bg-accent flex items-center justify-center">
					<svg class="w-8 h-8 text-foreground-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
					</svg>
				</div>
				<h2 class="text-xl font-semibold text-foreground mb-2">No Events Yet</h2>
				<p class="text-foreground-muted">There are no public events at the moment. Check back soon!</p>
			</div>
		</section>
	{/if}

</div>

<style>
	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.event-row {
		animation: fadeIn 0.4s ease-out forwards;
		opacity: 0;
	}
</style>
