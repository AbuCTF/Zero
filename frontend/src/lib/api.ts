/**
 * API Client for ZeroPool Backend
 */

import { browser } from '$app/environment';

const API_BASE = browser ? '/api' : (import.meta.env.VITE_API_URL || 'http://localhost:8000/api');

export interface ApiResponse<T = unknown> {
	success: boolean;
	data?: T;
	message?: string;
	error?: string;
}

export interface PaginatedResponse<T> {
	success: boolean;
	total: number;
	page: number;
	per_page: number;
	pages: number;
	items: T[];
}

class ApiError extends Error {
	constructor(
		public status: number,
		public code: string,
		message: string
	) {
		super(message);
		this.name = 'ApiError';
	}
}

async function request<T>(
	endpoint: string,
	options: RequestInit = {}
): Promise<T> {
	const url = `${API_BASE}${endpoint}`;

	const config: RequestInit = {
		...options,
		headers: {
			'Content-Type': 'application/json',
			...options.headers
		},
		credentials: 'include' // Include cookies for session auth
	};

	const response = await fetch(url, config);

	if (!response.ok) {
		let errorMessage = 'An error occurred';
		let errorCode = 'UNKNOWN_ERROR';

		try {
			const errorData = await response.json();
			errorMessage = errorData.detail || errorData.message || errorMessage;
			errorCode = errorData.code || errorCode;
		} catch {
			errorMessage = response.statusText;
		}

		throw new ApiError(response.status, errorCode, errorMessage);
	}

	// Handle empty responses
	const text = await response.text();
	if (!text) {
		return {} as T;
	}

	return JSON.parse(text);
}

// Auth endpoints
export const auth = {
	login: (email: string, password: string) =>
		request<{ success: boolean; user: App.Locals['user'] }>('/auth/login', {
			method: 'POST',
			body: JSON.stringify({ email, password })
		}),

	logout: () =>
		request<{ success: boolean }>('/auth/logout', {
			method: 'POST'
		}),

	me: () =>
		request<{ user: App.Locals['user'] }>('/auth/me'),

	register: (data: { email: string; username: string; password: string; name?: string }) =>
		request<{ success: boolean; message: string }>('/auth/register', {
			method: 'POST',
			body: JSON.stringify(data)
		}),

	verifyEmail: (token: string) =>
		request<{ success: boolean }>(`/auth/verify-email?token=${token}`)
};

// Events endpoints
export const events = {
	list: (page = 1, perPage = 20) =>
		request<{
			success: boolean;
			total: number;
			page: number;
			per_page: number;
			pages: number;
			events: Event[];
		}>(`/events?page=${page}&per_page=${perPage}`),

	get: (id: string) =>
		request<Event>(`/events/${id}`),

	getBySlug: (slug: string) =>
		request<Event>(`/events/${slug}`),

	register: (eventId: string, data: ParticipantRegistration) =>
		request<{ success: boolean; message: string }>(`/events/${eventId}/register`, {
			method: 'POST',
			body: JSON.stringify(data)
		})
};

