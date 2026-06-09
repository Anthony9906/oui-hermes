<script lang="ts">
	import { getContext } from 'svelte';
	import type { Readable } from 'svelte/store';

	import type { ExpertSkillCard } from '$lib/apis/expert-agents';
	import ChatBubble from '$lib/components/icons/ChatBubble.svelte';
	import LucideIcon from './LucideIcon.svelte';

	export let skill: ExpertSkillCard;
	export let onStart: (skill: ExpertSkillCard) => void = () => {};
	export let onDetails: (skill: ExpertSkillCard) => void = () => {};
	export let variant: 'default' | 'featured' = 'default';

	const i18n = getContext<Readable<{ language?: string }>>('i18n');
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
	const recentUpdateWindowMs = 3 * 24 * 60 * 60 * 1000;

	const hashString = (value: string) =>
		Array.from(value || 'expert-agent').reduce((acc, char) => acc + char.charCodeAt(0), 0);
	const isChineseLanguage = (language?: string) => language?.toLowerCase().startsWith('zh');
	const cardCopy = {
		zh: {
			unversioned: '未标版本',
			viewDetails: (skillName: string) => `查看 ${skillName} 技能详情`,
			startChat: '开始对话',
			startChatWith: (skillName: string) => `开始 ${skillName} 对话`,
			noDescription: '暂无描述',
			usageTitle: (count: number) => `使用次数 ${count}`,
			usageWithVersionTitle: (count: number, version: string) =>
				`使用次数 ${count}，版本 ${version}`,
			usageLabel: (count: number) => `使用 ${count}`
		},
		en: {
			unversioned: 'Unversioned',
			viewDetails: (skillName: string) => `View ${skillName} skill details`,
			startChat: 'Start chat',
			startChatWith: (skillName: string) => `Start chat with ${skillName}`,
			noDescription: 'No description',
			usageTitle: (count: number) => `Used ${count}`,
			usageWithVersionTitle: (count: number, version: string) =>
				`Used ${count}, version ${version}`,
			usageLabel: (count: number) => `Used ${count}`
		}
	};
	$: copy = isChineseLanguage($i18n.language) ? cardCopy.zh : cardCopy.en;

	$: skillHash = hashString(skill.skill_name);
	$: skillIcon = skill.icon || iconOptions[skillHash % iconOptions.length];
	$: iconBackground = skill.icon_background || iconBackgrounds[skillHash % iconBackgrounds.length];
	$: skillVersion = skill.version
		? skill.version.toLowerCase().startsWith('v')
			? skill.version
			: `v${skill.version}`
		: copy.unversioned;
	$: skillTags = skill.tags ?? [];
	$: isFeatured = variant === 'featured';
	$: usageCount = skill.usage_count ?? 0;
	$: updatedAtMs = skill.updated_at ? new Date(skill.updated_at).getTime() : Number.NaN;
	$: updatedAgeMs = Date.now() - updatedAtMs;
	$: isRecentlyUpdated =
		Number.isFinite(updatedAtMs) && updatedAgeMs >= 0 && updatedAgeMs <= recentUpdateWindowMs;
</script>

<div
	class="expert-skill-card group relative flex w-full min-w-[240px] flex-col overflow-hidden rounded-xl border border-[#b9d3ee]/80 bg-white shadow-[0_10px_28px_rgba(16,67,132,0.07),inset_0_1px_0_rgba(255,255,255,0.88)] transition duration-200 hover:-translate-y-0.5 hover:border-[#5f91c7]/60 hover:bg-[#fbfdff] hover:shadow-[0_18px_40px_rgba(16,67,132,0.12),inset_0_1px_0_rgba(255,255,255,0.95)] focus-within:border-[#5f91c7]/60 focus-within:bg-[#fbfdff] focus-within:shadow-[0_18px_40px_rgba(16,67,132,0.12),inset_0_1px_0_rgba(255,255,255,0.95)] dark:border-gray-800 dark:bg-gray-900/92 dark:hover:border-gray-700 dark:hover:bg-gray-900 {isFeatured
		? 'expert-skill-card-featured min-h-[14rem] p-3.5'
		: 'min-h-[9.75rem] p-3.5'}"
