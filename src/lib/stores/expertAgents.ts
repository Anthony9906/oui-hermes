import { writable } from 'svelte/store';
import type { ExpertSkillCard } from '$lib/apis/expert-agents';

export type ExpertAgentStartRequest = {
	skill_name: string;
	prompt: string;
	nonce: string;
};

export const showExpertAgentDrawer = writable(false);
export const expertAgentStartRequest = writable<ExpertAgentStartRequest | null>(null);

export const openExpertAgentDrawer = () => {
	showExpertAgentDrawer.set(true);
};

export const closeExpertAgentDrawer = () => {
	showExpertAgentDrawer.set(false);
};

export const toggleExpertAgentDrawer = () => {
	showExpertAgentDrawer.update((show) => !show);
};

export const requestStartExpertSkillChat = (skill: ExpertSkillCard) => {
	expertAgentStartRequest.set({
		skill_name: skill.skill_name,
		prompt: `现在开始使用专家技能 ${skill.skill_name} 来完成用户提出的需求或任务。`,
		nonce: crypto.randomUUID()
	});
};

export const clearExpertAgentStartRequest = () => {
	expertAgentStartRequest.set(null);
};
