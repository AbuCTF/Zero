<script lang="ts">
    import { onMount } from 'svelte';
    import { page } from '$app/stores';
    import { api, type Event } from '$lib/api';
    import { formatDate } from '$lib/utils';

    const slug = $derived($page.params.slug);
    
    let event = $state<Event | null>(null);
    let loading = $state(true);
    let error = $state('');
    let success = $state(false);
    let submitting = $state(false);

    let form = $state({
        name: '',
        email: '',
        team_name: '',
        team_password: '',
        create_team: true
    });

    onMount(async () => {
        await loadEvent();
    });

    async function loadEvent() {
        loading = true;
        error = '';
        try {
            event = await api.events.getBySlug(slug);
        } catch (e: any) {
            error = e.message || 'Event not found';
        } finally {
            loading = false;
        }
    }

    function isRegistrationOpen(): boolean {
        if (!event) return false;
        
        // Check if import-only mode
        if (event.settings?.is_import_only) return false;
        
        if (event.status !== 'registration' && event.status !== 'live') return false;
        
        const now = new Date();
        if (event.registration_start && new Date(event.registration_start) > now) return false;
        if (event.registration_end && new Date(event.registration_end) < now) return false;
        
        return true;
    }

    function isImportOnly(): boolean {
        return event?.settings?.is_import_only === true;
    }

    function getRegistrationStatus(): { text: string; class: string } {
        if (!event) return { text: '', class: '' };
        
        // Check import-only mode first
        if (event.settings?.is_import_only) {
            return { 
                text: 'Invite only',
                class: 'text-foreground-muted'
            };
        }
        
        const now = new Date();
        
        if (event.registration_start && new Date(event.registration_start) > now) {
            return { 
                text: `Registration opens ${formatDate(event.registration_start)}`,
                class: 'text-foreground-muted'
            };
        }
        
        if (event.registration_end && new Date(event.registration_end) < now) {
            return { 
                text: 'Registration closed',
                class: 'text-destructive'
            };
        }
        
        if (event.status === 'completed' || event.status === 'finalized') {
            return { 
                text: 'Event ended',
                class: 'text-foreground-muted'
            };
        }
        
        if (event.status !== 'registration' && event.status !== 'live') {
            return { 
                text: 'Registration not available',
                class: 'text-foreground-muted'
            };
        }
        
        return { 
            text: 'Registration open',
            class: 'text-success'
        };
    }

    async function handleSubmit() {
        if (!event) return;
        
        submitting = true;
        error = '';
        
        try {
            await api.events.register(event.id, {
                name: form.name,
                email: form.email,
                team_name: event.team_mode ? form.team_name : undefined,
                team_password: event.team_mode && !form.create_team ? form.team_password : undefined,
                create_team: event.team_mode ? form.create_team : undefined
            });
            
            success = true;
        } catch (e: any) {
            error = e.message || 'Registration failed';
        } finally {
            submitting = false;
        }
    }
</script>

<svelte:head>
    <title>{event?.name || 'Event'} - ZeroPool</title>
</svelte:head>

