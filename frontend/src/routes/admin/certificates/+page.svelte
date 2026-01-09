<script lang="ts">
    import { onMount } from 'svelte';
    import { api, type CertificateTemplate, type Event } from '$lib/api';

    let templates = $state<CertificateTemplate[]>([]);
    let events = $state<Event[]>([]);
    let loading = $state(true);
    let error = $state('');
    
    let showModal = $state(false);
    let editingTemplate = $state<CertificateTemplate | null>(null);
    let saving = $state(false);
    let uploading = $state(false);
    
    let form = $state({
        name: '',
        event_id: '' as string | number,
        background_image: '',
        output_format: 'png' as 'png' | 'pdf',
        width: 1920,
        height: 1080,
        text_zones: [] as Array<{
            id: string;
            field: string;
            x: number;
            y: number;
            font_size: number;
            font_family: string;
            color: string;
            alignment: 'left' | 'center' | 'right';
        }>
    });

    let previewImage = $state<string | null>(null);
    let selectedZone = $state<string | null>(null);
    let isDragging = $state(false);

    const availableFields = [
        { value: 'participant_name', label: 'Participant Name' },
        { value: 'team_name', label: 'Team Name' },
        { value: 'event_name', label: 'Event Name' },
        { value: 'rank', label: 'Rank/Position' },
        { value: 'score', label: 'Score' },
        { value: 'date', label: 'Date' },
        { value: 'verification_code', label: 'Verification Code' },
        { value: 'custom', label: 'Custom Text' }
    ];

    const fontFamilies = [
        'Inter',
        'Roboto',
        'Open Sans',
        'Montserrat',
        'Playfair Display',
        'Georgia',
        'Times New Roman'
    ];

    onMount(async () => {
        await Promise.all([loadTemplates(), loadEvents()]);
    });

    async function loadTemplates() {
        loading = true;
        error = '';
        try {
            templates = await api.admin.certificateTemplates.list();
        } catch (e: any) {
            error = e.message || 'Failed to load templates';
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

    function openAddModal() {
        editingTemplate = null;
        form = {
            name: '',
            event_id: '',
            background_image: '',
            output_format: 'png',
            width: 1920,
            height: 1080,
            text_zones: []
        };
        previewImage = null;
        selectedZone = null;
        showModal = true;
    }

    function openEditModal(template: CertificateTemplate) {
        editingTemplate = template;
        form = {
            name: template.name,
            event_id: template.event_id || '',
            background_image: template.background_image,
            output_format: template.output_format as 'png' | 'pdf',
            width: template.width,
            height: template.height,
            text_zones: template.text_zones.map((z: any, i: number) => ({
                ...z,
                id: z.id || `zone-${i}`
            }))
        };
        previewImage = template.background_image;
        selectedZone = null;
        showModal = true;
    }

    async function handleImageUpload(event: Event & { currentTarget: HTMLInputElement }) {
        const file = event.currentTarget.files?.[0];
        if (!file) return;
        
        if (!file.type.startsWith('image/')) {
            error = 'Please upload an image file';
            return;
        }

        uploading = true;
        try {
            // Create FormData for upload
            const formData = new FormData();
            formData.append('file', file);
            
            // Upload to server
            const response = await fetch('/api/admin/upload', {
                method: 'POST',
                body: formData,
                credentials: 'include'
            });
            
            if (!response.ok) {
                throw new Error('Upload failed');
            }
            
            const result = await response.json();
            form.background_image = result.url;
            
            // Show preview
            const reader = new FileReader();
            reader.onload = (e) => {
                previewImage = e.target?.result as string;
            };
            reader.readAsDataURL(file);
        } catch (e: any) {
            // Fallback: use base64 for demo
            const reader = new FileReader();
            reader.onload = (e) => {
                const base64 = e.target?.result as string;
                form.background_image = base64;
                previewImage = base64;
            };
            reader.readAsDataURL(file);
        } finally {
            uploading = false;
        }
    }

    function addTextZone() {
        const id = `zone-${Date.now()}`;
        form.text_zones = [...form.text_zones, {
            id,
            field: 'participant_name',
            x: 50,
            y: 50,
            font_size: 48,
            font_family: 'Inter',
            color: '#000000',
            alignment: 'center'
        }];
        selectedZone = id;
    }

    function removeTextZone(id: string) {
        form.text_zones = form.text_zones.filter(z => z.id !== id);
        if (selectedZone === id) selectedZone = null;
    }

    function updateZone(id: string, updates: Partial<typeof form.text_zones[0]>) {
        form.text_zones = form.text_zones.map(z => 
            z.id === id ? { ...z, ...updates } : z
        );
    }

    async function handleSubmit() {
        if (!form.name || !form.background_image) {
            error = 'Please provide a name and upload a background image';
            return;
        }
        
        saving = true;
        error = '';
        try {
            const payload = {
                ...form,
                event_id: form.event_id ? String(form.event_id) : null,
                text_zones: form.text_zones.map(({ id, ...zone }) => zone)
            };
            
            if (editingTemplate) {
                await api.admin.certificateTemplates.update(editingTemplate.id, payload);
            } else {
                await api.admin.certificateTemplates.create(payload);
            }
            showModal = false;
            await loadTemplates();
        } catch (e: any) {
            error = e.message || 'Failed to save template';
        } finally {
            saving = false;
        }
    }

    async function handleDelete(id: string) {
        if (!confirm('Are you sure you want to delete this certificate template?')) return;
        
        try {
            await api.admin.certificateTemplates.delete(id);
            await loadTemplates();
        } catch (e: any) {
            error = e.message || 'Failed to delete template';
        }
    }

    function getEventName(eventId: string | null): string {
        if (!eventId) return 'Global';
        return events.find(e => e.id === eventId)?.name || 'Unknown';
    }

    function getFieldLabel(field: string): string {
        return availableFields.find(f => f.value === field)?.label || field;
    }
</script>

<svelte:head>
    <title>Certificate Templates - ZeroPool Admin</title>
</svelte:head>

<div class="p-6 lg:p-8">
    <div class="space-y-6">
        <div class="flex items-center justify-between">
            <div>
                <h1 class="text-2xl font-semibold">Certificate Templates</h1>
                <p class="text-sm text-muted-foreground mt-1">
                    Design certificates with custom text placement
                </p>
            </div>
            <button onclick={openAddModal} class="btn btn-primary">
                New Template
            </button>
        </div>

    {#if error && !showModal}
        <div class="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
            {error}
        </div>
    {/if}

    {#if loading}
        <div class="card p-12 text-center">
            <div class="animate-pulse text-muted-foreground">Loading templates...</div>
        </div>
    {:else if templates.length === 0}
        <div class="card p-12 text-center">
            <div class="text-muted-foreground mb-4">No certificate templates yet</div>
            <button onclick={openAddModal} class="btn btn-primary">
                Create Your First Template
            </button>
        </div>
    {:else}
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {#each templates as template}
                <div class="card overflow-hidden">
                    <div class="aspect-video bg-muted relative">
                        {#if template.background_image}
                            <img 
                                src={template.background_image} 
                                alt={template.name}
                                class="w-full h-full object-cover"
                            />
                        {:else}
                            <div class="absolute inset-0 flex items-center justify-center text-muted-foreground">
                                No preview
                            </div>
                        {/if}
                    </div>
                    <div class="p-4">
                        <div class="flex items-start justify-between">
                            <div>
                                <h3 class="font-medium">{template.name}</h3>
                                <p class="text-sm text-muted-foreground">
                                    {getEventName(template.event_id)} | {template.output_format.toUpperCase()}
                                </p>
                                <p class="text-xs text-muted-foreground mt-1">
                                    {template.text_zones.length} text zone{template.text_zones.length !== 1 ? 's' : ''}
                                </p>
                            </div>
                            <div class="flex items-center gap-1">
                                <button 
                                    onclick={() => openEditModal(template)}
                                    class="btn btn-ghost btn-sm"
                                >
                                    Edit
                                </button>
                                <button 
                                    onclick={() => handleDelete(template.id)}
                                    class="btn btn-ghost btn-sm text-destructive"
                                >
                                    Delete
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            {/each}
        </div>
    {/if}
    </div>
</div>

{#if showModal}
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div class="bg-card rounded-xl shadow-xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
            <div class="px-6 py-4 border-b border-border flex items-center justify-between">
                <h2 class="text-lg font-semibold">
                    {editingTemplate ? 'Edit Template' : 'New Certificate Template'}
                </h2>
                <button onclick={() => showModal = false} class="btn btn-ghost btn-sm">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
            
            <div class="flex-1 overflow-y-auto p-6">
                {#if error}
                    <div class="bg-destructive/10 text-destructive px-4 py-3 rounded-lg mb-4">
                        {error}
                    </div>
                {/if}
                
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Left: Settings -->
                    <div class="space-y-4">
                        <div>
                            <label for="name" class="block text-sm font-medium mb-1.5">
                                Template Name
                            </label>
                            <input
                                type="text"
                                id="name"
                                bind:value={form.name}
                                class="input"
                                placeholder="Participation Certificate"
                                required
                            />
                        </div>

                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label for="event" class="block text-sm font-medium mb-1.5">
                                    Event (Optional)
                                </label>
                                <select id="event" bind:value={form.event_id} class="input">
                                    <option value="">Global Template</option>
                                    {#each events as event}
                                        <option value={event.id}>{event.name}</option>
                                    {/each}
                                </select>
                            </div>
                            <div>
                                <label for="format" class="block text-sm font-medium mb-1.5">
                                    Output Format
                                </label>
                                <select id="format" bind:value={form.output_format} class="input">
                                    <option value="png">PNG</option>
                                    <option value="pdf">PDF</option>
                                </select>
                            </div>
                        </div>

                        <div>
                            <label class="block text-sm font-medium mb-1.5">
                                Background Image
                            </label>
                            <div class="flex items-center gap-3">
                                <label class="btn btn-secondary cursor-pointer">
                                    {uploading ? 'Uploading...' : 'Upload Image'}
                                    <input 
                                        type="file" 
                                        accept="image/*" 
                                        onchange={handleImageUpload}
                                        class="hidden"
                                        disabled={uploading}
                                    />
                                </label>
                                {#if form.background_image}
                                    <span class="text-sm text-muted-foreground">Image uploaded</span>
                                {/if}
                            </div>
                            <p class="text-xs text-muted-foreground mt-1">
                                Recommended: 1920x1080 for landscape, 1080x1920 for portrait
                            </p>
                        </div>

                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label for="width" class="block text-sm font-medium mb-1.5">
                                    Width (px)
                                </label>
                                <input
                                    type="number"
                                    id="width"
                                    bind:value={form.width}
                                    class="input"
                                    min="100"
                                    max="4000"
                                />
                            </div>
                            <div>
                                <label for="height" class="block text-sm font-medium mb-1.5">
                                    Height (px)
                                </label>
                                <input
                                    type="number"
                                    id="height"
                                    bind:value={form.height}
                                    class="input"
                                    min="100"
                                    max="4000"
                                />
                            </div>
                        </div>

                        <hr class="border-border" />

                        <div>
                            <div class="flex items-center justify-between mb-3">
                                <h3 class="text-sm font-medium">Text Zones</h3>
                                <button onclick={addTextZone} class="btn btn-secondary btn-sm">
                                    Add Zone
                                </button>
                            </div>
                            
                            {#if form.text_zones.length === 0}
                                <p class="text-sm text-muted-foreground text-center py-4">
                                    No text zones. Click "Add Zone" to create one.
                                </p>
                            {:else}
                                <div class="space-y-3 max-h-64 overflow-y-auto">
                                    {#each form.text_zones as zone}
                                        <div 
                                            class="p-3 rounded-lg border transition-colors cursor-pointer {selectedZone === zone.id ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'}"
                                            onclick={() => selectedZone = zone.id}
                                        >
                                            <div class="flex items-center justify-between mb-2">
                                                <select 
                                                    bind:value={zone.field}
                                                    class="input text-sm py-1"
                                                    onclick={(e) => e.stopPropagation()}
                                                >
                                                    {#each availableFields as field}
                                                        <option value={field.value}>{field.label}</option>
                                                    {/each}
                                                </select>
                                                <button 
                                                    onclick={(e) => { e.stopPropagation(); removeTextZone(zone.id); }}
                                                    class="btn btn-ghost btn-sm text-destructive"
                                                >
                                                    Remove
                                                </button>
                                            </div>
                                            
                                            {#if selectedZone === zone.id}
                                                <div class="grid grid-cols-2 gap-2 mt-2">
                                                    <div>
                                                        <label class="text-xs text-muted-foreground">X (%)</label>
                                                        <input
                                                            type="number"
                                                            bind:value={zone.x}
                                                            class="input text-sm py-1"
                                                            min="0"
                                                            max="100"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label class="text-xs text-muted-foreground">Y (%)</label>
                                                        <input
                                                            type="number"
                                                            bind:value={zone.y}
                                                            class="input text-sm py-1"
                                                            min="0"
                                                            max="100"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label class="text-xs text-muted-foreground">Font Size</label>
                                                        <input
                                                            type="number"
                                                            bind:value={zone.font_size}
                                                            class="input text-sm py-1"
                                                            min="8"
                                                            max="200"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label class="text-xs text-muted-foreground">Color</label>
                                                        <input
                                                            type="color"
                                                            bind:value={zone.color}
                                                            class="input h-8 p-1"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label class="text-xs text-muted-foreground">Font</label>
                                                        <select bind:value={zone.font_family} class="input text-sm py-1">
                                                            {#each fontFamilies as font}
                                                                <option value={font}>{font}</option>
                                                            {/each}
                                                        </select>
                                                    </div>
                                                    <div>
                                                        <label class="text-xs text-muted-foreground">Align</label>
                                                        <select bind:value={zone.alignment} class="input text-sm py-1">
                                                            <option value="left">Left</option>
                                                            <option value="center">Center</option>
                                                            <option value="right">Right</option>
                                                        </select>
                                                    </div>
                                                </div>
                                            {/if}
                                        </div>
                                    {/each}
                                </div>
                            {/if}
                        </div>
                    </div>

                    <!-- Right: Preview -->
                    <div>
                        <h3 class="text-sm font-medium mb-3">Preview</h3>
                        <div 
                            class="relative bg-muted rounded-lg overflow-hidden"
                            style="aspect-ratio: {form.width}/{form.height};"
                        >
                            {#if previewImage}
                                <img 
                                    src={previewImage} 
                                    alt="Certificate preview"
                                    class="w-full h-full object-contain"
                                />
                                <!-- Text zone markers -->
                                {#each form.text_zones as zone}
                                    <div 
                                        class="absolute transform -translate-x-1/2 -translate-y-1/2 pointer-events-none
                                               {selectedZone === zone.id ? 'ring-2 ring-primary' : ''}"
                                        style="left: {zone.x}%; top: {zone.y}%; font-size: {zone.font_size * 0.3}px; color: {zone.color}; font-family: {zone.font_family}; text-align: {zone.alignment};"
                                    >
                                        <div class="bg-black/50 px-2 py-1 rounded text-white text-xs whitespace-nowrap">
                                            {getFieldLabel(zone.field)}
                                        </div>
                                    </div>
                                {/each}
                            {:else}
                                <div class="absolute inset-0 flex items-center justify-center text-muted-foreground">
                                    Upload an image to preview
                                </div>
                            {/if}
                        </div>
                        <p class="text-xs text-muted-foreground mt-2 text-center">
                            Text zones are shown at their approximate positions
                        </p>
                    </div>
                </div>
            </div>

            <div class="px-6 py-4 border-t border-border flex justify-end gap-3">
                <button onclick={() => showModal = false} class="btn btn-ghost">
                    Cancel
                </button>
                <button 
                    onclick={handleSubmit}
                    disabled={saving}
                    class="btn btn-primary"
                >
                    {saving ? 'Saving...' : (editingTemplate ? 'Update Template' : 'Create Template')}
                </button>
            </div>
        </div>
    </div>
{/if}
