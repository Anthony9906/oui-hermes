import { writable } from 'svelte/store';
import { v4 as uuidv4 } from 'uuid';
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

export const buildExpertSkillPrompt = (skillName: string) => {
	return `专家模式 : ${skillName}

加载你的专家技能，然后直接问用户一个关键问题帮他快速切入任务，并给2-3个具体选项让他选。不要列能力，不要自我介绍。简洁、专业。`;
};

export const requestStartExpertSkillChat = (skill: ExpertSkillCard) => {
	expertAgentStartRequest.set({
		skill_name: skill.skill_name,
		prompt: buildExpertSkillPrompt(skill.skill_name),
		nonce: uuidv4()
	});
};

export const clearExpertAgentStartRequest = () => {
	expertAgentStartRequest.set(null);
};
