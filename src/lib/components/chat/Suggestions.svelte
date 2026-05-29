<script lang="ts">
	import Fuse from 'fuse.js';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import { getContext } from 'svelte';
	import LucideIcon from '$lib/components/expert-agents/LucideIcon.svelte';

	const i18n = getContext('i18n');

	export let suggestionPrompts = [];
	export let className = '';
	export let inputValue = '';
	export let onSelect = (e) => {};

	let sortedPrompts = [];

	const fuseOptions = {
		keys: ['content', 'title'],
		threshold: 0.5
	};

	let fuse;
	let filteredPrompts = [];
	$: displayedPrompts = filteredPrompts.slice(0, 3);
	$: activeLanguage = $i18n.language;

	const normalizeTitle = (title) => {
		if (typeof title === 'string') {
			return [title, ''];
		}

		if (Array.isArray(title)) {
			return [title[0] ?? '', title[1] ?? ''];
		}

		return ['', ''];
	};

	const isChineseLanguage = (language) => language?.toLowerCase().startsWith('zh');

	const hasLocalizedPromptContent = (localizedPrompt) => {
		const title = normalizeTitle(localizedPrompt?.title);
		return Boolean(title[0] || title[1] || localizedPrompt?.content);
	};

	const getLocalizedPrompt = (prompt, language) => {
		const fallbackPrompt = {
			...prompt,
			title: normalizeTitle(prompt?.title),
			content: prompt?.content ?? ''
		};

		if (!isChineseLanguage(language)) {
			return fallbackPrompt;
		}

		const localizedPrompt = prompt?.locales?.['zh-CN'] ?? prompt?.locales?.zh;

		if (!hasLocalizedPromptContent(localizedPrompt)) {
			return fallbackPrompt;
		}

		const localizedTitle = normalizeTitle(localizedPrompt.title);

		return {
			...prompt,
			title: [
				localizedTitle[0] || fallbackPrompt.title[0],
				localizedTitle[1] || fallbackPrompt.title[1]
			],
			content: localizedPrompt.content || fallbackPrompt.content
		};
	};

	const getPromptText = (prompt) => {
		const title = Array.isArray(prompt?.title) ? prompt.title.join(' ') : prompt?.title;
		return `${title ?? ''} ${prompt?.content ?? ''}`.toLowerCase();
	};

	const getPromptCase = (prompt) => {
		const text = getPromptText(prompt);

		if (
			text.includes('tray transfer') ||
			text.includes('tray盘') ||
			text.includes('tray 盘') ||
			text.includes('水平搬运') ||
			text.includes('水平移载') ||
			text.includes('345')
		) {
			return 'tray-transfer';
		}

		if (
			text.includes('180° rotary fixture') ||
			text.includes('180 rotary fixture') ||
			text.includes('rotary fixture') ||
			text.includes('rotary cylinder') ||
			text.includes('旋转') ||
			text.includes('180')
		) {
			return 'rotary-fixture';
		}

		if (
			text.includes('pallet lifter') ||
			text.includes('lifting') ||
			text.includes('lifter') ||
			text.includes('顶升') ||
			text.includes('载具') ||
			text.includes('20mm') ||
			text.includes('20 mm')
		) {
			return 'pallet-lifter';
		}

		return '';
	};

	const getPromptPriority = (prompt) => {
		const promptCase = getPromptCase(prompt);

		if (promptCase === 'tray-transfer') {
			return 0;
		}

		if (promptCase === 'rotary-fixture') {
			return 1;
		}

		if (promptCase === 'pallet-lifter') {
			return 2;
		}

		return 10;
	};
	const sortPromptSuggestions = (prompts) =>
		[...(prompts ?? [])]
			.map((prompt, index) => ({ prompt, index, priority: getPromptPriority(prompt) }))
			.sort((a, b) => a.priority - b.priority || a.index - b.index)
			.map((item) => item.prompt);

	const getPromptIconName = (prompt) => {
		const text = getPromptText(prompt);
		const promptCase = getPromptCase(prompt);

		if (promptCase === 'tray-transfer') {
			return 'send-to-back';
		}

		if (promptCase === 'rotary-fixture') {
			return 'refresh-ccw-dot';
		}

		if (promptCase === 'pallet-lifter') {
			return 'banknote-arrow-up';
		}

		if (text.includes('3d') || text.includes('方案') || text.includes('设计')) {
			return 'package';
		}
		if (text.includes('需求') || text.includes('分析')) {
			return 'clipboard-list';
		}

		return 'sparkles';
	};

	const getPromptSketchImage = (prompt) => {
		const promptCase = getPromptCase(prompt);

		if (promptCase === 'tray-transfer') {
			return '/assets/images/expert-agent/skill-card-tray-transfer-sketch.png';
		}

		if (promptCase === 'rotary-fixture') {
			return '/assets/images/expert-agent/skill-card-rotary-fixture-sketch.png';
		}

		if (promptCase === 'pallet-lifter') {
			return '/assets/images/expert-agent/skill-card-pallet-lifter-sketch.png';
		}

		return '/assets/images/expert-agent/skill-card-standard-parts-sketch.png';
	};

	// Initialize Fuse
	$: fuse = new Fuse(sortedPrompts, fuseOptions);

	const getFilteredPrompts = (inputValue, prompts, promptFuse) => {
		if (inputValue.length > 500) {
			return [];
		}

		return inputValue.trim() && promptFuse
			? promptFuse.search(inputValue.trim()).map((result) => result.item)
			: prompts;
	};

	$: localizedPrompts = (suggestionPrompts ?? []).map((prompt) =>
		getLocalizedPrompt(prompt, activeLanguage)
	);
	$: sortedPrompts = sortPromptSuggestions(localizedPrompts ?? []);
	$: filteredPrompts = getFilteredPrompts(inputValue, sortedPrompts, fuse);
