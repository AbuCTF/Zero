// Re-export utilities
export { clsx } from 'clsx';
export { twMerge } from 'tailwind-merge';

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind CSS classes with clsx
 */
export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

/**
 * Format a date string
 */
export function formatDate(date: string | Date | undefined, options?: Intl.DateTimeFormatOptions): string {
	if (!date) return '-';
	const d = typeof date === 'string' ? new Date(date) : date;
	return d.toLocaleDateString('en-US', {
		year: 'numeric',
		month: 'short',
		day: 'numeric',
		...options
	});
}

/**
 * Format a date with time
 */
export function formatDateTime(date: string | Date | undefined): string {
	if (!date) return '-';
	const d = typeof date === 'string' ? new Date(date) : date;
	return d.toLocaleString('en-US', {
		year: 'numeric',
		month: 'short',
		day: 'numeric',
		hour: '2-digit',
		minute: '2-digit'
	});
}

/**
 * Format relative time
 */
export function formatRelativeTime(date: string | Date): string {
	const d = typeof date === 'string' ? new Date(date) : date;
	const now = new Date();
	const diff = now.getTime() - d.getTime();

	const seconds = Math.floor(diff / 1000);
	const minutes = Math.floor(seconds / 60);
	const hours = Math.floor(minutes / 60);
	const days = Math.floor(hours / 24);

	if (seconds < 60) return 'just now';
	if (minutes < 60) return `${minutes}m ago`;
	if (hours < 24) return `${hours}h ago`;
	if (days < 7) return `${days}d ago`;

	return formatDate(d);
}

/**
 * Format a number with commas
 */
export function formatNumber(num: number | undefined): string {
	if (num === undefined || num === null) return '0';
	return num.toLocaleString();
}

/**
 * Format percentage
 */
export function formatPercent(value: number, total: number): string {
	if (total === 0) return '0%';
	return `${Math.round((value / total) * 100)}%`;
}

/**
 * Truncate text
 */
export function truncate(text: string, length: number): string {
	if (text.length <= length) return text;
	return text.slice(0, length) + '...';
}

/**
 * Capitalize first letter
 */
export function capitalize(text: string): string {
	return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * Slugify a string
 */
export function slugify(text: string): string {
	return text
		.toLowerCase()
		.trim()
		.replace(/[^\w\s-]/g, '')
		.replace(/[\s_-]+/g, '-')
		.replace(/^-+|-+$/g, '');
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
	fn: T,
	delay: number
): (...args: Parameters<T>) => void {
	let timeoutId: ReturnType<typeof setTimeout>;
	return (...args: Parameters<T>) => {
		clearTimeout(timeoutId);
		timeoutId = setTimeout(() => fn(...args), delay);
	};
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
	try {
		await navigator.clipboard.writeText(text);
		return true;
	} catch {
		// Fallback for older browsers
		const textarea = document.createElement('textarea');
		textarea.value = text;
		document.body.appendChild(textarea);
		textarea.select();
		const result = document.execCommand('copy');
		document.body.removeChild(textarea);
		return result;
	}
}

/**
 * Download file from URL
 */
export function downloadFile(url: string, filename?: string): void {
	const a = document.createElement('a');
	a.href = url;
	a.download = filename || '';
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
}

/**
 * Generate random ID
 */
export function generateId(length = 8): string {
	return Math.random()
		.toString(36)
		.substring(2, 2 + length);
}

/**
 * Check if value is empty
 */
export function isEmpty(value: unknown): boolean {
	if (value === null || value === undefined) return true;
	if (typeof value === 'string') return value.trim() === '';
	if (Array.isArray(value)) return value.length === 0;
	if (typeof value === 'object') return Object.keys(value).length === 0;
	return false;
}

/**
 * Safe JSON parse
 */
export function safeJsonParse<T>(json: string, fallback: T): T {
	try {
		return JSON.parse(json);
	} catch {
		return fallback;
	}
}

/**
 * Event status badge color
 */
export function getEventStatusColor(status: string): string {
	switch (status) {
		case 'draft':
			return 'badge-muted';
		case 'registration':
			return 'badge-warning';
		case 'live':
			return 'badge-success';
		case 'completed':
			return 'badge-success';
		case 'archived':
			return 'badge-muted';
		default:
			return 'badge-muted';
	}
}

/**
 * Provider type display name
 */
export function getProviderDisplayName(type: string): string {
	const names: Record<string, string> = {
		smtp: 'SMTP',
		brevo: 'Brevo',
		mailgun: 'Mailgun',
		aws_ses: 'AWS SES',
		mailjet: 'Mailjet',
		gmail: 'Gmail'
	};
	return names[type] || type;
}
