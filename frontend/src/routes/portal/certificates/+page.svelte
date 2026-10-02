<script lang="ts">
    import { onMount } from 'svelte';
    import { api, type Certificate } from '$lib/api';
    import { formatDate } from '$lib/utils';

    let certificates = $state<Certificate[]>([]);
    let loading = $state(true);
    let error = $state('');
    let editingCertId = $state<string | null>(null);
    let editName = $state('');
    let saving = $state(false);
    let previewErrors = $state<Record<string, boolean>>({});

    const MAX_CERTIFICATE_NAME_LENGTH = 80;

    onMount(async () => {
        await loadCertificates();
    });

    async function loadCertificates() {
        loading = true;
        try {
            certificates = await api.participant.certificates();
            previewErrors = {};
        } catch (e: any) {
            error = e.message || 'Failed to load certificates';
        } finally {
            loading = false;
        }
    }

    function getTypeLabel(type: string): string {
        switch (type) {
            case 'participation': return 'Participation';
            case 'winner': return 'Winner';
            case 'finalist': return 'Finalist';
            case 'special': return 'Special Award';
            default: return type;
        }
    }

    function startEditing(cert: Certificate) {
        editingCertId = cert.id;
        editName = cert.display_name || '';
    }

    function cancelEditing() {
        editingCertId = null;
        editName = '';
    }

    async function saveDisplayName(certId: string) {
        if (!editName.trim()) return;
        
        saving = true;
        try {
            const result = await api.participant.updateCertificateName(certId, editName.trim());
            if (result.success) {
                certificates = certificates.map(c =>
                    c.id === certId
                        ? { ...c, display_name: result.display_name, edit_count: (c.edit_count ?? 0) + 1 }
                        : c
                );
                previewErrors = { ...previewErrors, [certId]: false };
                editingCertId = null;
                editName = '';
            }
        } catch (e: any) {
            error = e.message || 'Failed to update display name';
        } finally {
            saving = false;
        }
    }

    function confirmDownload(event: MouseEvent, cert: Certificate) {
        if (cert.name_locked) return;
        if (!confirm(`Download this certificate with the name “${cert.display_name}”? Your name will be locked after the first download.`)) {
            event.preventDefault();
        }
    }
</script>

<svelte:head>
    <title>Certificates - Participant Portal</title>
</svelte:head>