// Admin endpoints
export const admin = {
	// Dashboard
	stats: () =>
		request<DashboardStats>('/admin/stats'),

	// Events
	events: {
		list: (page = 1, status?: string) => {
			let url = `/admin/events?page=${page}`;
			if (status) url += `&status_filter=${status}`;
			return request<{ events: Event[]; total: number; pages: number }>(url);
		},

		create: (data: EventCreate) =>
			request<Event>('/admin/events', {
				method: 'POST',
				body: JSON.stringify(data)
			}),

		get: (id: string) =>
			request<Event>(`/admin/events/${id}`),

		update: (id: string, data: Partial<EventCreate>) =>
			request<Event>(`/admin/events/${id}`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),

		stats: (id: string) =>
			request<EventStats>(`/admin/events/${id}/stats`),

		delete: (id: string) =>
			request<{ success: boolean; message: string }>(`/admin/events/${id}`, {
				method: 'DELETE'
			}),

		finalize: (id: string) =>
			request<{ success: boolean; message: string }>(`/admin/events/${id}/finalize`, {
				method: 'POST'
			}),

		syncCTFd: (id: string) =>
			request<{ success: boolean; message: string; stats?: { teams_created: number; teams_updated: number; participants_updated: number; participants_matched_by_id: number; participants_matched_by_name: number; unmatched_entries: unknown[] } }>(`/admin/events/${id}/ctfd/sync`, {
				method: 'POST'
			}),

		provisionCtfd: (id: string) =>
			request<{ success: boolean; message: string; stats?: { provisioned: number } }>(`/admin/events/${id}/ctfd/provision`, {
				method: 'POST'
			})
	},

	// Participants
	participants: {
		list: (eventId: string, page = 1, perPage = 50, search?: string) => {
			let url = `/admin/events/${eventId}/participants?page=${page}&per_page=${perPage}`;
			if (search) url += `&search=${encodeURIComponent(search)}`;
			return request<{ participants: Participant[]; total: number; page: number; pages: number; per_page: number }>(url);
		},

		import: (eventId: string, data: { participants: ParticipantImport[]; generate_passwords: boolean }) =>
			request<{ success: boolean; imported: number; skipped: number; errors: unknown[] }>(
				`/admin/events/${eventId}/participants/import`,
				{ method: 'POST', body: JSON.stringify(data) }
			),

		export: (eventId: string) =>
			`${API_BASE}/admin/events/${eventId}/export/participants`,

		delete: (eventId: string, participantId: string) =>
			request<{ success: boolean }>(`/admin/events/${eventId}/participants/${participantId}`, {
				method: 'DELETE'
			}),

		verify: (eventId: string, participantId: string) =>
			request<{ success: boolean }>(`/admin/events/${eventId}/participants/${participantId}/verify`, {
				method: 'POST'
			})
	},

	// Email Providers
	providers: {
		list: () =>
			request<EmailProvider[]>('/admin/providers'),

		create: (data: EmailProviderCreate) =>
			request<EmailProvider>('/admin/providers', {
				method: 'POST',
				body: JSON.stringify(data)
			}),

		update: (id: string, data: Partial<EmailProviderCreate>) =>
			request<EmailProvider>(`/admin/providers/${id}`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),

		delete: (id: string) =>
			request<{ success: boolean }>(`/admin/providers/${id}`, {
				method: 'DELETE'
			}),

		test: (id: string, recipientEmail: string) =>
			request<{ success: boolean; sent: boolean; error?: string }>(
				`/admin/providers/${id}/test`,
				{ method: 'POST', body: JSON.stringify({ recipient_email: recipientEmail }) }
			)
	},

	// Email Templates
	templates: {
		list: (eventId?: string) => {
			let url = '/admin/templates';
			if (eventId) url += `?event_id=${eventId}`;
			return request<EmailTemplate[]>(url);
		},

		create: (data: EmailTemplateCreate) =>
			request<EmailTemplate>('/admin/templates', {
				method: 'POST',
				body: JSON.stringify(data)
			}),

		get: (id: string) =>
			request<EmailTemplate>(`/admin/templates/${id}`),

		update: (id: string, data: Partial<EmailTemplateCreate>) =>
			request<EmailTemplate>(`/admin/templates/${id}`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),

		delete: (id: string) =>
			request<{ success: boolean }>(`/admin/templates/${id}`, {
				method: 'DELETE'
			})
	},

	// Voucher Pools
	voucherPools: {
		list: (eventId: string) =>
			request<VoucherPool[]>(`/admin/events/${eventId}/voucher-pools`),

		create: (eventId: string, data: VoucherPoolCreate) =>
			request<VoucherPool>(`/admin/events/${eventId}/voucher-pools`, {
				method: 'POST',
				body: JSON.stringify(data)
			}),

		uploadVouchers: (poolId: string, codes: string[]) =>
			request<{ success: boolean; message: string }>(
				`/admin/voucher-pools/${poolId}/vouchers`,
				{ method: 'POST', body: JSON.stringify({ codes }) }
			)
	},

	// Prize Rules
	prizeRules: {
		list: (eventId: string) =>
			request<PrizeRule[]>(`/admin/events/${eventId}/prize-rules`),

		create: (eventId: string, data: PrizeRuleCreate) =>
			request<PrizeRule>(`/admin/events/${eventId}/prize-rules`, {
				method: 'POST',
				body: JSON.stringify(data)
			}),

		delete: (id: string) =>
			request<{ success: boolean }>(`/admin/prize-rules/${id}`, {
				method: 'DELETE'
			})
	},

	// Certificate Templates
	certificateTemplates: {
		list: (eventId?: string) => {
			let url = '/admin/certificate-templates';
			if (eventId) url += `?event_id=${eventId}`;
			return request<CertificateTemplate[]>(url);
		},

		create: (data: CertificateTemplateCreate) =>
			request<CertificateTemplate>('/admin/certificate-templates', {
				method: 'POST',
				body: JSON.stringify(data)
			}),

		update: (id: string, data: Partial<CertificateTemplateCreate>) =>
			request<CertificateTemplate>(`/admin/certificate-templates/${id}`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),

		delete: (id: string) =>
			request<{ success: boolean }>(`/admin/certificate-templates/${id}`, {
				method: 'DELETE'
			}),

		uploadImage: (id: string, file: File) => {
			const formData = new FormData();
			formData.append('file', file);
			return fetch(`${API_BASE}/admin/certificate-templates/${id}/upload`, {
				method: 'POST',
				body: formData,
				credentials: 'include'
			}).then((res) => res.json());
		}
	},

	// Campaigns
	campaigns: {
		list: (eventId?: string) => {
			let url = '/admin/campaigns';
			if (eventId) url += `?event_id=${eventId}`;
			return request<EmailCampaign[]>(url);
		},

		create: (data: CampaignCreate) =>
			request<EmailCampaign>('/admin/campaigns', {
				method: 'POST',
				body: JSON.stringify(data)
			}),

		start: (id: string) =>
			request<{ success: boolean; message: string }>(`/admin/campaigns/${id}/start`, {
				method: 'POST'
			}),

		pause: (id: string) =>
			request<{ success: boolean; message: string }>(`/admin/campaigns/${id}/pause`, {
				method: 'POST'
			}),

		delete: (id: string) =>
			request<{ success: boolean }>(`/admin/campaigns/${id}`, {
				method: 'DELETE'
			}),

		cancel: (id: string) =>
			request<{ success: boolean; message: string }>(`/admin/campaigns/${id}/cancel`, {
				method: 'POST'
			})
	}
};

