<script lang="ts">
    import { goto } from '$app/navigation';
    import { api } from '$lib/api';

    let saving = $state(false);
    let error = $state('');

    let form = $state({
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
        ctfd_api_key: '',
        is_import_only: false
    });

    function generateSlug(name: string): string {
        return name
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-|-$/g, '');
    }

    function handleNameChange() {
        if (!form.slug || form.slug === generateSlug(form.name.slice(0, -1))) {
            form.slug = generateSlug(form.name);
        }
    }

    async function handleSubmit() {
        if (!form.name || !form.slug) {
            error = 'Name and slug are required';
            return;
        }
        
        saving = true;
        error = '';
        
        try {
            const event = await api.admin.events.create({
                ...form,
                start_date: form.start_date || undefined,
                end_date: form.end_date || undefined,
                registration_open: form.registration_open || undefined,
                registration_close: form.registration_close || undefined
            });
            
            goto(`/admin/events/${event.id}`);
        } catch (e: any) {
            error = e.message || 'Failed to create event';
        } finally {
            saving = false;
        }
    }
</script>

<svelte:head>
    <title>New Event - ZeroPool Admin</title>
</svelte:head>

<div class="p-6 lg:p-8">
<div class="max-w-2xl mx-auto space-y-6">
    <div class="flex items-center gap-3">
        <a href="/admin/events" class="text-muted-foreground hover:text-foreground transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
        </a>
        <h1 class="text-2xl font-semibold">New Event</h1>
    </div>

    {#if error}
        <div class="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
            {error}
        </div>
    {/if}

    <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-6">
        <div class="card p-6 space-y-4">
            <h3 class="font-medium">Basic Information</h3>
            
            <div>
                <label for="name" class="block text-sm font-medium mb-1.5">Event Name</label>
                <input 
                    type="text" 
                    id="name" 
                    bind:value={form.name}
                    oninput={handleNameChange}
                    class="input" 
                    placeholder="CTF 2025 Finals"
                    required 
                />
            </div>

            <div>
                <label for="slug" class="block text-sm font-medium mb-1.5">URL Slug</label>
                <div class="flex items-center gap-2">
                    <span class="text-sm text-muted-foreground">/events/</span>
                    <input 
                        type="text" 
                        id="slug" 
                        bind:value={form.slug}
                        class="input flex-1" 
                        placeholder="ctf-2025-finals"
                        pattern="[a-z0-9-]+"
                        required 
                    />
                </div>
                <p class="text-xs text-muted-foreground mt-1">
                    Only lowercase letters, numbers, and hyphens
                </p>
            </div>

            <div>
                <label for="description" class="block text-sm font-medium mb-1.5">Description</label>
                <textarea 
                    id="description" 
                    bind:value={form.description}
                    class="input" 
                    rows="3"
                    placeholder="Brief description of your event..."
                ></textarea>
            </div>

            <label class="flex items-center gap-3 p-3 bg-muted/50 rounded-lg cursor-pointer">
                <input type="checkbox" bind:checked={form.is_import_only} class="rounded" />
                <div>
                    <div class="text-sm font-medium">Import Only Mode</div>
                    <div class="text-xs text-muted-foreground">
                        Skip registration, just import participants for prize distribution
                    </div>
                </div>
            </label>
        </div>

        {#if !form.is_import_only}
            <div class="card p-6 space-y-4">
                <h3 class="font-medium">Schedule</h3>
                
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label for="reg-open" class="block text-sm font-medium mb-1.5">Registration Opens</label>
                        <input type="datetime-local" id="reg-open" bind:value={form.registration_open} class="input" />
                    </div>
                    <div>
                        <label for="reg-close" class="block text-sm font-medium mb-1.5">Registration Closes</label>
                        <input type="datetime-local" id="reg-close" bind:value={form.registration_close} class="input" />
                    </div>
                    <div>
                        <label for="start" class="block text-sm font-medium mb-1.5">Event Starts</label>
                        <input type="datetime-local" id="start" bind:value={form.start_date} class="input" />
                    </div>
                    <div>
                        <label for="end" class="block text-sm font-medium mb-1.5">Event Ends</label>
                        <input type="datetime-local" id="end" bind:value={form.end_date} class="input" />
                    </div>
                </div>
            </div>

            <div class="card p-6 space-y-4">
                <h3 class="font-medium">Team Settings</h3>
                
                <label class="flex items-center gap-3">
                    <input type="checkbox" bind:checked={form.team_mode} class="rounded" />
                    <span class="text-sm">Enable team mode</span>
                </label>

                {#if form.team_mode}
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label for="min-team" class="block text-sm font-medium mb-1.5">Min Team Size</label>
                            <input type="number" id="min-team" bind:value={form.min_team_size} class="input" min="1" />
                        </div>
                        <div>
                            <label for="max-team" class="block text-sm font-medium mb-1.5">Max Team Size</label>
                            <input type="number" id="max-team" bind:value={form.max_team_size} class="input" min="1" />
                        </div>
                    </div>
                {/if}

                <div>
                    <label for="max-participants" class="block text-sm font-medium mb-1.5">Max Participants</label>
                    <input 
                        type="number" 
                        id="max-participants" 
                        bind:value={form.max_participants} 
                        class="input" 
                        placeholder="Leave empty for unlimited" 
                    />
                </div>
            </div>
        {/if}

        <div class="card p-6 space-y-4">
            <h3 class="font-medium">CTFd Integration (Optional)</h3>
            <p class="text-sm text-muted-foreground -mt-2">
                Connect to sync results automatically after the competition
            </p>
            
            <div>
                <label for="ctfd-url" class="block text-sm font-medium mb-1.5">CTFd URL</label>
                <input 
                    type="url" 
                    id="ctfd-url" 
                    bind:value={form.ctfd_url}
                    class="input" 
                    placeholder="https://ctf.example.com" 
                />
            </div>

            <div>
                <label for="ctfd-key" class="block text-sm font-medium mb-1.5">CTFd API Key</label>
                <input 
                    type="password" 
                    id="ctfd-key" 
                    bind:value={form.ctfd_api_key}
                    class="input" 
                    placeholder="ctfd_xxx..." 
                />
                <p class="text-xs text-muted-foreground mt-1">
                    Generate from CTFd Admin &gt; Config &gt; Access Tokens
                </p>
            </div>
        </div>

        <div class="flex items-center justify-end gap-3">
            <a href="/admin/events" class="btn btn-ghost">Cancel</a>
            <button type="submit" disabled={saving} class="btn btn-primary">
                {saving ? 'Creating...' : 'Create Event'}
            </button>
        </div>
    </form>
</div>
</div>
