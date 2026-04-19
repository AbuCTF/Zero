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

        if (event.settings?.is_import_only) {
            return { text: 'Invite only', class: 'text-foreground-muted' };
        }

        const now = new Date();

        if (event.registration_start && new Date(event.registration_start) > now) {
            return {
                text: `Registration opens ${formatDate(event.registration_start)}`,
                class: 'text-foreground-muted'
            };
        }

        if (event.registration_end && new Date(event.registration_end) < now) {
            return { text: 'Registration closed', class: 'text-destructive' };
        }

        if (event.status === 'completed' || event.status === 'finalized') {
            return { text: 'Event ended', class: 'text-foreground-muted' };
        }

        if (event.status !== 'registration' && event.status !== 'live') {
            return { text: 'Registration not available', class: 'text-foreground-muted' };
        }

        return { text: 'Registration open', class: 'text-success' };
    }

    function getStatusLabel(): string {
        if (!event) return '';
        if (event.status === 'live') return 'Live now';
        if (event.status === 'registration') return 'Registration open';
        if (event.status === 'active') return 'Active';
        if (event.status === 'completed' || event.status === 'finalized') return 'Ended';
        return '';
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
    <title>{event?.name || 'Event'} — ZeroPool</title>
</svelte:head>

<div class="min-h-screen bg-background flex flex-col">

    <!-- Header -->
    <header class="sticky top-0 z-10 bg-background/90 backdrop-blur-sm border-b border-border/50">
        <div class="max-w-2xl mx-auto px-5 sm:px-8 h-14 flex items-center">
            <a href="/" class="opacity-80 hover:opacity-100 transition-opacity duration-200" aria-label="Home">
                <img src="/logo.png" alt="ZeroPool" class="h-6 w-auto" />
            </a>
        </div>
    </header>

    <main class="flex-1 max-w-2xl mx-auto w-full px-5 sm:px-8 py-12 sm:py-16">

        <!-- Loading -->
        {#if loading}
            <div class="max-w-sm mx-auto text-center space-y-3 mb-12">
                <div class="skeleton h-7 w-48 mx-auto rounded" />
                <div class="skeleton h-4 w-64 mx-auto rounded" />
                <div class="skeleton h-3 w-28 mx-auto rounded" />
            </div>
            <div class="max-w-sm mx-auto card space-y-4">
                <div class="skeleton h-9 rounded" />
                <div class="skeleton h-9 rounded" />
                <div class="skeleton h-10 rounded" />
            </div>

        <!-- Not found -->
        {:else if error && !event}
            <div class="text-center py-24">
                <p class="text-xs font-mono text-foreground-muted/50 mb-2 tracking-widest uppercase">Not Found</p>
                <h1 class="text-2xl font-semibold tracking-tight mb-3">Event doesn't exist</h1>
                <p class="text-sm text-foreground-muted mb-8 max-w-xs mx-auto">
                    This event may have been removed or the link is incorrect.
                </p>
                <a href="/" class="btn-secondary">← Go home</a>
            </div>

        {:else if event}
            <!-- Event header -->
            <div class="text-center mb-10 sm:mb-14">
                {#if getStatusLabel()}
                    <p class="text-label mb-4">{getStatusLabel()}</p>
                {/if}
                <h1 class="text-3xl sm:text-4xl font-semibold tracking-tight mb-3">
                    {event.name}
                </h1>
                {#if event.description}
                    <p class="text-foreground-muted text-sm sm:text-base max-w-sm mx-auto leading-relaxed">
                        {event.description}
                    </p>
                {/if}

                <div class="mt-6 flex items-center justify-center gap-2.5 text-xs font-mono">
                    {#if event.start_date}
                        <span class="text-foreground-muted">{formatDate(event.start_date)}</span>
                        <span class="w-1 h-1 rounded-full bg-border-hover flex-shrink-0" aria-hidden="true" />
                    {/if}
                    <span class={getRegistrationStatus().class}>
                        {getRegistrationStatus().text}
                    </span>
                </div>
            </div>

            <!-- State cards -->
            <div class="max-w-sm mx-auto">

                <!-- Success -->
                {#if success}
                    <div class="text-center py-10 space-y-5 fade-in">
                        <div class="w-12 h-12 mx-auto rounded-full border border-success/30 bg-success/10 flex items-center justify-center">
                            <svg class="w-5 h-5 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <div>
                            <h2 class="text-base font-semibold mb-2">You're registered</h2>
                            <p class="text-sm text-foreground-muted leading-relaxed">
                                Check <span class="font-mono text-foreground">{form.email}</span> for a verification link to complete your registration.
                            </p>
                        </div>
                        <p class="text-xs text-foreground-muted/50">
                            Nothing in your inbox? Check spam or contact the organizers.
                        </p>
                    </div>

                <!-- Import only / Participant portal -->
                {:else if isImportOnly()}
                    <div class="text-center py-10 space-y-5 fade-in">
                        <div class="w-12 h-12 mx-auto rounded-full border border-border bg-accent flex items-center justify-center">
                            <svg class="w-5 h-5 text-foreground-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                            </svg>
                        </div>
                        <div>
                            <h2 class="text-base font-semibold mb-2">Invite only</h2>
                            <p class="text-sm text-foreground-muted leading-relaxed">
                                This event uses pre-registered participants. Access your certificates and prizes through the participant portal.
                            </p>
                        </div>
                        <a href="/portal/login" class="btn-primary w-full">
                            Participant Portal →
                        </a>
                    </div>

                <!-- Registration unavailable -->
                {:else if !isRegistrationOpen()}
                    <div class="text-center py-10 space-y-4 fade-in">
                        <div class="w-12 h-12 mx-auto rounded-full border border-border bg-accent flex items-center justify-center">
                            <svg class="w-5 h-5 text-foreground-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                            </svg>
                        </div>
                        <div>
                            <h2 class="text-base font-semibold mb-1">Registration Unavailable</h2>
                            <p class="text-sm text-foreground-muted">{getRegistrationStatus().text}</p>
                        </div>
                    </div>

                <!-- Registration form -->
                {:else}
                    <div class="card fade-in">
                        {#if error}
                            <div class="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/20 text-destructive text-xs rounded-md mb-5">
                                <svg class="w-3.5 h-3.5 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                                </svg>
                                <span class="font-mono">{error}</span>
                            </div>
                        {/if}

                        <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
                            <div class="space-y-1.5">
                                <label for="name" class="input-label">Full Name</label>
                                <input
                                    type="text"
                                    id="name"
                                    bind:value={form.name}
                                    class="input"
                                    placeholder="John Doe"
                                    autocomplete="name"
                                    required
                                />
                            </div>

                            <div class="space-y-1.5">
                                <label for="email" class="input-label">Email Address</label>
                                <input
                                    type="email"
                                    id="email"
                                    bind:value={form.email}
                                    class="input"
                                    placeholder="you@example.com"
                                    autocomplete="email"
                                    required
                                />
                            </div>

                            {#if event.team_mode}
                                <div class="border-t border-border pt-4 space-y-2.5">
                                    <p class="text-label mb-3">Team</p>

                                    <label class="flex items-center gap-3 p-3 rounded-md border cursor-pointer transition-colors
                                        {form.create_team ? 'border-foreground/20 bg-accent/60' : 'border-border hover:border-border-hover'}">
                                        <input type="radio" bind:group={form.create_team} value={true} class="accent-primary" />
                                        <div>
                                            <div class="text-sm font-medium">Create team</div>
                                            <div class="text-xs text-foreground-muted mt-0.5">Start a new team, invite others</div>
                                        </div>
                                    </label>

                                    <label class="flex items-center gap-3 p-3 rounded-md border cursor-pointer transition-colors
                                        {!form.create_team ? 'border-foreground/20 bg-accent/60' : 'border-border hover:border-border-hover'}">
                                        <input type="radio" bind:group={form.create_team} value={false} class="accent-primary" />
                                        <div>
                                            <div class="text-sm font-medium">Join team</div>
                                            <div class="text-xs text-foreground-muted mt-0.5">Enter team name and password</div>
                                        </div>
                                    </label>
                                </div>

                                <div class="space-y-1.5">
                                    <label for="team" class="input-label">Team Name</label>
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
                                    <div class="space-y-1.5">
                                        <label for="team-password" class="input-label">Team Password</label>
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

                                <p class="text-xs text-foreground-muted font-mono">
                                    {event.min_team_size || 1}–{event.max_team_size || 4} members per team
                                </p>
                            {/if}

                            <button
                                type="submit"
                                disabled={submitting}
                                class="btn-primary w-full mt-1"
                            >
                                {#if submitting}
                                    <svg class="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    Registering...
                                {:else}
                                    Register →
                                {/if}
                            </button>
                        </form>
                    </div>
                {/if}

            </div>
        {/if}
    </main>

    <!-- Footer -->
    <footer class="border-t border-border/40 py-5 mt-auto">
        <div class="max-w-2xl mx-auto px-5 sm:px-8 flex items-center justify-between">
            <span class="text-xs font-mono text-foreground-muted/40">Powered by</span>
            <img src="/logo.png" alt="ZeroPool" class="h-4 w-auto opacity-30" />
        </div>
    </footer>

</div>