// Participant portal endpoints
export const participant = {
	me: () =>
		request<Participant>('/participants/me'),

	profile: () =>
		request<Participant>('/participants/me'),

	updateProfile: (data: Partial<{ name: string; password: string }>) =>
		request<Participant>('/participants/me', {
			method: 'PATCH',
			body: JSON.stringify(data)
		}),

	logout: () =>
		request<{ success: boolean }>('/participants/logout', {
			method: 'POST'
		}),

	requestAccess: (email: string, eventId?: string) =>
		request<{ 
			success: boolean; 
			message: string;
			requires_event_selection?: boolean;
			events?: Array<{ id: string; name: string; slug: string }>;
		}>('/participants/request-access', {
			method: 'POST',
			body: JSON.stringify({ email, event_id: eventId })
		}),

	events: () =>
		request<Event[]>('/participants/me/events'),

	prizes: () =>
		request<Prize[]>('/participants/me/prizes'),

	claimPrize: (prizeId: string) =>
		request<{ success: boolean; voucher_code?: string }>(`/prizes/${prizeId}/claim`, {
			method: 'POST'
		}),

	certificates: () =>
		request<Certificate[]>('/participants/me/certificates'),

	updateCertificateName: (certId: string, displayName: string) =>
		request<{ success: boolean; display_name: string }>(`/participants/me/certificates/${certId}`, {
			method: 'PATCH',
			body: JSON.stringify({ display_name: displayName })
		}),

	downloadCertificate: (certId: string, format: 'png' | 'pdf' = 'png') =>
		`${API_BASE}/participants/me/certificates/${certId}/download?format=${format}`
};

