<script lang="ts">
    import { goto } from '$app/navigation';
    import { api } from '$lib/api';

    let email = $state('');
    let loading = $state(false);
    let error = $state('');
    let sent = $state(false);
    
    // Event picker state
    let showEventPicker = $state(false);
    let availableEvents = $state<Array<{ id: string; name: string; slug: string }>>([]);

    async function handleSubmit(selectedEventId?: string) {
        if (!email) return;
        
        loading = true;
        error = '';
        
        try {
            const result = await api.participant.requestAccess(email, selectedEventId);
            
            if (result.requires_event_selection && result.events) {
                // User is registered for multiple events - show picker
                availableEvents = result.events;
                showEventPicker = true;
            } else {
                // Single event or event selected - email sent
                sent = true;
            }
        } catch (e: any) {
            error = e.message || 'Failed to send access link';
        } finally {
            loading = false;
        }
    }
    
    function selectEvent(eventId: string) {
        handleSubmit(eventId);
    }
    
    function goBack() {
        showEventPicker = false;
        availableEvents = [];
    }
</script>

<svelte:head>
    <title>Participant Portal - ZeroPool</title>
</svelte:head>

<div class="min-h-screen flex flex-col">
    <header class="border-b border-border">
        <div class="container mx-auto px-4 py-4">
            <a href="/" class="text-xl font-semibold">ZeroPool</a>
        </div>
    </header>

    <main class="flex-1 flex items-center justify-center p-4">
        <div class="w-full max-w-md">
            <div class="text-center mb-8">
                <h1 class="text-2xl font-bold mb-2">Participant Portal</h1>
                <p class="text-muted-foreground">
                    Access your prizes and certificates
                </p>
            </div>

            <div class="card p-6">
                {#if sent}
                    <div class="text-center py-4">
                        <div class="w-16 h-16 mx-auto mb-4 bg-primary/20 rounded-full flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                            </svg>
                        </div>
                        <h2 class="text-lg font-semibold mb-2">Check Your Email</h2>
                        <p class="text-muted-foreground text-sm">
                            We've sent a magic link to <strong>{email}</strong>.
                            Click the link in the email to access your portal.
                        </p>
                    </div>
                {:else if showEventPicker}
                    <!-- Event Picker for multi-event users -->
                    <div class="space-y-4">
                        <div class="text-center">
                            <h2 class="text-lg font-semibold mb-2">Select Event</h2>
                            <p class="text-muted-foreground text-sm">
                                You're registered for multiple events. Which one would you like to access?
                            </p>
                        </div>
                        
                        <div class="space-y-2">
                            {#each availableEvents as event}
                                <button
                                    onclick={() => selectEvent(event.id)}
                                    disabled={loading}
                                    class="w-full p-4 text-left rounded-lg border border-border hover:border-primary hover:bg-primary/5 transition-colors disabled:opacity-50"
                                >
                                    <div class="font-medium">{event.name}</div>
                                    <div class="text-xs text-muted-foreground mt-0.5">{event.slug}</div>
                                </button>
                            {/each}
                        </div>
                        
                        <button 
                            onclick={goBack}
                            class="btn btn-ghost w-full"
                        >
                            ← Back
                        </button>
                    </div>
                {:else}
                    {#if error}
                        <div class="bg-destructive/10 text-destructive px-4 py-3 rounded-lg mb-4 text-sm">
                            {error}
                        </div>
                    {/if}

                    <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
                        <div>
                            <label for="email" class="block text-sm font-medium mb-1.5">
                                Email Address
                            </label>
                            <input
                                type="email"
                                id="email"
                                bind:value={email}
                                class="input"
                                placeholder="you@example.com"
                                required
                            />
                            <p class="text-xs text-muted-foreground mt-1.5">
                                Enter the email you used to register for an event
                            </p>
                        </div>

                        <button 
                            type="submit" 
                            disabled={loading}
                            class="btn btn-primary w-full"
                        >
                            {loading ? 'Sending...' : 'Send Access Link'}
                        </button>
                    </form>
                {/if}
            </div>

            <p class="text-center text-sm text-muted-foreground mt-6">
                <a href="/" class="hover:text-foreground">Back to Home</a>
            </p>
        </div>
    </main>
</div>
