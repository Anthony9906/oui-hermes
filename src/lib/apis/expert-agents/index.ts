import { WEBUI_API_BASE_URL } from '$lib/constants';

export type ExpertSkillCard = {
	skill_name: string;
	description: string;
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
