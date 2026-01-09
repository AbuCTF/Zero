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

    function getStatusBadge(status: string): { class: string; text: string } {
        switch (status) {
            case 'registration': return { class: 'badge-primary', text: 'Registering' };
            case 'active': return { class: 'badge-success', text: 'Live' };
            case 'completed': return { class: 'badge-warning', text: 'Ended' };
            case 'finalized': return { class: 'badge-secondary', text: 'Finalized' };
            default: return { class: 'badge-secondary', text: status };
        }
    }
</script>

<svelte:head>
    <title>Dashboard - Participant Portal</title>
</svelte:head>

<div class="space-y-6">
    <div>
        <h1 class="text-2xl font-semibold">Welcome, {participant?.name || 'Participant'}</h1>
        <p class="text-sm text-muted-foreground mt-1">
            View your event participations, prizes, and certificates
        </p>
    </div>

    {#if loading}
        <div class="card p-12 text-center">
            <div class="animate-pulse text-muted-foreground">Loading...</div>
        </div>
    {:else}
        <!-- Quick Stats -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="card p-4">
                <div class="text-sm text-muted-foreground">Events Participated</div>
                <div class="text-2xl font-semibold mt-1">{events.length}</div>
            </div>
            <div class="card p-4">
                <div class="text-sm text-muted-foreground">Prizes Won</div>
                <div class="text-2xl font-semibold mt-1">
                    <a href="/portal/prizes" class="hover:text-primary">View Prizes</a>
                </div>
            </div>
            <div class="card p-4">
                <div class="text-sm text-muted-foreground">Certificates</div>
                <div class="text-2xl font-semibold mt-1">
                    <a href="/portal/certificates" class="hover:text-primary">View All</a>
                </div>
            </div>
        </div>

        <!-- Events -->
        <div class="card">
            <div class="px-6 py-4 border-b border-border">
                <h2 class="font-medium">Your Events</h2>
            </div>
            
            {#if events.length === 0}
                <div class="p-12 text-center text-muted-foreground">
                    You haven't participated in any events yet.
                </div>
            {:else}
                <div class="divide-y divide-border">
                    {#each events as event}
                        <div class="px-6 py-4 flex items-center justify-between">
                            <div>
                                <div class="flex items-center gap-2">
                                    <span class="font-medium">{event.name}</span>
                                    <span class={`badge ${getStatusBadge(event.status).class}`}>
                                        {getStatusBadge(event.status).text}
                                    </span>
                                </div>
                                <div class="text-sm text-muted-foreground mt-1">
                                    {event.start_date ? formatDate(event.start_date) : 'Date TBD'}
                                </div>
                            </div>
                            <div class="text-right">
                                {#if event.final_rank}
                                    <div class="text-sm">
                                        Rank: <span class="font-medium">#{event.final_rank}</span>
                                    </div>
                                {:else if participant?.final_rank}
                                    <div class="text-sm">
                                        Rank: <span class="font-medium">#{participant.final_rank}</span>
                                    </div>
                                {/if}
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        </div>
    {/if}
</div>

<style>
    .badge-success {
        background-color: hsl(142 76% 36% / 0.15);
        color: hsl(142 76% 36%);
    }
    .badge-warning {
        background-color: hsl(45 93% 47% / 0.15);
        color: hsl(45 93% 47%);
    }
</style>
