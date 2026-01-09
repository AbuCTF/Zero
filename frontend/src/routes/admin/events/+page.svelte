<script lang="ts">
	import { admin, type Event } from '$lib/api';
	import { formatDate, getEventStatusColor, capitalize } from '$lib/utils';
	import { onMount } from 'svelte';

	let events = $state<Event[]>([]);
	let loading = $state(true);
	let total = $state(0);
	let page = $state(1);
	let pages = $state(0);
	let statusFilter = $state('');

	onMount(() => {
		loadEvents();
	});

	async function loadEvents() {
		loading = true;
		try {
			const response = await admin.events.list(page, statusFilter || undefined);
			events = response.events;
			total = response.total;
			pages = response.pages;
		} catch (err) {
			console.error('Failed to load events:', err);
		} finally {
			loading = false;
		}
	}

	function handleFilterChange() {
		page = 1;
		loadEvents();
	}
</script>

<div class="p-6 lg:p-8">
	<div class="flex items-center justify-between mb-8">
		<div>
			<h1 class="text-2xl font-semibold text-foreground">Events</h1>
			<p class="text-sm text-foreground-muted mt-1">
				Manage your CTF events
			</p>
		</div>
		<a href="/admin/events/new" class="btn-primary">
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
			</svg>
			New Event
		</a>
	</div>

	<!-- Filters -->
	<div class="card mb-6">
		<div class="flex flex-wrap gap-4">
			<div>
				<label for="status" class="block text-sm font-medium text-foreground mb-1.5">
					Status
				</label>
				<select
					id="status"
					bind:value={statusFilter}
					onchange={handleFilterChange}
					class="input w-40"
				>
					<option value="">All</option>
					<option value="draft">Draft</option>
					<option value="registration">Registration</option>
					<option value="live">Live</option>
					<option value="completed">Completed</option>
					<option value="archived">Archived</option>
				</select>
			</div>
		</div>
	</div>

	<!-- Events Table -->
	{#if loading}
		<div class="table-container">
			<table class="table">
				<thead>
					<tr>
						<th>Name</th>
						<th>Status</th>
						<th>Participants</th>
						<th>Event Date</th>
						<th>Created</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					{#each [1, 2, 3, 4, 5] as _}
						<tr>
							<td><div class="skeleton h-4 w-32"></div></td>
							<td><div class="skeleton h-5 w-20"></div></td>
							<td><div class="skeleton h-4 w-16"></div></td>
							<td><div class="skeleton h-4 w-24"></div></td>
							<td><div class="skeleton h-4 w-24"></div></td>
							<td><div class="skeleton h-4 w-8"></div></td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else if events.length === 0}
		<div class="card text-center py-12">
			<svg class="w-12 h-12 text-foreground-muted mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
			</svg>
			<p class="text-foreground-muted mb-4">No events found</p>
			<a href="/admin/events/new" class="btn-primary">
				Create your first event
			</a>
		</div>
	{:else}
		<div class="table-container">
			<table class="table">
				<thead>
					<tr>
						<th>Name</th>
						<th>Status</th>
						<th>Participants</th>
						<th>Event Date</th>
						<th>Created</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					{#each events as event}
						<tr>
							<td>
								<a href="/admin/events/{event.id}" class="font-medium text-foreground hover:underline">
									{event.name}
								</a>
								<p class="text-xs text-foreground-muted">{event.slug}</p>
							</td>
							<td>
								<span class={getEventStatusColor(event.status)}>
									{capitalize(event.status)}
								</span>
							</td>
							<td>
								<span class="text-foreground">{event.participant_count ?? 0}</span>
								<span class="text-foreground-muted"> / {event.verified_count ?? 0} verified</span>
							</td>
							<td class="text-foreground-muted">
								{event.event_start ? formatDate(event.event_start) : '-'}
							</td>
							<td class="text-foreground-muted">
								{formatDate(event.created_at)}
							</td>
							<td>
								<a
									href="/admin/events/{event.id}"
									class="text-foreground-muted hover:text-foreground transition-colors"
								>
									<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
									</svg>
								</a>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<!-- Pagination -->
		{#if pages > 1}
			<div class="flex items-center justify-between mt-4">
				<p class="text-sm text-foreground-muted">
					Showing {events.length} of {total} events
				</p>
				<div class="flex gap-2">
					<button
						class="btn-secondary text-sm"
						disabled={page === 1}
						onclick={() => { page--; loadEvents(); }}
					>
						Previous
					</button>
					<button
						class="btn-secondary text-sm"
						disabled={page === pages}
						onclick={() => { page++; loadEvents(); }}
					>
						Next
					</button>
				</div>
			</div>
		{/if}
	{/if}
</div>