<div class="space-y-6">
    <div>
        <h1 class="text-2xl font-semibold">Certificates</h1>
        <p class="text-sm text-foreground-muted mt-1">
            Review your name, preview the final certificate, then download it
        </p>
    </div>

    {#if error}
        <div class="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
            {error}
        </div>
    {/if}

    {#if loading}
        <div class="card p-12 text-center">
            <div class="animate-pulse text-foreground-muted">Loading certificates...</div>
        </div>
    {:else if certificates.length === 0}
        <div class="card p-12 text-center">
            <div class="w-16 h-16 mx-auto mb-4 bg-muted rounded-full flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-foreground-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
            </div>
            <h2 class="text-lg font-medium mb-2">No Certificates Yet</h2>
            <p class="text-foreground-muted text-sm">
                Certificates will be available after event results are finalized.
            </p>
        </div>
    {:else}
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {#each certificates as cert}
                <div class="card overflow-hidden">
                    <div
                        class="bg-muted relative overflow-hidden"
                        style="aspect-ratio: {cert.width || 1600} / {cert.height || 900}"
                    >
                        {#if !previewErrors[cert.id]}
                            <img
                                src={api.participant.previewCertificate(cert.id, cert.edit_count ?? 0)}
                                alt="Personalized certificate preview for {cert.display_name}"
                                class="absolute inset-0 h-full w-full object-contain"
                                onerror={() => previewErrors = { ...previewErrors, [cert.id]: true }}
                            />
                        {:else}
                            <div class="absolute inset-0 flex flex-col items-center justify-center p-4 text-center">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 text-foreground-muted/50 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                                <span class="text-sm font-medium text-foreground-muted">Preview unavailable</span>
                                <button
                                    class="btn btn-ghost btn-sm mt-2"
                                    onclick={() => previewErrors = { ...previewErrors, [cert.id]: false }}
                                >
                                    Retry
                                </button>
                            </div>
                        {/if}
                        </div>
                    
                    <div class="p-4">
                        <div class="flex items-start justify-between mb-2">
                            <div>
                                <h3 class="font-medium">{cert.event_name}</h3>
                                <div class="text-sm text-foreground-muted">
                                    {getTypeLabel(cert.certificate_type)}
                                </div>
                            </div>
                            <span class="badge badge-secondary text-xs">
                                {cert.format?.toUpperCase() || 'PNG'}
                            </span>
                        </div>
                        
                        <div class="mb-4 p-3 bg-muted/50 rounded-lg">
                            <div class="flex items-center justify-between mb-1">
                                <span class="text-xs text-foreground-muted">Name on Certificate</span>
                                {#if cert.name_locked}
                                    <span class="badge badge-secondary text-xs" title="Name is locked after download">
                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                                        </svg>
                                        Locked
                                    </span>
                                {:else if (cert.edit_count ?? 0) >= 1}
                                    <span class="badge badge-muted text-xs" title="Edit limit reached">
                                        No edits left
                                    </span>
                                {/if}
                            </div>
                            {#if editingCertId === cert.id}
                                <div class="space-y-2">
                                    <input 
                                        type="text"
                                        bind:value={editName}
                                        class="input input-sm w-full text-sm"
                                        placeholder="Enter your full name"
                                        maxlength={MAX_CERTIFICATE_NAME_LENGTH}
                                        disabled={saving}
                                    />
                                    <div class="flex items-center justify-between gap-2">
                                        <span class="text-xs text-foreground-muted">
                                            {editName.length}/{MAX_CERTIFICATE_NAME_LENGTH}
                                        </span>
                                        <div class="flex gap-2">
                                            <button
                                                class="btn btn-secondary btn-sm"
                                                onclick={cancelEditing}
                                                disabled={saving}
                                            >
                                                Cancel
                                            </button>
                                            <button
                                                class="btn btn-primary btn-sm"
                                                onclick={() => saveDisplayName(cert.id)}
                                                disabled={saving || !editName.trim()}
                                            >
                                                {saving ? 'Saving...' : 'Save name'}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            {:else}
                                <div class="flex items-center justify-between gap-2">
                                    <span class="font-medium text-sm">{cert.display_name}</span>
                                    {#if !cert.name_locked && (cert.edit_count ?? 0) < 1}
                                        <button 
                                            class="btn btn-ghost btn-sm text-xs"
                                            onclick={() => startEditing(cert)}
                                            title="Edit name on certificate (1 edit allowed)"
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                            </svg>
                                            Edit
                                        </button>
                                    {/if}
                                </div>
                            {/if}
                        </div>
                        
                        <div class="text-xs text-foreground-muted mb-4">
                            Issued: {cert.created_at ? formatDate(cert.created_at) : '-'}
                        </div>
                        
                        <div class="flex items-center gap-2">
                            <a 
                                href={api.participant.downloadCertificate(cert.id, cert.format || 'png')}
                                download
                                class="btn btn-primary btn-sm flex-1"
                                onclick={(event) => confirmDownload(event, cert)}
                            >
                                Download {cert.format?.toUpperCase() || 'PNG'}
                            </a>
                            <a 
                                href="/verify?code={cert.verification_code}"
                                class="btn btn-secondary btn-sm"
                                title="Verify Certificate"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                </svg>
                            </a>
                        </div>
                        
                        <div class="mt-3 pt-3 border-t border-border">
                            <div class="flex items-center justify-between text-xs">
                                <span class="text-foreground-muted">Verification Code:</span>
                                <code class="font-mono text-foreground-muted">
                                    {cert.verification_code}
                                </code>
                            </div>
                        </div>
                    </div>
                </div>
            {/each}
        </div>
    {/if}
</div>
