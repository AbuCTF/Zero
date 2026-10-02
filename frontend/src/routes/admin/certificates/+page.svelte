<script lang="ts">
    import { onMount } from 'svelte';
    import { api, type CertificateTemplate, type Event as CtfEvent } from '$lib/api';

    type Zone = {
        id: string;
        field: string;
        x: number;
        y: number;
        width: number;
        height: number;
        font_size: number;
        font_family: string;
        color: string;
        alignment: 'left' | 'center' | 'right';
        is_percentage: boolean;
    };

    type DesignerForm = {
        name: string;
        event_id: string | number;
        background_image: string;
        output_format: 'png' | 'pdf';
        certificate_prefix: string;
        width: number;
        height: number;
        text_zones: Zone[];
        qr_zone: { x: number; y: number; size: number; is_percentage: boolean } | null;
        is_default: boolean;
    };

    const availableFields = [
        { value: 'participant_name', label: 'Participant Name' },
        { value: 'team_name', label: 'Team Name' },
        { value: 'event_name', label: 'Event Name' },
        { value: 'rank', label: 'Rank/Position' },
        { value: 'score', label: 'Score' },
        { value: 'date', label: 'Date' },
        { value: 'verification_code', label: 'Full Certificate ID' },
        { value: 'verification_suffix', label: 'Certificate ID Suffix' }
    ];

    const fontFamilies = [
        { value: 'Exo2', label: 'Exo 2' },
        { value: 'SpaceMono-Regular', label: 'Space Mono' },
        { value: 'DejaVuSans', label: 'DejaVu Sans' }
    ];

    const sampleValues: Record<string, string> = {
        participant_name: 'Participant Name',
        team_name: 'Team Name',
        event_name: 'H7CTF 2026',
        rank: '#12',
        score: '1337',
        date: 'September 27, 2026',
        verification_code: 'H7CTF26-ABCD-EFGH-JKLM',
        verification_suffix: 'ABCD-EFGH-JKLM'
    };

    function emptyForm(): DesignerForm {
        return {
            name: '',
            event_id: '',
            background_image: '',
            output_format: 'png',
            certificate_prefix: 'CERT',
            width: 1920,
            height: 1080,
            text_zones: [],
            qr_zone: null,
            is_default: false
        };
    }

    let templates = $state<CertificateTemplate[]>([]);
    let events = $state<CtfEvent[]>([]);
    let loading = $state(true);
    let error = $state('');
    let showModal = $state(false);
    let editingTemplate = $state<CertificateTemplate | null>(null);
    let saving = $state(false);
    let uploading = $state(false);
    let issuingTemplate = $state<string | null>(null);
    let notice = $state('');
    let form = $state<DesignerForm>(emptyForm());
    let previewImage = $state<string | null>(null);
    let selectedZone = $state<string | null>(null);
    let previewCanvas = $state<HTMLDivElement>();
    let dragging = $state<{ kind: 'text'; id: string } | { kind: 'qr' } | null>(null);
    let testTemplate = $state<CertificateTemplate | null>(null);
    let testName = $state('Sample Participant');
    let testPreviewUrl = $state<string | null>(null);
    let testRendering = $state(false);
    let showAlignmentGrid = $state(true);
    let snapStep = $state(0.25);
    let guideX = $state(50);
    let guideY = $state(50);

    const MAX_CERTIFICATE_NAME_LENGTH = 80;

    onMount(() => {
        const move = (event: PointerEvent) => moveDesignerItem(event);
        const stop = () => dragging = null;
        window.addEventListener('pointermove', move);
        window.addEventListener('pointerup', stop);
        Promise.all([loadTemplates(), loadEvents()]);
        return () => {
            window.removeEventListener('pointermove', move);
            window.removeEventListener('pointerup', stop);
        };
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
        } catch (e: any) {
            error = e.message || 'Failed to load events';
        }
    }

    function openAddModal() {
        editingTemplate = null;
        form = emptyForm();
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
            certificate_prefix: template.certificate_prefix || 'CERT',
            width: template.width,
            height: template.height,
            text_zones: template.text_zones.map((zone, index) => ({
                id: zone.id || `zone-${index}`,
                field: zone.field,
                x: zone.x,
                y: zone.y,
                width: zone.width ?? 70,
                height: zone.height ?? 10,
                font_size: zone.font_size ?? 48,
                font_family: zone.font_family ?? 'Exo2',
                color: zone.font_color ?? zone.color ?? '#000000',
                alignment: zone.alignment ?? 'center',
                is_percentage: zone.is_percentage ?? true
            })),
            qr_zone: template.qr_zone ? {
                x: template.qr_zone.x,
                y: template.qr_zone.y,
                size: template.qr_zone.size,
                is_percentage: template.qr_zone.is_percentage ?? true
            } : null,
            is_default: template.is_default
        };
        previewImage = template.background_image;
        selectedZone = null;
        showModal = true;
    }

    function handleImageUpload(event: Event & { currentTarget: HTMLInputElement }) {
        const file = event.currentTarget.files?.[0];
        if (!file) return;
        if (!file.type.startsWith('image/')) {
            error = 'Please upload a PNG or JPEG image';
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            error = 'Certificate artwork must be 10 MB or smaller';
            return;
        }

        uploading = true;
        const reader = new FileReader();
        reader.onload = (readEvent) => {
            const imageData = readEvent.target?.result as string;
            const image = new Image();
            image.onload = () => {
                form.width = image.naturalWidth;
                form.height = image.naturalHeight;
                form.background_image = imageData;
                previewImage = imageData;
                uploading = false;
            };
            image.onerror = () => {
                error = 'The selected image could not be read';
                uploading = false;
            };
            image.src = imageData;
        };
        reader.onerror = () => {
            error = 'The selected image could not be read';
            uploading = false;
        };
        reader.readAsDataURL(file);
    }

    function addTextZone() {
        const id = `zone-${Date.now()}`;
        form.text_zones = [...form.text_zones, {
            id,
            field: 'participant_name',
            x: 50,
            y: 40,
            width: 70,
            height: 10,
            font_size: 54,
            font_family: 'Exo2',
            color: '#000000',
            alignment: 'center',
            is_percentage: true
        }];
        selectedZone = id;
    }

    function removeTextZone(id: string) {
        form.text_zones = form.text_zones.filter((zone) => zone.id !== id);
        if (selectedZone === id) selectedZone = null;
    }

    function updateZone(id: string, updates: Partial<Zone>) {
        form.text_zones = form.text_zones.map((zone) => zone.id === id ? { ...zone, ...updates } : zone);
    }

    function toggleQrZone() {
        form.qr_zone = form.qr_zone ? null : { x: 50, y: 68, size: 11, is_percentage: true };
    }

    function beginTextDrag(event: PointerEvent, id: string) {
        event.preventDefault();
        selectedZone = id;
        dragging = { kind: 'text', id };
    }

    function beginQrDrag(event: PointerEvent) {
        event.preventDefault();
        selectedZone = null;
        dragging = { kind: 'qr' };
    }

    function moveDesignerItem(event: PointerEvent) {
        if (!dragging || !previewCanvas) return;
        const bounds = previewCanvas.getBoundingClientRect();
        const rawX = Math.max(0, Math.min(100, ((event.clientX - bounds.left) / bounds.width) * 100));
        const rawY = Math.max(0, Math.min(100, ((event.clientY - bounds.top) / bounds.height) * 100));
        const x = Number((Math.round(rawX / snapStep) * snapStep).toFixed(2));
        const y = Number((Math.round(rawY / snapStep) * snapStep).toFixed(2));
        if (dragging.kind === 'qr') {
            if (form.qr_zone) {
                form.qr_zone.x = Number(x.toFixed(2));
                form.qr_zone.y = Number(y.toFixed(2));
            }
            return;
        }
        updateZone(dragging.id, { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)) });
    }

    function alignSelectedZone(axis: 'x' | 'y') {
        if (!selectedZone) return;
        updateZone(selectedZone, axis === 'x' ? { x: guideX } : { y: guideY });
    }

    function nudgeZone(event: KeyboardEvent, id: string) {
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
        event.preventDefault();
        const zone = form.text_zones.find((item) => item.id === id);
        if (!zone) return;
        const amount = event.shiftKey ? 1 : 0.1;
        const updates: Partial<Zone> = {};
        if (event.key === 'ArrowLeft') updates.x = Math.max(0, Number((zone.x - amount).toFixed(2)));
        if (event.key === 'ArrowRight') updates.x = Math.min(100, Number((zone.x + amount).toFixed(2)));
        if (event.key === 'ArrowUp') updates.y = Math.max(0, Number((zone.y - amount).toFixed(2)));
        if (event.key === 'ArrowDown') updates.y = Math.min(100, Number((zone.y + amount).toFixed(2)));
        updateZone(id, updates);
    }

    function zoneTransform(alignment: Zone['alignment']): string {
        if (alignment === 'center') return 'translateX(-50%)';
        if (alignment === 'right') return 'translateX(-100%)';
        return 'none';
    }

    function qrWidthPercent(): number {
        if (!form.qr_zone) return 0;
        return form.qr_zone.size * (Math.min(form.width, form.height) / form.width);
    }

    function sampleValue(field: string): string {
        if (field === 'verification_code') return `${form.certificate_prefix || 'CERT'}-ABCD-EFGH-JKLM`;
        return sampleValues[field] || field;
    }

    async function handleSubmit() {
        if (!form.name.trim() || !form.background_image) {
            error = 'Add a template name and background image';
            return;
        }
        if (form.text_zones.length === 0) {
            error = 'Add at least one text zone';
            return;
        }

        saving = true;
        error = '';
        try {
            const payload = {
                ...form,
                name: form.name.trim(),
                event_id: form.event_id ? String(form.event_id) : null,
                text_zones: form.text_zones.map((zone) => ({
                    ...zone,
                    font_color: zone.color
                }))
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
        if (!confirm('Delete this certificate template?')) return;
        try {
            await api.admin.certificateTemplates.delete(id);
            await loadTemplates();
        } catch (e: any) {
            error = e.message || 'Failed to delete template';
        }
    }

    async function issueCertificates(template: CertificateTemplate) {
        if (!template.event_id || !template.is_default) return;
        if (!confirm(`Issue ${template.name} to eligible participants? Existing certificates will be kept.`)) return;
        issuingTemplate = template.id;
        error = '';
        notice = '';
        try {
            const result = await api.admin.certificateTemplates.issue(template.event_id);
            notice = result.message;
        } catch (e: any) {
            error = e.message || 'Failed to issue certificates';
        } finally {
            issuingTemplate = null;
        }
    }

    function getEventName(eventId: string | null | undefined): string {
        if (!eventId) return 'Global';
        return events.find((event) => event.id === eventId)?.name || 'Unknown';
    }

    async function openTestPreview(template: CertificateTemplate) {
        closeTestPreview();
        testTemplate = template;
        testName = 'Sample Participant';
        await renderTestPreview();
    }

    function closeTestPreview() {
        if (testPreviewUrl) URL.revokeObjectURL(testPreviewUrl);
        testPreviewUrl = null;
        testTemplate = null;
    }

    async function renderTestPreview() {
        if (!testTemplate || !testName.trim()) return;
        testRendering = true;
        error = '';
        try {
            const blob = await api.admin.certificateTemplates.render(testTemplate.id, testName.trim(), 'png');
            if (testPreviewUrl) URL.revokeObjectURL(testPreviewUrl);
            testPreviewUrl = URL.createObjectURL(blob);
        } catch (e: any) {
            error = e.message || 'Failed to render certificate preview';
        } finally {
            testRendering = false;
        }
    }

    function downloadTestPreview() {
        if (!testPreviewUrl || !testTemplate) return;
        const link = document.createElement('a');
        link.href = testPreviewUrl;
        link.download = `${testTemplate.name.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').toLowerCase() || 'certificate'}-preview.png`;
        link.click();
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
                <p class="text-sm text-foreground-muted mt-1">
                    Upload artwork, place dynamic fields and publish certificates
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

    {#if notice && !showModal}
        <div class="bg-success/10 text-success px-4 py-3 rounded-lg">
            {notice}
        </div>
    {/if}

    {#if loading}
        <div class="card p-12 text-center">
            <div class="animate-pulse text-foreground-muted">Loading templates...</div>
        </div>
    {:else if templates.length === 0}
        <div class="card p-12 text-center">
            <div class="text-foreground-muted mb-4">No certificate templates yet</div>
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
                            <div class="absolute inset-0 flex items-center justify-center text-foreground-muted">
                                No preview
                            </div>
                        {/if}
                    </div>
                    <div class="p-4">
                        <div class="flex items-start justify-between">
                            <div>
                                <h3 class="font-medium">{template.name}</h3>
                                <p class="text-sm text-foreground-muted">
                                    {getEventName(template.event_id)} | {template.output_format.toUpperCase()}
                                </p>
                                <p class="text-xs text-foreground-muted mt-1">
                                    {template.text_zones.length} text zone{template.text_zones.length !== 1 ? 's' : ''}
                                </p>
                            </div>
                            <div class="flex items-center gap-1">
                                <button
                                    onclick={() => openTestPreview(template)}
                                    class="btn btn-ghost btn-sm"
                                >
                                    Test output
                                </button>
                                {#if template.event_id && template.is_default}
                                    <button
                                        onclick={() => issueCertificates(template)}
                                        class="btn btn-ghost btn-sm"
                                        disabled={issuingTemplate === template.id}
                                    >
                                        {issuingTemplate === template.id ? 'Issuing…' : 'Issue'}
                                    </button>
                                {/if}
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
        <div class="bg-card rounded-xl shadow-xl w-full max-w-7xl max-h-[94vh] overflow-hidden flex flex-col">
            <div class="px-6 py-4 border-b border-border flex items-center justify-between">
                <h2 class="text-lg font-semibold">
                    {editingTemplate ? 'Edit Template' : 'New Certificate Template'}
                </h2>
                <button onclick={() => showModal = false} class="btn btn-ghost btn-sm" aria-label="Close">
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
                
                <div class="grid grid-cols-1 xl:grid-cols-12 gap-6">
                    <div class="space-y-4 xl:col-span-5">
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

                        <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
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
                            <div>
                                <label for="certificate-prefix" class="block text-sm font-medium mb-1.5">
                                    Certificate ID Prefix
                                </label>
                                <input
                                    id="certificate-prefix"
                                    bind:value={form.certificate_prefix}
                                    class="input uppercase"
                                    minlength="2"
                                    maxlength="20"
                                    pattern="[A-Za-z0-9]+"
                                    placeholder="CERT"
                                    required
                                />
                            </div>
                        </div>

                        <div>
                            <label for="background-image" class="block text-sm font-medium mb-1.5">
                                Background Image
                            </label>
                            <div class="flex items-center gap-3">
                                <label class="btn btn-secondary cursor-pointer">
                                    {uploading ? 'Uploading...' : 'Upload Image'}
                                    <input
                                        type="file"
                                        id="background-image"
                                        accept="image/*"
                                        onchange={handleImageUpload}
                                        class="hidden"
                                        disabled={uploading}
                                    />
                                </label>
                                {#if form.background_image}
                                    <span class="text-sm text-foreground-muted">Image uploaded</span>
                                {/if}
                            </div>
                            <p class="text-xs text-foreground-muted mt-1">
                                Canvas size is detected from the image automatically.
                            </p>
                        </div>

                        <label class="flex items-start gap-3 rounded-lg border border-border p-3">
                            <input type="checkbox" bind:checked={form.is_default} class="mt-0.5 h-4 w-4" />
                            <span>
                                <span class="block text-sm font-medium">Default for this event</span>
                                <span class="block text-xs text-foreground-muted mt-0.5">Used when certificates are issued for this event.</span>
                            </span>
                        </label>

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
                                <p class="text-sm text-foreground-muted text-center py-4">
                                    No text zones. Click "Add Zone" to create one.
                                </p>
                            {:else}
                                <div class="space-y-3 max-h-[28rem] overflow-y-auto pr-1">
                                    {#each form.text_zones as zone}
                                        <div
                                            class="p-3 rounded-lg border transition-colors cursor-pointer {selectedZone === zone.id ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'}"
                                            role="button"
                                            tabindex="0"
                                            aria-label="Select text zone"
                                            onclick={() => selectedZone = zone.id}
                                            onkeydown={(e) => { if (e.key === 'Enter') selectedZone = zone.id; }}
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
                                                        <label for="{zone.id}-x" class="text-xs text-foreground-muted">X (%)</label>
                                                        <input
                                                            type="number"
                                                            id="{zone.id}-x"
                                                            bind:value={zone.x}
                                                            class="input text-sm py-1"
                                                            min="0"
                                                            max="100"
                                                            step="0.1"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label for="{zone.id}-y" class="text-xs text-foreground-muted">Y (%)</label>
                                                        <input
                                                            type="number"
                                                            id="{zone.id}-y"
                                                            bind:value={zone.y}
                                                            class="input text-sm py-1"
                                                            min="0"
                                                            max="100"
                                                            step="0.1"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label for="{zone.id}-width" class="text-xs text-foreground-muted">Max width (%)</label>
                                                        <input
                                                            type="number"
                                                            id="{zone.id}-width"
                                                            bind:value={zone.width}
                                                            class="input text-sm py-1"
                                                            min="1"
                                                            max="100"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label for="{zone.id}-color" class="text-xs text-foreground-muted">Color</label>
                                                        <input
                                                            type="color"
                                                            id="{zone.id}-color"
                                                            bind:value={zone.color}
                                                            class="input h-8 p-1"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label for="{zone.id}-font" class="text-xs text-foreground-muted">Font</label>
                                                        <select id="{zone.id}-font" bind:value={zone.font_family} class="input text-sm py-1">
                                                            {#each fontFamilies as font}
                                                                <option value={font.value}>{font.label}</option>
                                                            {/each}
                                                        </select>
                                                    </div>
                                                    <div>
                                                        <label for="{zone.id}-align" class="text-xs text-foreground-muted">Align</label>
                                                        <select id="{zone.id}-align" bind:value={zone.alignment} class="input text-sm py-1">
                                                            <option value="left">Left</option>
                                                            <option value="center">Center</option>
                                                            <option value="right">Right</option>
                                                        </select>
                                                    </div>
                                                    <div class="col-span-2">
                                                        <div class="flex items-center justify-between">
                                                            <label for="{zone.id}-font-size" class="text-xs text-foreground-muted">Font size</label>
                                                            <span class="text-xs tabular-nums text-foreground-muted">{zone.font_size}px</span>
                                                        </div>
                                                        <input
                                                            type="range"
                                                            id="{zone.id}-font-size"
                                                            bind:value={zone.font_size}
                                                            class="w-full accent-primary"
                                                            min="8"
                                                            max="200"
                                                        />
                                                    </div>
                                                </div>
                                            {/if}
                                        </div>
                                    {/each}
                                </div>
                            {/if}
                        </div>

                        <div class="rounded-lg border border-border p-3">
                            <div class="flex items-center justify-between gap-3">
                                <div>
                                    <div class="text-sm font-medium">Verification QR</div>
                                    <div class="text-xs text-foreground-muted mt-0.5">Links to the public certificate record.</div>
                                </div>
                                <button onclick={toggleQrZone} class="btn btn-secondary btn-sm">
                                    {form.qr_zone ? 'Remove' : 'Add QR'}
                                </button>
                            </div>
                            {#if form.qr_zone}
                                <div class="grid grid-cols-3 gap-2 mt-3">
                                    <div>
                                        <label for="qr-x" class="text-xs text-foreground-muted">X (%)</label>
                                        <input id="qr-x" type="number" bind:value={form.qr_zone.x} min="0" max="100" class="input text-sm py-1" />
                                    </div>
                                    <div>
                                        <label for="qr-y" class="text-xs text-foreground-muted">Y (%)</label>
                                        <input id="qr-y" type="number" bind:value={form.qr_zone.y} min="0" max="100" class="input text-sm py-1" />
                                    </div>
                                    <div>
                                        <label for="qr-size" class="text-xs text-foreground-muted">Size (%)</label>
                                        <input id="qr-size" type="number" bind:value={form.qr_zone.size} min="2" max="40" class="input text-sm py-1" />
                                    </div>
                                </div>
                            {/if}
                        </div>
                    </div>

                    <div class="xl:col-span-7">
                        <div class="mb-3 space-y-3">
                            <div class="flex items-center justify-between">
                                <h3 class="text-sm font-medium">Layout preview</h3>
                                <span class="text-xs text-foreground-muted">Drag, use coordinates, or nudge with arrow keys</span>
                            </div>
                            <div class="grid grid-cols-2 gap-2 rounded-lg border border-border bg-muted/30 p-3 sm:grid-cols-4">
                                <label class="flex items-center gap-2 text-xs font-medium">
                                    <input type="checkbox" bind:checked={showAlignmentGrid} />
                                    Grid and guides
                                </label>
                                <label class="text-xs text-foreground-muted">
                                    Snap
                                    <select bind:value={snapStep} class="input mt-1 py-1 text-sm">
                                        <option value={0.1}>0.1%</option>
                                        <option value={0.25}>0.25%</option>
                                        <option value={0.5}>0.5%</option>
                                        <option value={1}>1%</option>
                                    </select>
                                </label>
                                <label class="text-xs text-foreground-muted">
                                    Vertical guide X
                                    <div class="mt-1 flex gap-1">
                                        <input type="number" bind:value={guideX} min="0" max="100" step="0.1" class="input py-1 text-sm" />
                                        <button type="button" class="btn btn-secondary btn-sm" onclick={() => alignSelectedZone('x')} disabled={!selectedZone}>Align</button>
                                    </div>
                                </label>
                                <label class="text-xs text-foreground-muted">
                                    Horizontal guide Y
                                    <div class="mt-1 flex gap-1">
                                        <input type="number" bind:value={guideY} min="0" max="100" step="0.1" class="input py-1 text-sm" />
                                        <button type="button" class="btn btn-secondary btn-sm" onclick={() => alignSelectedZone('y')} disabled={!selectedZone}>Align</button>
                                    </div>
                                </label>
                            </div>
                        </div>
                        <div 
                            bind:this={previewCanvas}
                            class="certificate-canvas relative bg-muted rounded-lg overflow-hidden border border-border select-none"
                            style="aspect-ratio: {form.width}/{form.height}; container-type: inline-size; background-image: {showAlignmentGrid ? 'linear-gradient(to right, color-mix(in srgb, currentColor 12%, transparent) 1px, transparent 1px), linear-gradient(to bottom, color-mix(in srgb, currentColor 12%, transparent) 1px, transparent 1px)' : 'none'}; background-size: 5% 5%;"
                        >
                            {#if previewImage}
                                <img 
                                    src={previewImage} 
                                    alt="Certificate preview"
                                    class="w-full h-full object-contain"
                                />
                                {#each form.text_zones as zone}
                                    <button
                                        type="button"
                                        class="absolute cursor-move whitespace-nowrap border border-transparent bg-transparent p-0 leading-tight {selectedZone === zone.id ? 'outline outline-2 outline-primary outline-offset-2' : 'hover:outline hover:outline-1 hover:outline-primary/70'}"
                                        style="left: {zone.x}%; top: {zone.y}%; width: {zone.width}%; transform: {zoneTransform(zone.alignment)}; font-size: {zone.font_size / form.width * 100}cqw; color: {zone.color}; font-family: {zone.font_family}; text-align: {zone.alignment};"
                                        onpointerdown={(event) => beginTextDrag(event, zone.id)}
                                        onkeydown={(event) => nudgeZone(event, zone.id)}
                                        aria-label="Move {availableFields.find((field) => field.value === zone.field)?.label || zone.field}"
                                    >
                                        {sampleValue(zone.field)}
                                    </button>
                                {/each}
                                {#if form.qr_zone}
                                    <button
                                        type="button"
                                        class="absolute grid cursor-move place-items-center border-2 border-primary bg-white text-[8px] font-semibold uppercase tracking-widest text-black"
                                        style="left: {form.qr_zone.x}%; top: {form.qr_zone.y}%; width: {qrWidthPercent()}%; aspect-ratio: 1;"
                                        onpointerdown={beginQrDrag}
                                        aria-label="Move verification QR"
                                    >
                                        QR
                                    </button>
                                {/if}
                                {#if showAlignmentGrid}
                                    <div class="pointer-events-none absolute inset-y-0 border-l border-primary/80" style="left: {guideX}%"></div>
                                    <div class="pointer-events-none absolute inset-x-0 border-t border-primary/80" style="top: {guideY}%"></div>
                                {/if}
                            {:else}
                                <div class="absolute inset-0 flex items-center justify-center text-foreground-muted">
                                    Upload an image to preview
                                </div>
                            {/if}
                        </div>
                        <div class="mt-3 flex items-center justify-between text-xs text-foreground-muted">
                            <span>{form.width} × {form.height}px</span>
                            <span>Long names shrink to fit the zone width</span>
                        </div>
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

{#if testTemplate}
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div class="bg-card rounded-xl shadow-xl w-full max-w-5xl max-h-[94vh] overflow-hidden flex flex-col">
            <div class="px-6 py-4 border-b border-border flex items-center justify-between">
                <div>
                    <h2 class="text-lg font-semibold">Test certificate output</h2>
                    <p class="text-sm text-foreground-muted mt-0.5">Rendered by the same generator used for participant downloads.</p>
                </div>
                <button onclick={closeTestPreview} class="btn btn-ghost btn-sm" aria-label="Close">✕</button>
            </div>
            <div class="flex-1 overflow-y-auto p-6 space-y-4">
                <div class="flex flex-col sm:flex-row sm:items-end gap-3">
                    <div class="flex-1">
                        <div class="flex items-center justify-between mb-1.5">
                            <label for="test-certificate-name" class="text-sm font-medium">Name on certificate</label>
                            <span class="text-xs text-foreground-muted">{testName.length}/{MAX_CERTIFICATE_NAME_LENGTH}</span>
                        </div>
                        <input
                            id="test-certificate-name"
                            bind:value={testName}
                            maxlength={MAX_CERTIFICATE_NAME_LENGTH}
                            class="input w-full"
                            placeholder="Enter any sample name"
                        />
                    </div>
                    <button
                        class="btn btn-secondary"
                        onclick={renderTestPreview}
                        disabled={testRendering || !testName.trim()}
                    >
                        {testRendering ? 'Rendering...' : 'Refresh preview'}
                    </button>
                    <button
                        class="btn btn-primary"
                        onclick={downloadTestPreview}
                        disabled={!testPreviewUrl || testRendering}
                    >
                        Download preview
                    </button>
                </div>

                <div
                    class="relative overflow-hidden rounded-lg border border-border bg-muted"
                    style="aspect-ratio: {testTemplate.width}/{testTemplate.height}"
                >
                    {#if testRendering && !testPreviewUrl}
                        <div class="absolute inset-0 grid place-items-center text-sm text-foreground-muted">Rendering certificate...</div>
                    {:else if testPreviewUrl}
                        <img src={testPreviewUrl} alt="Rendered certificate test output" class="h-full w-full object-contain" />
                    {:else}
                        <div class="absolute inset-0 grid place-items-center text-sm text-foreground-muted">Preview unavailable</div>
                    {/if}
                </div>
            </div>
        </div>
    </div>
{/if}
