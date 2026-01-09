<script lang="ts">
    import { onMount } from 'svelte';
    import { api, type EmailCampaign, type Event, type EmailTemplate } from '$lib/api';
    import { formatDate, formatNumber } from '$lib/utils';

    let campaigns = $state<EmailCampaign[]>([]);
    let events = $state<Event[]>([]);
    let templates = $state<EmailTemplate[]>([]);
    let loading = $state(true);
    let error = $state('');
    
    let showModal = $state(false);
    let saving = $state(false);
    
    let form = $state({
        name: '',
        event_id: '' as string | number,
        template_id: '' as string | number,
        recipient_filter: 'all' as 'all' | 'verified' | 'unverified' | 'prize_winners' | 'no_prize',
        scheduled_at: ''
    });

    const recipientFilters = [
        { value: 'all', label: 'All Participants' },
        { value: 'verified', label: 'Verified Only' },
        { value: 'unverified', label: 'Unverified Only' },
        { value: 'prize_winners', label: 'Prize Winners' },
        { value: 'no_prize', label: 'No Prize Yet' }
    ];

    const statusColors: Record<string, string> = {
        draft: 'badge-secondary',
        scheduled: 'badge-warning',
        sending: 'badge-primary',
        completed: 'badge-success',
        paused: 'badge-secondary',
        failed: 'badge-destructive'
    };

    onMount(async () => {
        await Promise.all([loadCampaigns(), loadEvents(), loadTemplates()]);
    });

    async function loadCampaigns() {
        loading = true;
        error = '';
        try {
            campaigns = await api.admin.campaigns.list();
        } catch (e: any) {
            error = e.message || 'Failed to load campaigns';
        } finally {
            loading = false;
        }
    }

    async function loadEvents() {
        try {
            const response = await api.admin.events.list();
            events = response.events || response;
        } catch (e) {
            console.error('Failed to load events:', e);
        }
    }

    async function loadTemplates() {
        try {
            templates = await api.admin.templates.list();
        } catch (e) {
            console.error('Failed to load templates:', e);
        }
    }

    function openAddModal() {
        form = {
            name: '',
            event_id: '',
            template_id: '',
            recipient_filter: 'all',
            scheduled_at: ''
        };
        showModal = true;
    }

    async function handleSubmit() {
        if (!form.event_id || !form.template_id) {
            error = 'Please select an event and template';
            return;
        }
        
        saving = true;
        error = '';
        try {
            await api.admin.campaigns.create({
                name: form.name,
                event_id: String(form.event_id),
                template_id: String(form.template_id),
                recipient_filter: { type: form.recipient_filter },
                scheduled_at: form.scheduled_at || undefined
            });
            showModal = false;
            await loadCampaigns();
        } catch (e: any) {
            error = e.message || 'Failed to create campaign';
        } finally {
            saving = false;
        }
    }

    async function startCampaign(id: string) {
        if (!confirm('Start sending this campaign? This action cannot be undone.')) return;
        
        try {
            await api.admin.campaigns.start(id);
            await loadCampaigns();
        } catch (e: any) {
            error = e.message || 'Failed to start campaign';
        }
    }

    async function pauseCampaign(id: string) {
        try {
            await api.admin.campaigns.pause(id);
            await loadCampaigns();
        } catch (e: any) {
            error = e.message || 'Failed to pause campaign';
        }
    }

    async function deleteCampaign(id: string) {
        if (!confirm('Are you sure you want to delete this campaign?')) return;
        
        try {
            await api.admin.campaigns.delete(id);
            await loadCampaigns();
        } catch (e: any) {
            error = e.message || 'Failed to delete campaign';
        }
    }

    function getEventName(eventId: string): string {
        return events.find(e => e.id === eventId)?.name || 'Unknown Event';
    }

    function getTemplateName(templateId: string): string {
        return templates.find(t => t.id === templateId)?.name || 'Unknown Template';
    }

    function getProgress(campaign: EmailCampaign): number {
        if (!campaign.total_recipients || campaign.total_recipients === 0) return 0;
        return Math.round(((campaign.sent_count || 0) / campaign.total_recipients) * 100);
    }
</script>

<svelte:head>
    <title>Email Campaigns - ZeroPool Admin</title>
</svelte:head>

