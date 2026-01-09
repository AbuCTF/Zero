<script lang="ts">
    import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { api } from '$lib/api';

    let loading = $state(true);
    let error = $state('');
    let success = $state(false);

    const token = $derived($page.url.searchParams.get('token'));

    onMount(async () => {
        if (!token) {
            error = 'No access token provided';
            loading = false;
            return;
        }

        try {
            const response = await fetch(`/api/participants/verify-magic-link?token=${encodeURIComponent(token)}`, {
                method: 'POST',
                credentials: 'include'
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                success = true;
                // Redirect to portal after a moment
                setTimeout(() => {
                    goto('/portal');
                }, 1500);
            } else {
                error = data.detail || 'Invalid or expired access link';
            }
        } catch (e: any) {
            error = e.message || 'Failed to verify access link';
        } finally {
            loading = false;
        }
    });
</script>

<svelte:head>
    <title>Verifying Access - ZeroPool</title>
</svelte:head>

<div class="min-h-screen flex flex-col">
    <header class="border-b border-border">
        <div class="container mx-auto px-4 py-4">
            <a href="/" class="text-xl font-semibold">ZeroPool</a>
        </div>
    </header>

    <main class="flex-1 flex items-center justify-center p-4">
        <div class="w-full max-w-md text-center">
            {#if loading}
                <div class="card p-8">
                    <div class="w-16 h-16 mx-auto mb-4 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
                    <h2 class="text-lg font-semibold mb-2">Verifying Access</h2>
                    <p class="text-muted-foreground text-sm">Please wait...</p>
                </div>
            {:else if success}
                <div class="card p-8">
                    <div class="w-16 h-16 mx-auto mb-4 bg-green-500/20 rounded-full flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                        </svg>
                    </div>
                    <h2 class="text-lg font-semibold mb-2 text-green-500">Access Verified!</h2>
                    <p class="text-muted-foreground text-sm">Redirecting to your portal...</p>
                </div>
            {:else}
                <div class="card p-8">
                    <div class="w-16 h-16 mx-auto mb-4 bg-destructive/20 rounded-full flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-destructive" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </div>
                    <h2 class="text-lg font-semibold mb-2 text-destructive">Access Failed</h2>
                    <p class="text-muted-foreground text-sm mb-4">{error}</p>
                    <a href="/portal/login" class="btn btn-primary">
                        Request New Link
                    </a>
                </div>
            {/if}
        </div>
    </main>
</div>
