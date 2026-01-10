<script lang="ts">
    import { onMount } from 'svelte';
    import { page } from '$app/stores';
    import { goto } from '$app/navigation';
    import { api, type Event, type Participant } from '$lib/api';
    import { formatDate, formatNumber } from '$lib/utils';

    const eventId = $derived($page.params.id);
    
    let event = $state<Event | null>(null);
    let participants = $state<Participant[]>([]);
    let loading = $state(true);
    let error = $state('');
    let activeTab = $state<'overview' | 'participants' | 'settings'>('overview');
    
    let syncing = $state(false);
    let finalizing = $state(false);
    let saving = $state(false);
    
    let showImportModal = $state(false);
    let importFile = $state<File | null>(null);
    let importing = $state(false);
    let updateExisting = $state(true);
    let importResult = $state<{ imported: number; updated: number; skipped: number; errors: any[] } | null>(null);

    let editForm = $state({
        name: '',
        slug: '',
        description: '',
        start_date: '',
        end_date: '',
        registration_open: '',
        registration_close: '',
        max_participants: null as number | null,
        team_mode: false,
        min_team_size: 1,
        max_team_size: 4,
        ctfd_url: '',
        ctfd_api_key: ''
    });

    onMount(async () => {
        await loadEvent();
    });

    async function loadEvent() {
        loading = true;
        error = '';
        try {
            event = await api.admin.events.get(eventId);
            const participantResponse = await api.admin.participants.list(eventId);
            participants = participantResponse.participants || [];
            
            // Populate edit form
            editForm = {
                name: event.name,
                slug: event.slug,
                description: event.description || '',
                start_date: event.start_date?.slice(0, 16) || '',
                end_date: event.end_date?.slice(0, 16) || '',
                registration_open: event.registration_open?.slice(0, 16) || '',
                registration_close: event.registration_close?.slice(0, 16) || '',
                max_participants: event.max_participants,
                team_mode: event.team_mode,
                min_team_size: event.min_team_size || 1,
                max_team_size: event.max_team_size || 4,
                ctfd_url: event.ctfd_url || '',
                ctfd_api_key: event.ctfd_api_key || ''
            };
        } catch (e: any) {
            error = e.message || 'Failed to load event';
        } finally {
            loading = false;
        }
    }

    async function saveSettings() {
        saving = true;
        error = '';
        try {
            await api.admin.events.update(eventId, editForm);
            await loadEvent();
        } catch (e: any) {
            error = e.message || 'Failed to save settings';
        } finally {
            saving = false;
        }
    }

    async function syncCTFd() {
        if (!event?.ctfd_url) {
            error = 'Please configure CTFd URL first';
            return;
        }
        
        syncing = true;
        error = '';
        try {
            await api.admin.events.syncCTFd(eventId);
            await loadEvent();
        } catch (e: any) {
            error = e.message || 'Failed to sync with CTFd';
        } finally {
            syncing = false;
        }
    }

    async function finalizeEvent() {
        if (!confirm('Finalize this event? This will lock results and enable prize distribution.')) return;
        
        finalizing = true;
        error = '';
        try {
            await api.admin.events.finalize(eventId);
            await loadEvent();
        } catch (e: any) {
            error = e.message || 'Failed to finalize event';
        } finally {
            finalizing = false;
        }
    }

    async function handleImport() {
        if (!importFile) return;
        
        importing = true;
        error = '';
        importResult = null;
        
        try {
            const formData = new FormData();
            formData.append('file', importFile);
            
            const url = `/api/admin/events/${eventId}/participants/import?update_existing=${updateExisting}`;
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                credentials: 'include'
            });
            
            if (!response.ok) {
                throw new Error('Import failed');
            }
            
            importResult = await response.json();
            await loadEvent();
        } catch (e: any) {
            error = e.message || 'Failed to import participants';
        } finally {
            importing = false;
        }
    }

    async function deleteEvent() {
        if (!confirm(`Delete "${event?.name}"? This action cannot be undone and will delete all participants, prizes, and certificates.`)) return;
        
        try {
            await api.admin.events.delete(eventId);
            goto('/admin/events');
        } catch (e: any) {
            error = e.message || 'Failed to delete event';
        }
    }

    async function deleteParticipant(id: string) {
        if (!confirm('Remove this participant from the event?')) return;
        
        try {
            await api.admin.participants.delete(eventId, id);
            participants = participants.filter(p => p.id !== id);
        } catch (e: any) {
            error = e.message || 'Failed to delete participant';
        }
    }

    async function verifyParticipant(id: string) {
        try {
            await api.admin.participants.verify(eventId, id);
            await loadEvent();
        } catch (e: any) {
            error = e.message || 'Failed to verify participant';
        }
    }

    function getStatusBadge(status: string): string {
        switch (status) {
            case 'draft': return 'badge-secondary';
            case 'registration': return 'badge-primary';
            case 'active': return 'badge-success';
            case 'completed': return 'badge-warning';
            case 'finalized': return 'badge-secondary';
            default: return 'badge-secondary';
        }
    }
