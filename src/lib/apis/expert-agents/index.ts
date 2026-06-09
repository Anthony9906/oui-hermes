import { WEBUI_API_BASE_URL } from '$lib/constants';

export type ExpertSkillCard = {
	skill_name: string;
	description: string;
	version?: string | null;
	updated_at?: string | null;
	author?: string | null;
	icon?: string | null;
	icon_background?: string | null;
	tags?: string[];
	usage_count?: number | null;
};

export type ExpertSkillDetail = {
	name: string;
	description: string;
	version?: string | null;
	updated_at?: string | null;
	author?: string | null;
	icon?: string | null;
	icon_background?: string | null;
	content: string;
	path?: string | null;
	tags?: string[];
	related_skills?: string[];
	linked_files?: Record<string, string[]> | null;
	readiness_status?: string | null;
	setup_needed?: boolean | null;
	setup_note?: string | null;
	metadata?: Record<string, unknown> | null;
};

export const getExpertAgents = async (token: string = ''): Promise<ExpertSkillCard[]> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/expert-agents`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json?.items ?? [];
		})
		.catch((err) => {
			error = err.detail ?? 'Failed to load expert agents';
			console.error(err);
			return [];
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getExpertAgentDetail = async (
	skillName: string,
	token: string = ''
): Promise<ExpertSkillDetail> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/expert-agents/${encodeURIComponent(skillName)}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Failed to load expert skill detail';
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateExpertAgentDetail = async (
	skillName: string,
	payload: {
		content: string;
		icon?: string | null;
		icon_background?: string | null;
	},
	token: string = ''
): Promise<ExpertSkillDetail> => {
	let error = null;

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/expert-agents/${encodeURIComponent(skillName)}/update`,
		{
			method: 'POST',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			},
			body: JSON.stringify(payload)
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Failed to save expert skill';
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateExpertAgentAppearance = async (
	skillName: string,
	payload: {
		icon: string;
		icon_background: string;
	},
	token: string = ''
): Promise<ExpertSkillDetail> => {
	let error = null;

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/expert-agents/${encodeURIComponent(skillName)}/appearance`,
		{
			method: 'POST',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			},
			body: JSON.stringify(payload)
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Failed to update expert skill appearance';
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const openExpertAgentDirectory = async (
	skillName: string,
	token: string = ''
): Promise<{ ok: boolean; path: string }> => {
	let error = null;

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/expert-agents/${encodeURIComponent(skillName)}/open-directory`,
		{
			method: 'POST',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Failed to open expert skill directory';
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
