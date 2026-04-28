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
	return [
		`当前对话启用专家技能： ${skillName}`,
		'优先按照该专家技能的知识、流程和约束完成用户的后续任务，',
		'只读取SKILL.md，然后用简洁的语言指导用户下一步做什么'
	].join('\n');
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