<div class="min-h-screen flex flex-col">
    <header class="border-b border-border">
        <div class="container mx-auto px-4 py-4">
            <a href="/" class="text-xl font-semibold">ZeroPool</a>
        </div>
    </header>

    <main class="flex-1 container mx-auto px-4 py-12">
        {#if loading}
            <div class="text-center py-12">
                <div class="animate-pulse text-muted-foreground">Loading event...</div>
            </div>
        {:else if error && !event}
            <div class="text-center py-12">
                <h1 class="text-2xl font-semibold mb-4">Event Not Found</h1>
                <p class="text-muted-foreground mb-6">
                    The event you're looking for doesn't exist or has been removed.
                </p>
                <a href="/" class="btn btn-primary">Go Home</a>
            </div>
        {:else if event}
            <div class="max-w-xl mx-auto">
                <div class="text-center mb-8">
                    <h1 class="text-3xl font-bold mb-2">{event.name}</h1>
                    {#if event.description}
                        <p class="text-muted-foreground">{event.description}</p>
                    {/if}
                    
                    <div class="mt-4 flex items-center justify-center gap-4 text-sm">
                        {#if event.start_date}
                            <span class="text-muted-foreground">
                                {formatDate(event.start_date)}
                            </span>
                        {/if}
                        <span class={getRegistrationStatus().class}>
                            {getRegistrationStatus().text}
                        </span>
                    </div>
                </div>

                {#if success}
                    <div class="card p-8 text-center">
                        <div class="w-16 h-16 mx-auto mb-4 bg-green-500/20 rounded-full flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <h2 class="text-xl font-semibold mb-2">Registration Successful</h2>
                        <p class="text-muted-foreground mb-6">
                            We've sent a verification email to <strong>{form.email}</strong>.
                            Please check your inbox and click the verification link to complete your registration.
                        </p>
                        <p class="text-sm text-muted-foreground">
                            Didn't receive the email? Check your spam folder or contact the organizers.
                        </p>
                    </div>
                {:else if isImportOnly()}
                    <div class="card p-8 text-center">
                        <div class="w-16 h-16 mx-auto mb-4 bg-accent rounded-full flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-foreground-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                            </svg>
                        </div>
                        <h2 class="text-xl font-semibold mb-2">Participant Portal</h2>
                        <p class="text-foreground-muted mb-6">
                            This event uses pre-registered participants. If you participated in this event, 
                            you can access your certificates and prizes through the participant portal.
                        </p>
                        <a href="/portal/login" class="btn btn-primary">
                            Access Participant Portal
                        </a>
                    </div>
                {:else if !isRegistrationOpen()}
                    <div class="card p-8 text-center">
                        <h2 class="text-xl font-semibold mb-2">Registration Unavailable</h2>
                        <p class="text-foreground-muted">
                            {getRegistrationStatus().text}
                        </p>
                    </div>
                {:else}
                    <div class="card p-6">
                        {#if error}
                            <div class="bg-destructive/10 text-destructive px-4 py-3 rounded-lg mb-6">
                                {error}
                            </div>
                        {/if}

                        <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
                            <div>
                                <label for="name" class="block text-sm font-medium mb-1.5">
                                    Full Name
                                </label>
                                <input
                                    type="text"
                                    id="name"
                                    bind:value={form.name}
                                    class="input"
                                    placeholder="John Doe"
                                    required
                                />
                            </div>

                            <div>
                                <label for="email" class="block text-sm font-medium mb-1.5">
                                    Email Address
                                </label>
                                <input
                                    type="email"
                                    id="email"
                                    bind:value={form.email}
                                    class="input"
                                    placeholder="you@example.com"
                                    required
                                />
                            </div>

                            {#if event.team_mode}
                                <hr class="border-border" />
                                
                                <div class="space-y-3">
                                    <label class="flex items-center gap-3 p-3 rounded-lg border border-border cursor-pointer hover:bg-muted/30 transition-colors {form.create_team ? 'bg-primary/5 border-primary' : ''}">
                                        <input type="radio" bind:group={form.create_team} value={true} class="accent-primary" />
                                        <div>
                                            <div class="font-medium text-sm">Create a new team</div>
                                            <div class="text-xs text-muted-foreground">
                                                Start your own team and invite others
                                            </div>
                                        </div>
                                    </label>
                                    
                                    <label class="flex items-center gap-3 p-3 rounded-lg border border-border cursor-pointer hover:bg-muted/30 transition-colors {!form.create_team ? 'bg-primary/5 border-primary' : ''}">
                                        <input type="radio" bind:group={form.create_team} value={false} class="accent-primary" />
                                        <div>
                                            <div class="font-medium text-sm">Join existing team</div>
                                            <div class="text-xs text-muted-foreground">
                                                Enter team name and password to join
                                            </div>
                                        </div>
                                    </label>
                                </div>

                                <div>
                                    <label for="team" class="block text-sm font-medium mb-1.5">
                                        Team Name
                                    </label>
                                    <input
                                        type="text"
                                        id="team"
                                        bind:value={form.team_name}
                                        class="input"
                                        placeholder="The Hackers"
                                        required
                                    />
                                </div>

                                {#if !form.create_team}
                                    <div>
                                        <label for="team-password" class="block text-sm font-medium mb-1.5">
                                            Team Password
                                        </label>
                                        <input
                                            type="password"
                                            id="team-password"
                                            bind:value={form.team_password}
                                            class="input"
                                            placeholder="Ask your team captain"
                                            required
                                        />
                                    </div>
                                {/if}

                                <p class="text-xs text-muted-foreground">
                                    Team size: {event.min_team_size || 1} - {event.max_team_size || 4} members
                                </p>
                            {/if}

                            <button 
                                type="submit" 
                                disabled={submitting}
                                class="btn btn-primary w-full"
                            >
                                {submitting ? 'Registering...' : 'Register'}
                            </button>
                        </form>
                    </div>
                {/if}
            </div>
        {/if}
    </main>

    <footer class="border-t border-border py-6">
        <div class="container mx-auto px-4 text-center text-sm text-muted-foreground">
            Powered by ZeroPool
        </div>
    </footer>
</div>
