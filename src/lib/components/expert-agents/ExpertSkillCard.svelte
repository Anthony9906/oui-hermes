<script lang="ts">
	import type { ExpertSkillCard } from '$lib/apis/expert-agents';
	import ChatBubble from '$lib/components/icons/ChatBubble.svelte';
	import InfoCircle from '$lib/components/icons/InfoCircle.svelte';
	import LucideIcon from './LucideIcon.svelte';

	export let skill: ExpertSkillCard;
	export let onStart: (skill: ExpertSkillCard) => void = () => {};
	export let onDetails: (skill: ExpertSkillCard) => void = () => {};

	const iconOptions = [
		'bot',
		'brain-circuit',
		'messages-square',
		'book-open',
		'search',
		'scan-search',
		'clipboard-list',
		'file-text',
		'table',
		'chart-no-axes-combined',
		'presentation',
		'workflow',
		'database',
		'package',
		'boxes',
		'blocks',
		'code',
		'terminal',
		'wrench',
		'cog',
		'cpu',
		'circuit-board',
		'factory',
		'ruler',
		'pencil-ruler',
		'drafting-compass',
		'compass',
		'shield-check',
		'lightbulb',
		'rocket',
		'hammer',
		'sparkles'
	];
	const iconBackgrounds = [
		'#e6edf7',
		'#ebeaf5',
		'#e8eef2',
		'#eef0e8',
		'#f0ece7',
		'#f1e9ee',
		'#edeef1',
		'#edf0e6'
	];
	const tagStyles = [
		{ background: '#eef2f6', color: '#5f6f82', border: '#dde5ee' },
		{ background: '#eef4f0', color: '#607568', border: '#dfe9e2' },
		{ background: '#f4f1ec', color: '#7a6955', border: '#e8e1d7' },
		{ background: '#f1f0f5', color: '#6d6681', border: '#e3e0eb' },
		{ background: '#edf3f4', color: '#5f7479', border: '#dce8ea' }
	];

	const hashString = (value: string) =>
		Array.from(value || 'expert-agent').reduce((acc, char) => acc + char.charCodeAt(0), 0);

	$: skillHash = hashString(skill.skill_name);
	$: skillIcon = skill.icon || iconOptions[skillHash % iconOptions.length];
	$: iconBackground = skill.icon_background || iconBackgrounds[skillHash % iconBackgrounds.length];
	$: skillVersion = skill.version
		? skill.version.toLowerCase().startsWith('v')
			? skill.version
			: `v${skill.version}`
		: '未标版本';
	$: skillTags = skill.tags ?? [];
</script>

<div
	class="expert-skill-card group relative flex min-h-[10rem] w-full min-w-[240px] flex-col overflow-hidden rounded-lg border border-[#b9d3ee]/80 bg-white p-3.5 shadow-[0_10px_28px_rgba(16,67,132,0.07),inset_0_1px_0_rgba(255,255,255,0.88)] transition duration-200 hover:-translate-y-0.5 hover:border-[#5f91c7]/60 hover:bg-[#fbfdff] hover:shadow-[0_18px_40px_rgba(16,67,132,0.12),inset_0_1px_0_rgba(255,255,255,0.95)] focus-within:border-[#5f91c7]/60 focus-within:bg-[#fbfdff] focus-within:shadow-[0_18px_40px_rgba(16,67,132,0.12),inset_0_1px_0_rgba(255,255,255,0.95)] dark:border-gray-800 dark:bg-gray-900/92 dark:hover:border-gray-700 dark:hover:bg-gray-900"