// Public endpoints
export const publicApi = {
	verifyCertificate: (code: string) =>
		request<{
			valid: boolean;
			participant_name?: string;
			event_name?: string;
			rank?: number;
			issued_at?: string;
		}>(`/certificates/verify/${code}`)
};

// Type definitions
export interface Event {
	id: string;
	name: string;
	slug: string;
	description?: string;
	status: 'draft' | 'registration' | 'active' | 'completed' | 'finalized' | 'archived';
	registration_open?: string;
	registration_close?: string;
	start_date?: string;
	end_date?: string;
	max_participants?: number | null;
	team_mode: boolean;
	min_team_size?: number;
	max_team_size?: number;
	ctfd_url?: string;
	ctfd_api_key?: string;
	ctfd_last_sync?: string;
	is_import_only?: boolean;
	created_at: string;
	updated_at?: string;
	participant_count?: number;
	verified_count?: number;
}

export interface EventCreate {
	name: string;
	slug: string;
	description?: string;
	registration_open?: string;
	registration_close?: string;
	start_date?: string;
	end_date?: string;
	max_participants?: number | null;
	team_mode?: boolean;
	min_team_size?: number;
	max_team_size?: number;
	ctfd_url?: string;
	ctfd_api_key?: string;
	is_import_only?: boolean;
}

export interface EventStats {
	participant_count: number;
	verified_count: number;
	ctfd_provisioned_count: number;
	team_count: number;
	emails_sent: number;
	certificates_generated: number;
	certificates_downloaded: number;
	prizes_assigned: number;
	prizes_claimed: number;
	vouchers_total: number;
	vouchers_claimed: number;
}

export interface DashboardStats {
	total_events: number;
	active_events: number;
	total_participants: number;
	verified_participants: number;
	total_emails_sent: number;
	emails_sent_today: number;
	total_certificates: number;
	certificates_downloaded: number;
	total_prizes: number;
	prizes_claimed: number;
	providers_active: number;
	providers_total: number;
	daily_email_capacity: number;
	daily_emails_used: number;
}

export interface Participant {
	id: string;
	event_id?: string;
	email: string;
	name: string;
	team_id?: number;
	team_name?: string;
	email_verified: boolean;
	email_verified_at?: string;
	ctfd_provisioned: boolean;
	ctfd_user_id?: number;
	final_rank?: number;
	final_score?: number;
	is_blocked: boolean;
	source: string;
	created_at: string;
	metadata?: Record<string, unknown>;
}

export interface ParticipantRegistration {
	email: string;
	name: string;
	team_name?: string;
	team_password?: string;
	create_team?: boolean;
}

export interface ParticipantImport {
	email: string;
	username: string;
	name?: string;
	metadata?: Record<string, unknown>;
}

export interface EmailProvider {
	id: string;
	name: string;
	provider_type: 'smtp' | 'brevo' | 'mailgun' | 'aws_ses' | 'mailjet' | 'gmail';
	daily_limit: number;
	hourly_limit: number;
	minute_limit: number;
	second_limit: number;
	monthly_limit?: number;
	priority: number;
	is_active: boolean;
	is_healthy: boolean;
	last_error?: string;
	last_error_at?: string;
	created_at: string;
	daily_used?: number;
	hourly_used?: number;
	available?: boolean;
}