<div class="p-6 lg:p-8">
    <div class="space-y-6">
        <div class="flex items-center justify-between">
        <div>
            <h1 class="text-2xl font-semibold">Email Campaigns</h1>
            <p class="text-sm text-muted-foreground mt-1">
                Send bulk emails to event participants
            </p>
        </div>
        <button onclick={openAddModal} class="btn btn-primary">
            New Campaign
        </button>
    </div>

    {#if error}
        <div class="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
            {error}
        </div>
    {/if}

    {#if loading}
        <div class="card p-12 text-center">
            <div class="animate-pulse text-muted-foreground">Loading campaigns...</div>
        </div>
    {:else if campaigns.length === 0}
        <div class="card p-12 text-center">
            <div class="text-muted-foreground mb-4">No email campaigns yet</div>
            <button onclick={openAddModal} class="btn btn-primary">
                Create Your First Campaign
            </button>
        </div>
    {:else}
        <div class="space-y-4">
            {#each campaigns as campaign}
                <div class="card p-6">
                    <div class="flex items-start justify-between mb-4">
                        <div>
                            <div class="flex items-center gap-3">
                                <h3 class="font-medium">{campaign.name}</h3>
                                <span class={`badge ${statusColors[campaign.status] || 'badge-secondary'}`}>
                                    {campaign.status}
                                </span>
                            </div>
                            <div class="text-sm text-muted-foreground mt-1 space-x-4">
                                <span>Event: {getEventName(campaign.event_id)}</span>
                                <span>Template: {getTemplateName(campaign.template_id)}</span>
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                            {#if campaign.status === 'draft' || campaign.status === 'scheduled'}
                                <button 
                                    onclick={() => startCampaign(campaign.id)}
                                    class="btn btn-primary btn-sm"
                                >
                                    Start
                                </button>
                            {/if}
                            {#if campaign.status === 'sending'}
                                <button 
                                    onclick={() => pauseCampaign(campaign.id)}
                                    class="btn btn-secondary btn-sm"
                                >
                                    Pause
                                </button>
                            {/if}
                            {#if campaign.status === 'paused'}
                                <button 
                                    onclick={() => startCampaign(campaign.id)}
                                    class="btn btn-primary btn-sm"
                                >
                                    Resume
                                </button>
                            {/if}
                            {#if campaign.status === 'draft'}
                                <button 
                                    onclick={() => deleteCampaign(campaign.id)}
                                    class="btn btn-ghost btn-sm text-destructive"
                                >
                                    Delete
                                </button>
                            {/if}
                        </div>
                    </div>

                    {#if campaign.status === 'sending' || campaign.status === 'completed'}
                        <div class="space-y-2">
                            <div class="flex justify-between text-sm">
                                <span class="text-muted-foreground">Progress</span>
                                <span>
                                    {formatNumber(campaign.sent_count || 0)} / {formatNumber(campaign.total_recipients || 0)} sent
                                </span>
                            </div>
                            <div class="h-2 bg-muted rounded-full overflow-hidden">
                                <div 
                                    class="h-full bg-primary transition-all duration-300"
                                    style="width: {getProgress(campaign)}%"
                                ></div>
                            </div>
                            <div class="flex justify-between text-xs text-muted-foreground">
                                <span>
                                    {formatNumber(campaign.failed_count || 0)} failed
                                </span>
                                <span>{getProgress(campaign)}%</span>
                            </div>
                        </div>
                    {:else if campaign.scheduled_at}
                        <div class="text-sm text-muted-foreground">
                            Scheduled for: {formatDate(campaign.scheduled_at)}
                        </div>
                    {/if}

                    {#if campaign.started_at || campaign.completed_at}
                        <div class="flex gap-4 mt-4 pt-4 border-t border-border text-xs text-muted-foreground">
                            {#if campaign.started_at}
                                <span>Started: {formatDate(campaign.started_at)}</span>
                            {/if}
                            {#if campaign.completed_at}
                                <span>Completed: {formatDate(campaign.completed_at)}</span>
                            {/if}
                        </div>
                    {/if}
                </div>
            {/each}
        </div>
    {/if}
</div>

{#if showModal}
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div class="bg-card rounded-xl shadow-xl w-full max-w-lg">
            <div class="px-6 py-4 border-b border-border flex items-center justify-between">
                <h2 class="text-lg font-semibold">New Campaign</h2>
                <button onclick={() => showModal = false} class="btn btn-ghost btn-sm">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
            
            <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="p-6 space-y-4">
                <div>
                    <label for="name" class="block text-sm font-medium mb-1.5">
                        Campaign Name
                    </label>
                    <input
                        type="text"
                        id="name"
                        bind:value={form.name}
                        class="input"
                        placeholder="Results Announcement"
                        required
                    />
                </div>

                <div>
                    <label for="event" class="block text-sm font-medium mb-1.5">
                        Event
                    </label>
                    <select id="event" bind:value={form.event_id} class="input" required>
                        <option value="">Select event...</option>
                        {#each events as event}
                            <option value={event.id}>{event.name}</option>
                        {/each}
                    </select>
                </div>

                <div>
                    <label for="template" class="block text-sm font-medium mb-1.5">
                        Email Template
                    </label>
                    <select id="template" bind:value={form.template_id} class="input" required>
                        <option value="">Select template...</option>
                        {#each templates as template}
                            <option value={template.id}>{template.name}</option>
                        {/each}
                    </select>
                </div>

                <div>
                    <label for="filter" class="block text-sm font-medium mb-1.5">
                        Recipients
                    </label>
                    <select id="filter" bind:value={form.recipient_filter} class="input">
                        {#each recipientFilters as filter}
                            <option value={filter.value}>{filter.label}</option>
                        {/each}
                    </select>
                </div>

                <div>
                    <label for="scheduled" class="block text-sm font-medium mb-1.5">
                        Schedule (Optional)
                    </label>
                    <input
                        type="datetime-local"
                        id="scheduled"
                        bind:value={form.scheduled_at}
                        class="input"
                    />
                    <p class="text-xs text-muted-foreground mt-1">
                        Leave empty to send immediately when started
                    </p>
                </div>
            </form>

            <div class="px-6 py-4 border-t border-border flex justify-end gap-3">
                <button onclick={() => showModal = false} class="btn btn-ghost">
                    Cancel
                </button>
                <button 
                    onclick={handleSubmit}
                    disabled={saving}
                    class="btn btn-primary"
                >
                    {saving ? 'Creating...' : 'Create Campaign'}
                </button>
            </div>
        </div>
    </div>
{/if}

<style>
    .badge-warning {
        background-color: hsl(45 93% 47% / 0.15);
        color: hsl(45 93% 47%);
    }
    .badge-success {
        background-color: hsl(142 76% 36% / 0.15);
        color: hsl(142 76% 36%);
    }
</style>
</div>
