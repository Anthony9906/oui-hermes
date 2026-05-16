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
</script>

<div
	class="expert-skill-card group relative flex min-h-[8.75rem] w-full min-w-[240px] flex-col overflow-hidden rounded-xl border border-[#d8deea] bg-white/92 p-3.5 shadow-[0_1px_2px_rgba(64,74,96,0.05)] transition duration-200 hover:-translate-y-0.5 hover:border-[#aeb9cc] hover:bg-white hover:shadow-[0_18px_38px_rgba(77,88,116,0.16)] focus-within:border-[#aeb9cc] focus-within:bg-white focus-within:shadow-[0_18px_38px_rgba(77,88,116,0.16)] dark:border-gray-800 dark:bg-gray-900/92 dark:hover:border-gray-700 dark:hover:bg-gray-900"
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
					class="line-clamp-1 text-[15px] font-semibold leading-5 text-[#232c40] dark:text-gray-100"
				>
					{skill.skill_name}
				</div>
				<div class="mt-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#8b96aa]">
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

	<div
		class="skill-description-preview mt-3 flex-1 text-[13px] leading-5 text-[#8b96aa] dark:text-gray-500"
	>
		{skill.description || '暂无描述'}
	</div>

	<div
		class="mt-3 flex items-center justify-between gap-2 border-t border-[#edf1f6] pt-2.5 dark:border-gray-800"
	>
		{#if skill.author}
			<div
				class="min-w-0 truncate text-[11px] font-medium leading-4 text-[#9aa4b5] dark:text-gray-500"
				title={skill.author}
			>
				{skill.author}
			</div>
		{:else}
			<div aria-hidden="true" />
		{/if}

		<button
			type="button"
			class="start-chat-button inline-flex h-7 min-w-0 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-[#d8deea] bg-white px-3 text-[12px] font-semibold text-[#667289] shadow-none transition group-hover:border-[#2f3a52] group-hover:bg-[#2f3a52] group-hover:text-white group-hover:shadow-[0_10px_24px_rgba(47,58,82,0.2)] hover:bg-[#222b3f] dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:group-hover:border-[#d9e2f5] dark:group-hover:bg-[#d9e2f5] dark:group-hover:text-[#1e2637]"
			on:click={() => onStart(skill)}
		>
			<ChatBubble className="size-3.5" strokeWidth="1.9" />
			开始会话
		</button>
	</div>
</div>

<style>
	.expert-skill-card::before {
		content: '';
		position: absolute;
		inset: 0 auto 0 0;
		z-index: 0;
		width: 3px;
		background: linear-gradient(180deg, #6f7f9e 0%, #8ba16d 100%);
		opacity: 0.72;
		transition: opacity 180ms ease;
	}

	.skill-icon-block {
		box-shadow:
			0 1px 1px rgba(47, 58, 82, 0.04),
			0 0 0 1px rgba(255, 255, 255, 0.78) inset;
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
		background: linear-gradient(180deg, #9aa6c8 0%, #8ba16d 100%);
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
	}
</style>