>
	<div class="flex items-start justify-between gap-3">
		<div class="flex min-w-0 gap-3 {isFeatured ? 'items-start' : 'items-center pr-1'}">
			<div
				class="skill-icon-block flex shrink-0 items-center justify-center rounded-xl text-[#31506b] {isFeatured
					? 'h-14 w-14'
					: 'h-8 w-8 rounded-lg'}"
				style:background-color={iconBackground}
			>
				<LucideIcon
					name={skillIcon}
					className={isFeatured ? 'size-7' : 'size-4'}
					strokeWidth="1.9"
				/>
			</div>

			<div class="min-w-0">
				{#if isFeatured}
					<button
						type="button"
						class="line-clamp-1 max-w-full text-left text-[24px] font-semibold leading-8 text-[#071f4d] transition hover:text-[#0f5ca8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#83bdf1]/60 dark:text-gray-100 dark:hover:text-[#b9d8ff]"
						aria-label={copy.viewDetails(skill.skill_name)}
						title={skill.skill_name}
						on:click|stopPropagation={() => {
							onDetails(skill);
						}}
					>
						{skill.skill_name}
					</button>
					<div
						class="mt-0.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#5f6f8f]"
					>
						<span class="version-badge">{skillVersion}</span>
						{#if isRecentlyUpdated}
							<span class="updated-badge">UPDATED</span>
						{/if}
					</div>
				{:else}
					<button
						type="button"
						class="line-clamp-1 max-w-full text-left text-[15px] font-semibold leading-5 text-[#071f4d] transition hover:text-[#0f5ca8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#83bdf1]/60 dark:text-gray-100 dark:hover:text-[#b9d8ff]"
						aria-label={copy.viewDetails(skill.skill_name)}
						title={skill.skill_name}
						on:click|stopPropagation={() => {
							onDetails(skill);
						}}
					>
						{skill.skill_name}
					</button>
				{/if}
			</div>
		</div>

		{#if isFeatured}
			<button
				type="button"
				class="start-chat-button inline-flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-[#001f5b] bg-[#001f5b] px-3.5 text-[12px] font-semibold text-white shadow-[0_10px_22px_rgba(0,31,91,0.22)] transition hover:border-[#071f4d] hover:bg-[#071f4d] dark:border-gray-100 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-white"
				on:click={() => onStart(skill)}
			>
				<ChatBubble className="size-4" strokeWidth="1.9" />
				{copy.startChat}
			</button>
		{:else}
			<button
				type="button"
				class="start-chat-button inline-flex size-8 shrink-0 items-center justify-center rounded-lg border border-[#b9d3ee] bg-white text-[#001f5b] shadow-none transition group-hover:border-[#001f5b] group-hover:bg-[#001f5b] group-hover:text-white group-hover:shadow-[0_10px_24px_rgba(0,31,91,0.18)] hover:bg-[#071f4d] dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:group-hover:border-[#d9e2f5] dark:group-hover:bg-[#d9e2f5] dark:group-hover:text-[#1e2637]"
				aria-label={copy.startChatWith(skill.skill_name)}
				title={copy.startChat}
				on:click={() => onStart(skill)}
			>
				<ChatBubble className="size-4" strokeWidth="1.9" />
			</button>
		{/if}
	</div>

	{#if isFeatured}
		<div class="featured-core-visual" aria-hidden="true">
			<img
				src="/assets/images/expert-agent/expert-agent-builder-agent-icons-only-transparent.png"
				alt=""
				loading="lazy"
				draggable="false"
			/>
		</div>
	{/if}

	{#if !isFeatured && skillTags.length}
		<div
			class="expert-skill-tags-scroll mt-3 flex flex-nowrap items-center gap-1 overflow-x-auto overflow-y-hidden"
		>
			{#each skillTags as tag, tagIdx}
				<span
					class="expert-skill-tag inline-flex h-[18px] max-w-[9rem] shrink-0 items-center truncate rounded border px-1 text-[9.5px] font-medium leading-none tracking-normal shadow-none"
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
		class="skill-description-preview flex-1 dark:text-gray-500 {isFeatured
			? 'mt-3 max-w-[65%] text-[13px] leading-5 text-[#61708f]'
			: 'mt-2.5 text-[11px] leading-4 text-[#8a99b0]'}"
	>
		{skill.description || copy.noDescription}
	</div>

	{#if isFeatured}
		<div
			class="featured-meta-row mt-3 flex max-w-[55%] items-center gap-3 text-[11px] font-medium leading-4 text-[#6f84a4] dark:text-gray-500"
		>
			{#if skill.author}
				<div class="min-w-0 flex items-center gap-1.5 truncate" title={skill.author}>
					<LucideIcon name="user" className="size-3.5 shrink-0 text-[#9db0c7]" strokeWidth="1.8" />
					<span class="truncate">{skill.author}</span>
				</div>
			{/if}
			<div
				class="shrink-0 flex items-center gap-1.5 text-[#7d91ae]"
				title={copy.usageTitle(usageCount)}
			>
				<LucideIcon name="bookmark-check" className="size-3.5" strokeWidth="1.8" />
				<span>{copy.usageLabel(usageCount)}</span>
			</div>
		</div>
	{:else}
		<div class="mt-3 flex items-center gap-3 border-t border-[#edf1f6] pt-2.5 dark:border-gray-800">
			<div
				class="min-w-0 flex items-center gap-3 text-[11px] font-medium leading-4 text-[#7b8ba8] dark:text-gray-500"
			>
				{#if skill.author}
					<div class="min-w-0 flex items-center gap-1.5 truncate" title={skill.author}>
						<LucideIcon
							name="user"
							className="size-3.5 shrink-0 text-[#9db0c7]"
							strokeWidth="1.8"
						/>
						<span class="truncate">{skill.author}</span>
					</div>
				{/if}
				<div
					class="shrink-0 flex items-center gap-1.5 text-[#8da0ba]"
					title={copy.usageWithVersionTitle(usageCount, skillVersion)}
				>
					<LucideIcon name="bookmark-check" className="size-3.5" strokeWidth="1.8" />
					<span>{copy.usageLabel(usageCount)}</span>
					<span class="version-badge">{skillVersion}</span>
					{#if isRecentlyUpdated}
						<span class="updated-badge">UPDATED</span>
					{/if}
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.expert-skill-card {
		background: linear-gradient(
			135deg,
			rgba(255, 255, 255, 0.98) 0%,
			rgba(244, 250, 255, 0.9) 100%
		);
	}

	.expert-skill-card-featured {
		background:
			radial-gradient(
				ellipse at 6% 0%,
				rgba(112, 188, 255, 0.34) 0%,
				rgba(185, 226, 255, 0.18) 36%,
				transparent 58%
			),
			linear-gradient(
				135deg,
				rgba(255, 255, 255, 0.98) 0%,
				rgba(241, 248, 255, 0.94) 56%,
				rgba(255, 255, 255, 0.98) 100%
			);
	}

	.featured-core-visual {
		position: absolute;
		right: 0.45rem;
		bottom: 0.25rem;
		width: auto;
		height: 66%;
		z-index: 0;
		pointer-events: none;
		opacity: 0.78;
	}

	.featured-core-visual img {
		width: auto;
		height: 100%;
		object-fit: contain;
		transform: scale(1);
		transform-origin: right bottom;
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

	.expert-skill-card > .featured-core-visual {
		position: absolute;
		z-index: 0;
	}

	.skill-description-preview {
		display: -webkit-box;
		overflow: hidden;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 3;
		line-clamp: 3;
	}

	.expert-skill-card-featured .skill-description-preview {
		-webkit-line-clamp: 3;
		line-clamp: 3;
	}

	.expert-skill-tag {
		flex: 0 0 auto;
	}

	.expert-skill-tags-scroll {
		-webkit-overflow-scrolling: touch;
		scrollbar-width: none;
		touch-action: pan-x;
	}

	.expert-skill-tags-scroll::-webkit-scrollbar {
		display: none;
	}

	.version-badge,
	.updated-badge {
		display: inline-flex;
		height: 0.8125rem;
		align-items: center;
		border-radius: 0.1875rem;
		padding: 0 0.2rem;
		font-size: 0.5rem;
		font-weight: 700;
		letter-spacing: 0.035em;
		line-height: 1;
	}

	.version-badge {
		background: rgba(100, 116, 139, 0.075);
		border: 1px solid rgba(100, 116, 139, 0.14);
		color: #738199;
	}

	.updated-badge {
		background: rgba(34, 197, 94, 0.075);
		border: 1px solid rgba(34, 197, 94, 0.14);
		color: #22a35a;
	}
</style>
