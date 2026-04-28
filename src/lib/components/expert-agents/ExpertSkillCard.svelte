<script lang="ts">
	import type { ExpertSkillCard } from '$lib/apis/expert-agents';
	import ArrowRight from '$lib/components/icons/ArrowRight.svelte';
	import InfoCircle from '$lib/components/icons/InfoCircle.svelte';

	export let skill: ExpertSkillCard;
	export let onStart: (skill: ExpertSkillCard) => void = () => {};
	export let onDetails: (skill: ExpertSkillCard) => void = () => {};
</script>

<div
	class="expert-skill-card group relative flex h-40 w-full min-w-[180px] flex-col overflow-hidden rounded-lg border border-gray-200 bg-white p-3 shadow-xs transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_14px_32px_rgba(134,144,175,0.24)] focus-within:shadow-[0_14px_32px_rgba(134,144,175,0.24)] dark:border-gray-800 dark:bg-gray-900"
>
	<div class="line-clamp-2 text-[15px] font-semibold leading-5 text-gray-900 dark:text-gray-100">
		{skill.skill_name}
	</div>

	<div
		class="skill-description-preview mt-2 flex-1 text-xs leading-5 text-gray-500 dark:text-gray-500"
	>
		{skill.description || '暂无描述'}
	</div>

	<div class="mt-2 flex items-center justify-between gap-1.5">
		<button
			type="button"
			class="flex size-6 shrink-0 items-center justify-center rounded-md text-gray-400 transition hover:bg-[#8690af]/10 hover:text-[#68728a] dark:text-gray-500 dark:hover:bg-[#8690af]/15 dark:hover:text-gray-300"
			aria-label={`查看 ${skill.skill_name} 技能详情`}
			on:click|stopPropagation={() => {
				onDetails(skill);
			}}
		>
			<InfoCircle className="size-3.5" strokeWidth="1.8" />
		</button>

		<button
			type="button"
			class="inline-flex h-6 min-w-0 items-center justify-center gap-1 rounded-md bg-[#8690af] px-2.5 text-[11px] font-medium text-white shadow-xs transition hover:bg-[#747f9f] hover:shadow-sm dark:bg-[#8690af] dark:hover:bg-[#9aa3bd]"
			on:click={() => onStart(skill)}
		>
			<ArrowRight className="size-3" strokeWidth="2" />
			开始会话
		</button>
	</div>
</div>

<style>
	.expert-skill-card::before {
		content: '';
		position: absolute;
		inset: 0;
		z-index: 0;
		opacity: 0;
		background:
			radial-gradient(circle at 18% 18%, rgba(134, 144, 175, 0.18), transparent 42%),
			radial-gradient(circle at 88% 10%, rgba(170, 180, 205, 0.2), transparent 38%),
			linear-gradient(135deg, #f8faff 0%, #eef2fb 48%, #f6f8fc 100%);
		transition:
			opacity 180ms ease,
			background-position 320ms ease;
		background-size: 140% 140%;
		background-position: 0% 50%;
	}

	.expert-skill-card:hover::before,
	.expert-skill-card:focus-within::before {
		opacity: 1;
		background-position: 100% 50%;
	}

	:global(.dark) .expert-skill-card::before {
		background:
			radial-gradient(circle at 18% 18%, rgba(134, 144, 175, 0.18), transparent 42%),
			radial-gradient(circle at 88% 10%, rgba(93, 104, 135, 0.22), transparent 38%),
			linear-gradient(135deg, #252d42 0%, #31394f 48%, #2f374d 100%);
	}

	.expert-skill-card > :global(*) {
		position: relative;
		z-index: 1;
	}

	.skill-description-preview {
		display: -webkit-box;
		overflow: hidden;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 3;
	}
</style>
