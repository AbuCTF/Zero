<script lang="ts">
	import { admin, type DashboardStats } from '$lib/api';
	import { formatNumber, formatPercent } from '$lib/utils';
	import { onMount } from 'svelte';

	let stats = $state<DashboardStats | null>(null);
	let loading = $state(true);
	let error = $state('');

	onMount(async () => {
		try {
			stats = await admin.stats();
		} catch (err) {
			error = 'Failed to load dashboard stats';
			console.error(err);
		} finally {
			loading = false;
		}
	});

	const statCards = $derived(
		stats
			? [
					{
						label: 'Total Events',
						value: stats.total_events,
						sub: `${stats.active_events} active`
					},
					{
						label: 'Participants',
						value: stats.total_participants,
						sub: `${stats.verified_participants} verified`
					},
					{
						label: 'Emails Sent',
						value: stats.total_emails_sent,
						sub: `${stats.emails_sent_today} today`
					},
					{
						label: 'Certificates',
						value: stats.total_certificates,
						sub: `${stats.certificates_downloaded} downloaded`
					},
					{
						label: 'Prizes',
						value: stats.total_prizes,
						sub: `${stats.prizes_claimed} claimed`
					},
					{
						label: 'Email Providers',
						value: stats.providers_active,
						sub: `${stats.providers_total} configured`
					}
			  ]
			: []
	);

	const emailCapacityPercent = $derived(
		stats && stats.daily_email_capacity > 0
			? Math.round((stats.daily_emails_used / stats.daily_email_capacity) * 100)
			: 0
	);
</script>

<div class="page-container fade-in">
	<div class="page-header">
		<h1 class="page-title">Dashboard</h1>
		<p class="page-subtitle">System overview</p>
	</div>

	{#if loading}
		<div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
			{#each [1, 2, 3, 4, 5, 6] as _}
				<div class="card">
					<div class="skeleton h-3 w-20 mb-3"></div>
					<div class="skeleton h-7 w-16 mb-2"></div>
					<div class="skeleton h-2.5 w-24"></div>
				</div>
			{/each}
		</div>
	{:else if error}
		<div class="card bg-destructive/10 border-destructive/30 text-destructive text-sm">
			{error}
		</div>
	{:else if stats}
		<!-- Stats Grid -->
		<div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-8">
			{#each statCards as card}
				<div class="card-hover">
					<p class="stat-label mb-2">{card.label}</p>
					<p class="stat-value">{formatNumber(card.value)}</p>
					<p class="text-xs text-foreground-muted mt-1">{card.sub}</p>
				</div>
			{/each}
		</div>

		<!-- Email Capacity -->
		<div class="card mb-8">
			<div class="flex items-center justify-between mb-4">
				<div>
					<p class="stat-label mb-1">Daily Email Capacity</p>
					<p class="text-sm text-foreground-muted">
						<span class="text-mono">{formatNumber(stats.daily_emails_used)}</span> / <span class="text-mono">{formatNumber(stats.daily_email_capacity)}</span> sent
					</p>
				</div>
				<div class="text-right">
					<span class="stat-value">{emailCapacityPercent}%</span>
				</div>
			</div>
			<div class="w-full h-1.5 bg-accent rounded-full overflow-hidden">
				<div
					class="h-full transition-all duration-500 ease-out {emailCapacityPercent > 80
						? 'bg-destructive'
						: emailCapacityPercent > 50
							? 'bg-warning'
							: 'bg-success'}"
					style="width: {emailCapacityPercent}%"
				></div>
			</div>
		</div>

		<!-- Quick Actions -->
		<div class="card">
			<p class="stat-label mb-4">Quick Actions</p>
			<div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
				<a href="/admin/events/new" class="btn-secondary justify-start">
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 4v16m8-8H4"></path>
					</svg>
					New Event
				</a>
				<a href="/admin/providers" class="btn-secondary justify-start">
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
					</svg>
					Providers
				</a>
				<a href="/admin/templates" class="btn-secondary justify-start">
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
					</svg>
					Templates
				</a>
				<a href="/admin/certificates" class="btn-secondary justify-start">
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"></path>
					</svg>
					Certificates
				</a>
			</div>
		</div>
	{/if}
</div>