export interface EmailProviderCreate {
	name: string;
	provider_type: string;
	config: Record<string, string>;
	daily_limit: number;
	hourly_limit: number;
	minute_limit?: number;
	second_limit?: number;
	monthly_limit?: number;
	priority: number;
}

export interface EmailTemplate {
	id: string;
	event_id?: string;
	slug: string;
	name: string;
	description?: string;
	subject: string;
	body_html: string;
	body_text?: string;
	variables?: string[];
	is_active: boolean;
	created_at: string;
}

export interface EmailTemplateCreate {
	event_id?: string;
	slug: string;
	name: string;
	description?: string;
	subject: string;
	body_html: string;
	body_text?: string;
	variables?: string[];
}

export interface VoucherPool {
	id: string;
	event_id: string;
	name: string;
	description?: string;
	platform?: string;
	total_count: number;
	claimed_count: number;
	created_at: string;
}

export interface VoucherPoolCreate {
	name: string;
	description?: string;
	platform?: string;
}

export interface PrizeRule {
	id: string;
	event_id: string;
	name: string;
	description?: string;
	rank_min: number;
	rank_max?: number;
	prize_type: string;
	prize_value?: string;
	voucher_pool_id?: number;
	voucher_pool_name?: string;
	is_active: boolean;
	created_at: string;
}

export interface PrizeRuleCreate {
	name: string;
	description?: string;
	rank_min: number;
	rank_max?: number;
	prize_type: string;
	prize_value?: string;
	voucher_pool_id?: number;
}

export interface Prize {
	id: string;
	participant_id: string;
	event_id?: string;
	event_name?: string;
	prize_rule_id?: number;
	voucher_id?: number;
	name: string;
	description?: string;
	prize_type: string;
	prize_value?: string;
	status: 'pending' | 'available' | 'claimed' | 'expired';
	claimed_at?: string;
	created_at: string;
	voucher_code?: string;
	voucher_instructions?: string;
	rank?: number;
}

export interface CertificateTemplate {
	id: string;
	event_id?: string;
	name: string;
	description?: string;
	background_image: string;
	output_format: string;
	width: number;
	height: number;
	text_zones: TextZone[];
	qr_zone?: QRZone;
	is_default: boolean;
	created_at: string;
}

export interface TextZone {
	text: string;
	x: number;
	y: number;
	font_name?: string;
	font_size?: number;
	color?: string;
	align?: 'left' | 'center' | 'right';
}

export interface QRZone {
	x: number;
	y: number;
	size: number;
}

export interface CertificateTemplateCreate {
	event_id?: number;
	name: string;
	description?: string;
	background_image?: string;
	output_format?: string;
	width?: number;
	height?: number;
	text_zones?: TextZone[];
	qr_zone?: QRZone;
	is_default?: boolean;
}

export interface Certificate {
	id: string;
	participant_id: string;
	event_id?: string;
	event_name?: string;
	template_id?: number;
	verification_code: string;
	certificate_type: string;
	file_url?: string;
	format?: string;
	generated_at?: string;
	downloaded_at?: string;
	download_count: number;
	display_name?: string;
	name_locked?: boolean;
	edit_count?: number;
	created_at: string;
}

export interface EmailCampaign {
	id: string;
	event_id: string;
	template_id: string;
	name: string;
	status: 'draft' | 'scheduled' | 'sending' | 'completed' | 'paused' | 'failed';
	recipient_filter?: Record<string, unknown>;
	total_recipients: number;
	sent_count: number;
	failed_count: number;
	scheduled_at?: string;
	started_at?: string;
	completed_at?: string;
	created_at: string;
}

export interface CampaignCreate {
	event_id: string;
	template_id: string;
	name: string;
	recipient_filter?: Record<string, unknown>;
	scheduled_at?: string;
}

// Combined API export
export const api = {
	auth,
	events,
	admin,
	participant,
	publicApi
};

export { ApiError };
