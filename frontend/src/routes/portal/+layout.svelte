<script lang="ts">
    import type { Snippet } from 'svelte';
    import { onMount } from 'svelte';
    import { page } from '$app/stores';
    import { goto } from '$app/navigation';
    import { api, type Participant } from '$lib/api';

    interface Props {
        children: Snippet;
    }
    let { children }: Props = $props();

    let participant = $state<Participant | null>(null);
    let loading = $state(true);

    const currentPath = $derived($page.url.pathname);

    onMount(async () => {
        await checkAuth();
    });

    async function checkAuth() {
        try {
            participant = await api.participant.me();
        } catch {
            goto('/portal/login');
        } finally {
            loading = false;
        }
    }

    async function handleLogout() {
        try {
            await api.participant.logout();
        } catch {
            // Ignore errors
        }
        goto('/');
    }

    const navItems = [
        { href: '/portal', label: 'Dashboard', icon: 'home' },
        { href: '/portal/prizes', label: 'My Prizes', icon: 'gift' },
        { href: '/portal/certificates', label: 'Certificates', icon: 'document' }
    ];
</script>

{#if loading}
    <div class="min-h-screen flex items-center justify-center">
        <div class="animate-pulse text-muted-foreground">Loading...</div>
    </div>
{:else}
    <div class="min-h-screen flex">
        <!-- Sidebar -->
        <aside class="w-64 bg-card border-r border-border flex flex-col">
            <div class="p-6 border-b border-border">
                <a href="/" class="block">
                    <img src="/logo.png" alt="ZeroPool" class="h-8 w-auto" />
                </a>
                <div class="text-xs text-muted-foreground mt-2">Participant Portal</div>
            </div>

            <nav class="flex-1 p-4">
                <ul class="space-y-1">
                    {#each navItems as item}
                        <li>
                            <a 
                                href={item.href}
                                class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors
                                       {currentPath === item.href 
                                           ? 'bg-primary/10 text-primary' 
                                           : 'text-muted-foreground hover:text-foreground hover:bg-muted'}"
                            >
                                {#if item.icon === 'home'}
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                                    </svg>
                                {:else if item.icon === 'gift'}
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" />
                                    </svg>
                                {:else if item.icon === 'document'}
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                {/if}
                                {item.label}
                            </a>
                        </li>
                    {/each}
                </ul>
            </nav>

            <div class="p-4 border-t border-border">
                {#if participant}
                    <div class="flex items-center gap-3 mb-3">
                        <div class="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-medium text-sm">
                            {participant.name.charAt(0).toUpperCase()}
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="text-sm font-medium truncate">{participant.name}</div>
                            <div class="text-xs text-muted-foreground truncate">{participant.email}</div>
                        </div>
                    </div>
                {/if}
                <button onclick={handleLogout} class="btn btn-ghost btn-sm w-full justify-start">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    Logout
                </button>
            </div>
        </aside>

        <!-- Main content -->
        <main class="flex-1 overflow-auto">
            <div class="p-8">
                {@render children()}
            </div>
        </main>
    </div>
{/if}
