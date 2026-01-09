<script lang="ts">
    import { onMount } from 'svelte';
    import { api, type EmailTemplate } from '$lib/api';

    let templates = $state<EmailTemplate[]>([]);
    let loading = $state(true);
    let error = $state('');
    
    let showModal = $state(false);
    let editingTemplate = $state<EmailTemplate | null>(null);
    let saving = $state(false);
    
    let form = $state({
        name: '',
        subject: '',
        body_html: '',
        body_text: '',
        slug: 'custom',
        description: '',
        event_id: null as string | null
    });

    const templateTypes = [
        { value: 'verification', label: 'Email Verification' },
        { value: 'welcome', label: 'Welcome Email' },
        { value: 'reminder', label: 'Event Reminder' },
        { value: 'results', label: 'Results Announcement' },
        { value: 'prize', label: 'Prize Notification' },
        { value: 'certificate', label: 'Certificate Delivery' },
        { value: 'custom', label: 'Custom' }
    ];

    const availableVariables = [
        { name: '{{ participant.name }}', desc: 'Participant full name' },
        { name: '{{ participant.email }}', desc: 'Participant email' },
        { name: '{{ participant.team_name }}', desc: 'Team name (if applicable)' },
        { name: '{{ event.name }}', desc: 'Event name' },
        { name: '{{ event.start_date }}', desc: 'Event start date' },
        { name: '{{ event.end_date }}', desc: 'Event end date' },
        { name: '{{ verification_url }}', desc: 'Email verification URL' },
        { name: '{{ prize.name }}', desc: 'Prize name' },
        { name: '{{ prize.description }}', desc: 'Prize description' },
        { name: '{{ voucher.code }}', desc: 'Voucher code' },
        { name: '{{ certificate_url }}', desc: 'Certificate download URL' },
        { name: '{{ rank }}', desc: 'Final ranking' },
        { name: '{{ score }}', desc: 'Final score' }
    ];

    onMount(async () => {
        await loadTemplates();
    });

    async function loadTemplates() {
        loading = true;
        error = '';
        try {
            templates = await api.admin.templates.list();
        } catch (e: any) {
            error = e.message || 'Failed to load templates';
        } finally {
            loading = false;
        }
    }

    function openAddModal() {
        editingTemplate = null;
        form = {
            name: '',
            subject: '',
            body_html: getDefaultHtmlTemplate(),
            body_text: '',
            slug: 'custom',
            description: '',
            event_id: null
        };
        showModal = true;
    }

    function openEditModal(template: EmailTemplate) {
        editingTemplate = template;
        form = {
            name: template.name,
            subject: template.subject,
            body_html: template.body_html,
            body_text: template.body_text || '',
            slug: template.slug,
            description: template.description || '',
            event_id: template.event_id || null
        };
        showModal = true;
    }

    function getDefaultHtmlTemplate(): string {
        return `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ subject }}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #1a1a2e; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { background: #f5f5f5; padding: 30px; border-radius: 0 0 8px 8px; }
        .button { display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }
        .footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ event.name }}</h1>
    </div>
    <div class="content">
        <p>Hello {{ participant.name }},</p>
        <p>Your email content goes here.</p>
    </div>
    <div class="footer">
        <p>Powered by ZeroPool</p>
    </div>
</body>
</html>`;
    }

    async function handleSubmit() {
        saving = true;
        error = '';
        try {
            if (editingTemplate) {
                await api.admin.templates.update(editingTemplate.id, form);
            } else {
                await api.admin.templates.create(form);
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
        if (!confirm('Are you sure you want to delete this template?')) return;
        
        try {
            await api.admin.templates.delete(id);
            await loadTemplates();
        } catch (e: any) {
            error = e.message || 'Failed to delete template';
        }
    }

    function insertVariable(variable: string) {
        const textarea = document.getElementById('html-body') as HTMLTextAreaElement;
        if (textarea) {
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            const text = form.body_html;
            form.body_html = text.substring(0, start) + variable + text.substring(end);
            // Reset cursor position after insert
            setTimeout(() => {
                textarea.focus();
                textarea.setSelectionRange(start + variable.length, start + variable.length);
            }, 0);
        }
    }

    function duplicateTemplate(template: EmailTemplate) {
        editingTemplate = null;
        form = {
            name: `${template.name} (Copy)`,
            subject: template.subject,
            body_html: template.body_html,
            body_text: template.body_text || '',
            slug: 'custom',
            description: '',
            event_id: null
        };
        showModal = true;
    }
</script>

<svelte:head>
    <title>Email Templates - ZeroPool Admin</title>
</svelte:head>

<div class="p-6 lg:p-8">
    <div class="space-y-6">
        <div class="flex items-center justify-between">
            <div>
                <h1 class="text-2xl font-semibold">Email Templates</h1>
                <p class="text-sm text-muted-foreground mt-1">
                    Create and manage email templates with Jinja2 variables
                </p>
            </div>
            <button onclick={openAddModal} class="btn btn-primary">
                New Template
            </button>
        </div>

    {#if error}
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
            <div class="text-muted-foreground mb-4">No email templates yet</div>
            <button onclick={openAddModal} class="btn btn-primary">
                Create Your First Template
            </button>
        </div>
    {:else}
        <div class="grid gap-4">
            {#each templates as template}
                <div class="card p-6">
                    <div class="flex items-start justify-between">
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-3">
                                <h3 class="font-medium truncate">{template.name}</h3>
                                <span class="badge badge-secondary text-xs">
                                    {template.slug}
                                </span>
                                {#if template.event_id}
                                    <span class="badge badge-outline text-xs">
                                        Event-specific
                                    </span>
                                {/if}
                            </div>
                            <p class="text-sm text-muted-foreground mt-1 truncate">
                                Subject: {template.subject}
                            </p>
                        </div>
                        <div class="flex items-center gap-2">
                            <button 
                                onclick={() => duplicateTemplate(template)}
                                class="btn btn-ghost btn-sm"
                                title="Duplicate"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                            </button>
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
            {/each}
        </div>
    {/if}
</div>

{#if showModal}
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div class="bg-card rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
            <div class="px-6 py-4 border-b border-border flex items-center justify-between">
                <h2 class="text-lg font-semibold">
                    {editingTemplate ? 'Edit Template' : 'New Template'}
                </h2>
                <button onclick={() => showModal = false} class="btn btn-ghost btn-sm">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
            
            <div class="flex-1 overflow-y-auto p-6">
                <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-6">
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label for="name" class="block text-sm font-medium mb-1.5">
                                Template Name
                            </label>
                            <input
                                type="text"
                                id="name"
                                bind:value={form.name}
                                class="input"
                                placeholder="Welcome Email"
                                required
                            />
                        </div>
                        <div>
                            <label for="type" class="block text-sm font-medium mb-1.5">
                                Template Type (Slug)
                            </label>
                            <select id="type" bind:value={form.slug} class="input">
                                {#each templateTypes as type}
                                    <option value={type.value}>{type.label}</option>
                                {/each}
                            </select>
                        </div>
                    </div>

                    <div>
                        <label for="subject" class="block text-sm font-medium mb-1.5">
                            Email Subject
                        </label>
                        <input
                            type="text"
                            id="subject"
                            bind:value={form.subject}
                            class="input"
                            placeholder="Welcome to {'{{'} event.name {'}}'}"
                            required
                        />
                        <p class="text-xs text-muted-foreground mt-1">
                            Supports Jinja2 variables
                        </p>
                    </div>

                    <div>
                        <div class="flex items-center justify-between mb-1.5">
                            <label for="html-body" class="block text-sm font-medium">
                                HTML Body
                            </label>
                            <div class="flex items-center gap-2">
                                <span class="text-xs text-muted-foreground">Insert variable:</span>
                                <select 
                                    onchange={(e) => {
                                        const target = e.target as HTMLSelectElement;
                                        if (target.value) {
                                            insertVariable(target.value);
                                            target.value = '';
                                        }
                                    }}
                                    class="input text-xs py-1 px-2 w-48"
                                >
                                    <option value="">Select...</option>
                                    {#each availableVariables as v}
                                        <option value={v.name}>{v.name}</option>
                                    {/each}
                                </select>
                            </div>
                        </div>
                        <textarea
                            id="html-body"
                            bind:value={form.body_html}
                            class="input font-mono text-sm"
                            rows="16"
                            required
                        ></textarea>
                    </div>

                    <details class="group">
                        <summary class="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                            Plain Text Body (Optional)
                        </summary>
                        <div class="mt-3">
                            <textarea
                                bind:value={form.body_text}
                                class="input font-mono text-sm"
                                rows="8"
                                placeholder="Plain text fallback for email clients that don't support HTML"
                            ></textarea>
                        </div>
                    </details>

                    <details class="group">
                        <summary class="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                            Available Variables Reference
                        </summary>
                        <div class="mt-3 bg-muted/50 rounded-lg p-4">
                            <div class="grid grid-cols-2 gap-2 text-sm">
                                {#each availableVariables as v}
                                    <div class="flex items-start gap-2">
                                        <code class="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
                                            {v.name}
                                        </code>
                                        <span class="text-muted-foreground text-xs">{v.desc}</span>
                                    </div>
                                {/each}
                            </div>
                        </div>
                    </details>
                </form>
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
</div>

<style>
    .badge-outline {
        background: transparent;
        border: 1px solid hsl(var(--border));
    }
</style>