</script>

{#if displayedPrompts.length > 0}
	<div
		class="mb-4 flex items-center gap-1.5 text-[13px] font-medium text-[#5f6f8f] dark:text-gray-400"
	>
		<Bolt />
		{$i18n.t('Suggested')}
	</div>
{/if}

<div class="w-full">
	{#if displayedPrompts.length > 0}
		<div
			role="list"
			class="grid w-full max-w-none grid-cols-1 items-stretch gap-4 @2xl:grid-cols-2 @4xl:grid-cols-3 {className}"
		>
			{#each displayedPrompts as prompt, idx (prompt.id || `${prompt.content}-${idx}`)}
				<!-- svelte-ignore a11y-no-interactive-element-to-noninteractive-role -->
				<button
					role="listitem"
					class="suggestion-card waterfall group flex min-h-[146px] w-full items-start gap-4 overflow-hidden rounded-lg px-4 py-4 text-left transition duration-200"
					style="animation-delay: {idx * 60}ms"
					on:click={() => onSelect({ type: 'prompt', data: prompt.content, prompt })}
				>
					<div class="suggestion-content flex min-w-0 flex-col text-left">
						{#if prompt.title && prompt.title[0] !== ''}
							<div class="flex min-w-0 items-center gap-2.5">
								<LucideIcon
									name={getPromptIconName(prompt)}
									className="suggestion-icon size-5 shrink-0 text-[#31506b]"
									strokeWidth="1.9"
								/>
								<div
									class="text-[1.12rem] font-semibold leading-6 text-[#071f4d] transition line-clamp-1 dark:text-gray-300 dark:group-hover:text-gray-100"
								>
									{prompt.title[0]}
								</div>
							</div>
							<div
								class="mt-2 text-[13px] leading-5 text-[#61708f] dark:text-gray-400 font-normal line-clamp-3"
							>
								{prompt.title[1]}
							</div>
						{:else}
							<div class="flex min-w-0 items-center gap-2.5">
								<LucideIcon
									name={getPromptIconName(prompt)}
									className="suggestion-icon size-5 shrink-0 text-[#31506b]"
									strokeWidth="1.9"
								/>
								<div
									class="text-[1.12rem] font-semibold leading-6 text-[#071f4d] transition line-clamp-1 dark:text-gray-300 dark:group-hover:text-gray-100"
								>
									{prompt.content}
								</div>
							</div>
							<div
								class="mt-2 text-[13px] leading-5 text-[#61708f] dark:text-gray-400 font-normal line-clamp-3"
							>
								{$i18n.t('Prompt')}
							</div>
						{/if}
					</div>

					<div class="suggestion-sketch" aria-hidden="true">
						<img src={getPromptSketchImage(prompt)} alt="" loading="lazy" draggable="false" />
					</div>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	/* Waterfall animation for the suggestions */
	@keyframes fadeInUp {
		0% {
			opacity: 0;
			transform: translateY(20px);
		}
		100% {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.waterfall {
		opacity: 0;
		animation-name: fadeInUp;
		animation-duration: 200ms;
		animation-fill-mode: forwards;
		animation-timing-function: ease;
	}

	.suggestion-card {
		position: relative;
		isolation: isolate;
		border: 1px solid rgba(138, 185, 238, 0.46);
		background:
			linear-gradient(135deg, rgba(255, 255, 255, 0.94) 0%, rgba(244, 250, 255, 0.86) 100%),
			radial-gradient(circle at 12% 16%, rgba(123, 220, 255, 0.22), transparent 34%);
		box-shadow:
			0 14px 34px rgba(16, 67, 132, 0.08),
			inset 0 1px 0 rgba(255, 255, 255, 0.88);
		backdrop-filter: blur(14px);
		min-height: 146px;
	}

	.suggestion-content {
		position: relative;
		z-index: 1;
		padding-right: min(26%, 6rem);
	}

	.suggestion-card::before {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: inherit;
		border-top: 2px solid rgba(123, 220, 255, 0.72);
		opacity: 0.68;
		pointer-events: none;
	}

	.suggestion-card:hover {
		border-color: rgba(47, 111, 196, 0.42);
		background:
			linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(238, 248, 255, 0.92) 100%),
			radial-gradient(circle at 86% 20%, rgba(88, 201, 255, 0.22), transparent 32%);
		box-shadow:
			0 18px 42px rgba(16, 67, 132, 0.12),
			inset 0 1px 0 rgba(255, 255, 255, 0.92);
		transform: translateY(-2px);
	}

	.suggestion-sketch {
		position: absolute;
		right: 0.5rem;
		bottom: 0.35rem;
		width: min(34%, 8rem);
		z-index: 0;
		pointer-events: none;
		transition: transform 200ms ease;
	}

	.suggestion-sketch img {
		display: block;
		width: 100%;
		height: auto;
		user-select: none;
	}

	.suggestion-card:hover .suggestion-sketch {
		transform: translate(-2px, -2px);
	}

	@media (prefers-reduced-motion: reduce) {
		.waterfall {
			animation: none;
			opacity: 1;
		}

		.suggestion-card:hover {
			transform: none;
		}

		.suggestion-card:hover .suggestion-sketch {
			transform: none;
		}
	}
</style>