>
	<div class="flex items-start justify-between gap-3">
		<div class="flex min-w-0 items-start gap-3">
			<div
				class="skill-icon-block flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-[#31506b]"
				style:background-color={iconBackground}
			>
				<LucideIcon name={skillIcon} className="size-5" strokeWidth="1.9" />
			</div>

			<div class="min-w-0">
				<div
					class="line-clamp-1 text-[15px] font-semibold leading-5 text-[#071f4d] dark:text-gray-100"
				>
					{skill.skill_name}
				</div>
				<div class="mt-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#5f6f8f]">
					{skillVersion}
				</div>
			</div>
		</div>

		<button
			type="button"
			class="flex size-7 shrink-0 items-center justify-center rounded-lg border border-transparent text-[#7f8aa0] transition hover:border-[#d8deea] hover:bg-[#f3f6fb] hover:text-[#3f4a62] dark:text-gray-500 dark:hover:border-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-300"
			aria-label={`查看 ${skill.skill_name} 技能详情`}
			on:click|stopPropagation={() => {
				onDetails(skill);
			}}
		>
			<InfoCircle className="size-3.5" strokeWidth="1.8" />
		</button>
	</div>

	{#if skillTags.length}
		<div class="mt-3 flex flex-wrap items-center gap-1.5">
			{#each skillTags as tag, tagIdx}
				<span
					class="expert-skill-tag inline-flex h-5 min-w-0 max-w-full items-center truncate rounded-md border px-1.5 text-[10px] font-medium leading-none tracking-normal shadow-none"
					style:background-color={tagStyles[tagIdx % tagStyles.length].background}
					style:border-color={tagStyles[tagIdx % tagStyles.length].border}
					style:color={tagStyles[tagIdx % tagStyles.length].color}
					title={tag}
				>
					{tag}
				</span>
			{/each}
		</div>
	{/if}

	<div
		class="skill-description-preview mt-2.5 flex-1 text-[13px] leading-5 text-[#61708f] dark:text-gray-500"
	>
		{skill.description || '暂无描述'}
	</div>

	<div
		class="mt-3 flex items-center justify-between gap-2 border-t border-[#edf1f6] pt-2.5 dark:border-gray-800"
	>
		{#if skill.author}
			<div
				class="min-w-0 truncate text-[11px] font-medium leading-4 text-[#7b8ba8] dark:text-gray-500"
				title={skill.author}
			>
				{skill.author}
			</div>
		{:else}
			<div aria-hidden="true"></div>
		{/if}

		<button
			type="button"
			class="start-chat-button inline-flex h-7 min-w-0 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-[#b9d3ee] bg-white px-3 text-[12px] font-semibold text-[#001f5b] shadow-none transition group-hover:border-[#001f5b] group-hover:bg-[#001f5b] group-hover:text-white group-hover:shadow-[0_10px_24px_rgba(0,31,91,0.18)] hover:bg-[#071f4d] dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:group-hover:border-[#d9e2f5] dark:group-hover:bg-[#d9e2f5] dark:group-hover:text-[#1e2637]"
			on:click={() => onStart(skill)}
		>
			<ChatBubble className="size-3.5" strokeWidth="1.9" />
			开始会话
		</button>
	</div>
</div>

<style>
	.expert-skill-card {
		background: linear-gradient(
			135deg,
			rgba(255, 255, 255, 0.98) 0%,
			rgba(244, 250, 255, 0.9) 100%
		);
	}

	.expert-skill-card::before {
		content: '';
		position: absolute;
		inset: 0;
		z-index: 0;
		border-top: 2px solid rgba(123, 184, 238, 0.72);
		opacity: 0.72;
		transition: opacity 180ms ease;
		pointer-events: none;
	}

	.skill-icon-block {
		background: linear-gradient(145deg, rgba(238, 247, 255, 0.96), rgba(218, 241, 255, 0.86));
		box-shadow:
			0 1px 1px rgba(47, 58, 82, 0.04),
			0 0 0 1px rgba(123, 164, 216, 0.18) inset;
	}

	.start-chat-button {
		transform: translateY(0);
	}

	.expert-skill-card:hover .start-chat-button,
	.expert-skill-card:focus-within .start-chat-button {
		transform: translateY(-1px);
	}

	.expert-skill-card:hover::before,
	.expert-skill-card:focus-within::before {
		opacity: 1;
	}

	:global(.dark) .expert-skill-card::before {
		border-top-color: rgba(154, 166, 200, 0.76);
	}

	.expert-skill-card > :global(*) {
		position: relative;
		z-index: 1;
	}

	.skill-description-preview {
		display: -webkit-box;
		overflow: hidden;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		line-clamp: 2;
	}

	.expert-skill-tag {
		flex: 0 1 auto;
	}
</style>