</script>

<svelte:head>
    <title>{event?.name || 'Event'} - ZeroPool Admin</title>
</svelte:head>

<div class="p-6 lg:p-8">
{#if loading}
    <div class="p-12 text-center">
        <div class="animate-pulse text-muted-foreground">Loading event...</div>
    </div>
{:else if !event}
    <div class="p-12 text-center">
        <div class="text-muted-foreground mb-4">Event not found</div>
        <a href="/admin/events" class="btn btn-primary">Back to Events</a>
    </div>
{:else}
    <div class="space-y-6">
        <!-- Header -->
        <div class="flex items-start justify-between">
            <div>
                <div class="flex items-center gap-3 mb-1">
                    <a href="/admin/events" class="text-muted-foreground hover:text-foreground transition-colors">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                        </svg>
                    </a>
                    <h1 class="text-2xl font-semibold">{event.name}</h1>
                    <span class={`badge ${getStatusBadge(event.status)}`}>
                        {event.status}
                    </span>
                </div>
                <p class="text-sm text-muted-foreground">
                    {event.slug} | {participants.length} participants
                </p>
            </div>
            <div class="flex items-center gap-2">
                {#if event.ctfd_url && event.status !== 'finalized'}
                    <button 
                        onclick={syncCTFd}
                        disabled={syncing}
                        class="btn btn-secondary"
                    >
                        {syncing ? 'Syncing...' : 'Sync CTFd'}
                    </button>
                {/if}
                {#if event.status === 'completed'}
                    <button 
                        onclick={finalizeEvent}
                        disabled={finalizing}
                        class="btn btn-primary"
                    >
                        {finalizing ? 'Finalizing...' : 'Finalize Event'}
                    </button>
                {/if}
                <button 
                    onclick={deleteEvent}
                    class="btn btn-ghost text-destructive hover:bg-destructive/10"
                >
                    Delete
                </button>
            </div>
        </div>

        {#if error}
            <div class="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
                {error}
            </div>
        {/if}

        <!-- Tabs -->
        <div class="border-b border-border">
            <nav class="flex gap-6">
                <button 
                    onclick={() => activeTab = 'overview'}
                    class="py-3 text-sm font-medium border-b-2 transition-colors {activeTab === 'overview' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}"
                >
                    Overview
                </button>
                <button 
                    onclick={() => activeTab = 'participants'}
                    class="py-3 text-sm font-medium border-b-2 transition-colors {activeTab === 'participants' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}"
                >
                    Participants ({participants.length})
                </button>
                <button 
                    onclick={() => activeTab = 'settings'}
                    class="py-3 text-sm font-medium border-b-2 transition-colors {activeTab === 'settings' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}"
                >
                    Settings
                </button>
            </nav>
        </div>

        <!-- Tab Content -->
        {#if activeTab === 'overview'}
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="card p-4 group hover:border-border-hover transition-colors">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="text-xs font-medium text-muted-foreground uppercase tracking-wide">Participants</div>
                            <div class="text-2xl font-semibold mt-1 tracking-tight">{formatNumber(participants.length)}</div>
                        </div>
                        <div class="w-10 h-10 rounded-lg bg-accent/50 flex items-center justify-center text-muted-foreground group-hover:bg-accent transition-colors">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                        </div>
                    </div>
                </div>
                <div class="card p-4 group hover:border-border-hover transition-colors">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="text-xs font-medium text-muted-foreground uppercase tracking-wide">Verified</div>
                            <div class="text-2xl font-semibold mt-1 tracking-tight">
                                {formatNumber(participants.filter(p => p.email_verified).length)}
                            </div>
                        </div>
                        <div class="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center text-success">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        </div>
                    </div>
                </div>
                <div class="card p-4 group hover:border-border-hover transition-colors">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="text-xs font-medium text-muted-foreground uppercase tracking-wide">Teams</div>
                            <div class="text-2xl font-semibold mt-1 tracking-tight">
                                {formatNumber(new Set(participants.filter(p => p.team_id).map(p => p.team_id)).size)}
                            </div>
                        </div>
                        <div class="w-10 h-10 rounded-lg bg-accent/50 flex items-center justify-center text-muted-foreground group-hover:bg-accent transition-colors">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>
                        </div>
                    </div>
                </div>
                <div class="card p-4 group hover:border-border-hover transition-colors">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="text-xs font-medium text-muted-foreground uppercase tracking-wide">With Results</div>
                            <div class="text-2xl font-semibold mt-1 tracking-tight">
                                {formatNumber(participants.filter(p => p.final_rank).length)}
                            </div>
                        </div>
                        <div class="w-10 h-10 rounded-lg bg-accent/50 flex items-center justify-center text-muted-foreground group-hover:bg-accent transition-colors">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                        </div>
                    </div>
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div class="card">
                    <h3 class="font-medium mb-4 flex items-center gap-2">
                        <svg class="w-4 h-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                        Event Timeline
                    </h3>
                    <div class="space-y-3 text-sm">
                        <div class="flex justify-between items-center py-2 border-b border-border/50">
                            <span class="text-muted-foreground">Registration Opens</span>
                            <span class="font-medium">{event.registration_open ? formatDate(event.registration_open) : '—'}</span>
                        </div>
                        <div class="flex justify-between items-center py-2 border-b border-border/50">
                            <span class="text-muted-foreground">Registration Closes</span>
                            <span class="font-medium">{event.registration_close ? formatDate(event.registration_close) : '—'}</span>
                        </div>
                        <div class="flex justify-between items-center py-2 border-b border-border/50">
                            <span class="text-muted-foreground">Event Starts</span>
                            <span class="font-medium">{event.start_date ? formatDate(event.start_date) : '—'}</span>
                        </div>
                        <div class="flex justify-between items-center py-2">
                            <span class="text-muted-foreground">Event Ends</span>
                            <span class="font-medium">{event.end_date ? formatDate(event.end_date) : '—'}</span>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <h3 class="font-medium mb-4 flex items-center gap-2">
                        <svg class="w-4 h-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
                        CTFd Integration
                    </h3>
                    {#if event.ctfd_url}
                        <div class="space-y-3 text-sm">
                            <div class="flex justify-between items-center py-2 border-b border-border/50">
                                <span class="text-muted-foreground">Platform URL</span>
                                <a href={event.ctfd_url} target="_blank" class="text-foreground hover:text-primary transition-colors font-medium truncate max-w-[200px]">
                                    {event.ctfd_url.replace(/^https?:\/\//, '')}
                                </a>
                            </div>
                            <div class="flex justify-between items-center py-2">
                                <span class="text-muted-foreground">Last Sync</span>
                                <span class="font-medium">{event.ctfd_last_sync ? formatDate(event.ctfd_last_sync) : 'Never'}</span>
                            </div>
                        </div>
                    {:else}
                        <div class="flex items-center gap-3 p-4 bg-accent/30 rounded-lg">
                            <svg class="w-5 h-5 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            <p class="text-sm text-muted-foreground">
                                No CTFd instance configured. Set it up in Settings.
                            </p>
                        </div>
                    {/if}
                </div>
            </div>

        {:else if activeTab === 'participants'}
            <div class="flex items-center justify-between mb-4">
                <div class="text-sm text-muted-foreground">
                    {participants.length} participant{participants.length !== 1 ? 's' : ''} registered
                </div>
                <button onclick={() => showImportModal = true} class="btn btn-secondary gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
                    Import
                </button>
            </div>

            {#if participants.length === 0}
                <div class="card p-12 text-center">
                    <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-accent/50 flex items-center justify-center">
                        <svg class="w-8 h-8 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                    </div>
                    <div class="text-foreground font-medium mb-1">No participants yet</div>
                    <p class="text-sm text-muted-foreground mb-4">Import a list of participants to get started</p>
                    <button onclick={() => showImportModal = true} class="btn btn-primary">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
                        Import Participants
                    </button>
                </div>
            {:else}
                <div class="card overflow-hidden">
                    <table class="w-full">
                        <thead class="bg-muted/50">
                            <tr>
                                <th class="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">
                                    Name
                                </th>
                                <th class="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">
                                    Email
                                </th>
                                <th class="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">
                                    Team
                                </th>
                                <th class="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">
                                    Rank
                                </th>
                                <th class="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">
                                    Status
                                </th>
                                <th class="text-right text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">
                                    Actions
                                </th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-border">
                            {#each participants as participant}
                                <tr class="hover:bg-muted/30">
                                    <td class="px-4 py-3">
                                        <div class="font-medium">{participant.name}</div>
                                    </td>
                                    <td class="px-4 py-3 text-sm text-muted-foreground">
                                        {participant.email}
                                    </td>
                                    <td class="px-4 py-3 text-sm">
                                        {participant.team_name || '-'}
                                    </td>
                                    <td class="px-4 py-3 text-sm">
                                        {participant.final_rank || '-'}
                                    </td>
                                    <td class="px-4 py-3">
                                        {#if participant.email_verified}
                                            <span class="badge badge-success">Verified</span>
                                        {:else}
                                            <span class="badge badge-secondary">Unverified</span>
                                        {/if}
                                    </td>
                                    <td class="px-4 py-3 text-right">
                                        <div class="flex items-center justify-end gap-1">
                                            {#if !participant.email_verified}
                                                <button 
                                                    onclick={() => verifyParticipant(participant.id)}
                                                    class="btn btn-ghost btn-sm"
                                                    title="Mark as verified"
                                                >
                                                    Verify
                                                </button>
                                            {/if}
                                            <button 
                                                onclick={() => deleteParticipant(participant.id)}
                                                class="btn btn-ghost btn-sm text-destructive"
                                            >
                                                Remove
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                </div>
            {/if}

        {:else if activeTab === 'settings'}
            <form onsubmit={(e) => { e.preventDefault(); saveSettings(); }} class="space-y-6 max-w-2xl">
                <div class="card p-6 space-y-4">
                    <h3 class="font-medium">Basic Information</h3>
                    
                    <div>
                        <label for="name" class="block text-sm font-medium mb-1.5">Event Name</label>
                        <input type="text" id="name" bind:value={editForm.name} class="input" required />
                    </div>

                    <div>
                        <label for="slug" class="block text-sm font-medium mb-1.5">URL Slug</label>
                        <input type="text" id="slug" bind:value={editForm.slug} class="input" required />
                    </div>

                    <div>
                        <label for="description" class="block text-sm font-medium mb-1.5">Description</label>
                        <textarea id="description" bind:value={editForm.description} class="input" rows="3"></textarea>
                    </div>
                </div>

                <div class="card p-6 space-y-4">
                    <h3 class="font-medium">Schedule</h3>
                    
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label for="reg-open" class="block text-sm font-medium mb-1.5">Registration Opens</label>
                            <input type="datetime-local" id="reg-open" bind:value={editForm.registration_open} class="input" />
                        </div>
                        <div>
                            <label for="reg-close" class="block text-sm font-medium mb-1.5">Registration Closes</label>
                            <input type="datetime-local" id="reg-close" bind:value={editForm.registration_close} class="input" />
                        </div>
                        <div>
                            <label for="start" class="block text-sm font-medium mb-1.5">Event Starts</label>
                            <input type="datetime-local" id="start" bind:value={editForm.start_date} class="input" />
                        </div>
                        <div>
                            <label for="end" class="block text-sm font-medium mb-1.5">Event Ends</label>
                            <input type="datetime-local" id="end" bind:value={editForm.end_date} class="input" />
                        </div>
                    </div>
                </div>

                <div class="card p-6 space-y-4">
                    <h3 class="font-medium">Team Settings</h3>
                    
                    <label class="flex items-center gap-3">
                        <input type="checkbox" bind:checked={editForm.team_mode} class="rounded" />
                        <span class="text-sm">Enable team mode</span>
                    </label>

                    {#if editForm.team_mode}
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label for="min-team" class="block text-sm font-medium mb-1.5">Min Team Size</label>
                                <input type="number" id="min-team" bind:value={editForm.min_team_size} class="input" min="1" />
                            </div>
                            <div>
                                <label for="max-team" class="block text-sm font-medium mb-1.5">Max Team Size</label>
                                <input type="number" id="max-team" bind:value={editForm.max_team_size} class="input" min="1" />
                            </div>
                        </div>
                    {/if}

                    <div>
                        <label for="max-participants" class="block text-sm font-medium mb-1.5">Max Participants</label>
                        <input type="number" id="max-participants" bind:value={editForm.max_participants} class="input" placeholder="Unlimited" />
                    </div>
                </div>

                <div class="card p-6 space-y-4">
                    <h3 class="font-medium">CTFd Integration</h3>
                    
                    <div>
                        <label for="ctfd-url" class="block text-sm font-medium mb-1.5">CTFd URL</label>
                        <input type="url" id="ctfd-url" bind:value={editForm.ctfd_url} class="input" placeholder="https://ctf.example.com" />
                    </div>

                    <div>
                        <label for="ctfd-key" class="block text-sm font-medium mb-1.5">CTFd API Key</label>
                        <input type="password" id="ctfd-key" bind:value={editForm.ctfd_api_key} class="input" placeholder="ctfd_xxx..." />
                        <p class="text-xs text-muted-foreground mt-1">
                            Generate from CTFd Admin > Config > Access Tokens
                        </p>
                    </div>
                </div>

                <div class="flex justify-end">
                    <button type="submit" disabled={saving} class="btn btn-primary">
                        {saving ? 'Saving...' : 'Save Settings'}
                    </button>
                </div>
            </form>
        {/if}
    </div>
{/if}

<!-- Import Modal -->
{#if showImportModal}
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div class="bg-card rounded-xl shadow-xl w-full max-w-md">
            <div class="px-6 py-4 border-b border-border flex items-center justify-between">
                <h2 class="text-lg font-semibold">Import Participants</h2>
                <button onclick={() => { showImportModal = false; importResult = null; }} class="btn btn-ghost btn-sm">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
            
            <div class="p-6 space-y-4">
                {#if importResult}
                    <div class="space-y-3">
                        <div class="grid grid-cols-3 gap-3">
                            <div class="bg-accent/50 rounded-lg p-3 text-center">
                                <div class="text-2xl font-semibold text-foreground">{importResult.imported || 0}</div>
                                <div class="text-xs text-muted-foreground">New</div>
                            </div>
                            <div class="bg-primary/10 rounded-lg p-3 text-center">
                                <div class="text-2xl font-semibold text-primary">{importResult.updated || 0}</div>
                                <div class="text-xs text-muted-foreground">Updated</div>
                            </div>
                            <div class="bg-muted/50 rounded-lg p-3 text-center">
                                <div class="text-2xl font-semibold text-muted-foreground">{importResult.skipped || 0}</div>
                                <div class="text-xs text-muted-foreground">Skipped</div>
                            </div>
                        </div>
                        {#if importResult.errors && importResult.errors.length > 0}
                            <div class="bg-destructive/10 rounded-lg p-3">
                                <div class="text-sm font-medium text-destructive mb-1">Errors ({importResult.errors.length})</div>
                                <ul class="text-xs text-destructive/80 space-y-0.5">
                                    {#each importResult.errors.slice(0, 5) as err}
                                        <li>Row {err.row}: {err.error}</li>
                                    {/each}
                                    {#if importResult.errors.length > 5}
                                        <li class="text-muted-foreground">...and {importResult.errors.length - 5} more</li>
                                    {/if}
                                </ul>
                            </div>
                        {/if}
                    </div>
                {:else if importing}
                    <!-- Progress indicator while importing -->
                    <div class="text-center py-8">
                        <div class="inline-block w-12 h-12 border-4 border-primary/30 border-t-primary rounded-full animate-spin mb-4"></div>
                        <p class="text-sm font-medium">Importing participants...</p>
                        {#if importFile}
                            <p class="text-xs text-muted-foreground mt-1">Processing {importFile.name}</p>
                        {/if}
                        <p class="text-xs text-muted-foreground mt-3">
                            This may take a moment for large files
                        </p>
                    </div>
                {:else}
                    <div class="space-y-4">
                        <label class="block border-2 border-dashed border-border rounded-lg p-6 text-center hover:border-primary/50 transition-colors cursor-pointer">
                            <input 
                                type="file" 
                                accept=".txt,.csv,.json"
                                onchange={(e) => importFile = e.currentTarget.files?.[0] || null}
                                class="sr-only"
                            />
                            <svg class="w-8 h-8 mx-auto text-muted-foreground mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                            {#if importFile}
                                <p class="text-sm font-medium text-foreground">{importFile.name}</p>
                                <p class="text-xs text-muted-foreground mt-1">{(importFile.size / 1024).toFixed(1)} KB</p>
                            {:else}
                                <p class="text-sm text-muted-foreground">Click to select a file</p>
                            {/if}
                        </label>
                        
                        <!-- Update existing checkbox -->
                        <label class="flex items-center gap-2 cursor-pointer">
                            <input 
                                type="checkbox" 
                                bind:checked={updateExisting}
                                class="rounded border-border"
                            />
                            <span class="text-sm">Update existing participants</span>
                            <span class="text-xs text-muted-foreground">(rank, score, name)</span>
                        </label>
                        
                        <div class="text-xs text-muted-foreground space-y-1">
                            <p class="font-medium">Supported formats:</p>
                            <ul class="list-disc list-inside text-muted-foreground/80 space-y-0.5">
                                <li><code class="font-mono text-foreground/70">.txt</code> — One email per line</li>
                                <li><code class="font-mono text-foreground/70">.csv</code> — email required; username, name, rank, score optional</li>
                                <li><code class="font-mono text-foreground/70">.json</code> — Array of participant objects</li>
                            </ul>
                            <p class="mt-2 text-muted-foreground/70">
                                Batch imports add new participants. Column order doesn't matter.
                            </p>
                        </div>
                    </div>
                {/if}
            </div>

            <div class="px-6 py-4 border-t border-border flex justify-end gap-3">
                <button onclick={() => { showImportModal = false; importResult = null; }} class="btn btn-ghost">
                    {importResult ? 'Close' : 'Cancel'}
                </button>
                {#if !importResult}
                    <button 
                        onclick={handleImport}
                        disabled={importing || !importFile}
                        class="btn btn-primary"
                    >
                        {importing ? 'Importing...' : 'Import'}
                    </button>
                {/if}
            </div>
        </div>
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
