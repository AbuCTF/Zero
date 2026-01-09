<script lang="ts">
    import { onMount } from 'svelte';
    import { api, type Prize } from '$lib/api';
    import { formatDate } from '$lib/utils';

    let prizes = $state<Prize[]>([]);
    let loading = $state(true);
    let error = $state('');
    
    let claimingId = $state<number | null>(null);
    let showVoucher = $state<Prize | null>(null);

    onMount(async () => {
        await loadPrizes();
    });

    async function loadPrizes() {
        loading = true;
        try {
            prizes = await api.participant.prizes();
        } catch (e: any) {
            error = e.message || 'Failed to load prizes';
        } finally {
            loading = false;
        }
    }

    async function claimPrize(prizeId: number) {
        claimingId = prizeId;
        try {
            await api.participant.claimPrize(prizeId);
            await loadPrizes();
        } catch (e: any) {
            error = e.message || 'Failed to claim prize';
        } finally {
            claimingId = null;
        }
    }

    function copyVoucher(code: string) {
        navigator.clipboard.writeText(code);
    }

    function getStatusBadge(status: string): { class: string; text: string } {
        switch (status) {
            case 'pending': return { class: 'badge-warning', text: 'Ready to Claim' };
            case 'claimed': return { class: 'badge-success', text: 'Claimed' };
            case 'delivered': return { class: 'badge-secondary', text: 'Delivered' };
            default: return { class: 'badge-secondary', text: status };
        }
    }
</script>

<svelte:head>
    <title>My Prizes - Participant Portal</title>
</svelte:head>

<div class="space-y-6">
    <div>
        <h1 class="text-2xl font-semibold">My Prizes</h1>
        <p class="text-sm text-muted-foreground mt-1">
            View and claim your prizes from events
        </p>
    </div>

    {#if error}
        <div class="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
            {error}
        </div>
    {/if}

    {#if loading}
        <div class="card p-12 text-center">
            <div class="animate-pulse text-muted-foreground">Loading prizes...</div>
        </div>
    {:else if prizes.length === 0}
        <div class="card p-12 text-center">
            <div class="w-16 h-16 mx-auto mb-4 bg-muted rounded-full flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" />
                </svg>
            </div>
            <h2 class="text-lg font-medium mb-2">No Prizes Yet</h2>
            <p class="text-muted-foreground text-sm">
                Prizes will appear here once event results are finalized.
            </p>
        </div>
    {:else}
        <div class="grid gap-4">
            {#each prizes as prize}
                <div class="card p-6">
                    <div class="flex items-start justify-between">
                        <div class="flex-1">
                            <div class="flex items-center gap-3 mb-2">
                                <h3 class="font-medium">{prize.name}</h3>
                                <span class={`badge ${getStatusBadge(prize.status).class}`}>
                                    {getStatusBadge(prize.status).text}
                                </span>
                            </div>
                            
                            {#if prize.description}
                                <p class="text-sm text-muted-foreground mb-3">
                                    {prize.description}
                                </p>
                            {/if}
                            
                            <div class="flex items-center gap-4 text-sm text-muted-foreground">
                                <span>Event: {prize.event_name}</span>
                                {#if prize.rank}
                                    <span>Rank: #{prize.rank}</span>
                                {/if}
                            </div>
                        </div>
                        
                        <div class="flex items-center gap-2">
                            {#if prize.status === 'pending'}
                                <button 
                                    onclick={() => claimPrize(prize.id)}
                                    disabled={claimingId === prize.id}
                                    class="btn btn-primary"
                                >
                                    {claimingId === prize.id ? 'Claiming...' : 'Claim Prize'}
                                </button>
                            {:else if prize.voucher_code}
                                <button 
                                    onclick={() => showVoucher = prize}
                                    class="btn btn-secondary"
                                >
                                    View Voucher
                                </button>
                            {/if}
                        </div>
                    </div>

                    {#if prize.claimed_at}
                        <div class="mt-4 pt-4 border-t border-border text-xs text-muted-foreground">
                            Claimed on {formatDate(prize.claimed_at)}
                        </div>
                    {/if}
                </div>
            {/each}
        </div>
    {/if}
</div>

<!-- Voucher Modal -->
{#if showVoucher}
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div class="bg-card rounded-xl shadow-xl w-full max-w-md">
            <div class="px-6 py-4 border-b border-border flex items-center justify-between">
                <h2 class="text-lg font-semibold">Your Voucher Code</h2>
                <button onclick={() => showVoucher = null} class="btn btn-ghost btn-sm">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
            
            <div class="p-6">
                <div class="text-center mb-4">
                    <div class="text-sm text-muted-foreground mb-2">{showVoucher.name}</div>
                </div>
                
                <div class="bg-muted rounded-lg p-4 text-center mb-4">
                    <code class="text-xl font-mono font-bold tracking-wide">
                        {showVoucher.voucher_code}
                    </code>
                </div>
                
                <button 
                    onclick={() => copyVoucher(showVoucher!.voucher_code!)}
                    class="btn btn-primary w-full"
                >
                    Copy to Clipboard
                </button>

                {#if showVoucher.voucher_instructions}
                    <div class="mt-4 p-3 bg-muted/50 rounded-lg">
                        <div class="text-xs font-medium mb-1">Redemption Instructions:</div>
                        <div class="text-sm text-muted-foreground">
                            {showVoucher.voucher_instructions}
                        </div>
                    </div>
                {/if}
            </div>
        </div>
    </div>
{/if}

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
