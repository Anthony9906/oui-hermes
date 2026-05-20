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
	$: displayedPrompts = filteredPrompts.slice(0, 2);

	const promptTagStyles = [
		{ background: '#eef2f6', color: '#5f6f82', border: '#dde5ee' },
		{ background: '#eef4f0', color: '#607568', border: '#dfe9e2' },
		{ background: '#f4f1ec', color: '#7a6955', border: '#e8e1d7' },
		{ background: '#f1f0f5', color: '#6d6681', border: '#e3e0eb' },
		{ background: '#edf3f4', color: '#5f7479', border: '#dce8ea' }
	];

	const getPromptText = (prompt) => {
		const title = Array.isArray(prompt?.title) ? prompt.title.join(' ') : prompt?.title;
		return `${title ?? ''} ${prompt?.content ?? ''}`.toLowerCase();
	};
	const getPromptPriority = (prompt) => {
		const text = getPromptText(prompt);

		if (
			text.includes('standard parts selection') ||
			text.includes('标准件') ||
			text.includes('选型') ||
			text.includes('模组')
		) {
			return 0;
		}
		if (text.includes('plc flow chart') || text.includes('plc') || text.includes('流程')) {
			return 1;
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

		if (
			text.includes('standard parts selection') ||
			text.includes('标准件') ||
			text.includes('选型') ||
			text.includes('模组')
		) {
			return 'swatch-book';
		}
		if (text.includes('plc flow chart') || text.includes('plc') || text.includes('流程')) {
			return 'git-pull-request';
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
		const text = getPromptText(prompt);

		if (
			text.includes('standard parts selection') ||
			text.includes('标准件') ||
			text.includes('选型') ||
			text.includes('模组')
		) {
			return '/assets/images/expert-agent/skill-card-standard-parts-sketch.png';
		}
		if (text.includes('plc flow chart') || text.includes('plc') || text.includes('流程')) {
			return '/assets/images/expert-agent/skill-card-plc-sketch.png';
		}

		return '/assets/images/expert-agent/skill-card-standard-parts-sketch.png';
	};

	const getPromptTags = (prompt) => {
		const text = getPromptText(prompt);

		if (
			text.includes('standard parts selection') ||
			text.includes('标准件') ||
			text.includes('选型') ||
			text.includes('模组')
		) {
			return ['Agentic', 'Multi-series', 'Recommendation'];
		}
		if (text.includes('plc flow chart') || text.includes('plc') || text.includes('流程')) {
			return ['Mermaid', 'Programmable'];
		}

		return [];
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

	$: sortedPrompts = sortPromptSuggestions(suggestionPrompts ?? []);
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
			class="grid w-full max-w-none grid-cols-1 items-stretch gap-5 @2xl:grid-cols-2 {className}"
			style="gap: calc(var(--spacing) * 15) !important"
		>
			{#each displayedPrompts as prompt, idx (prompt.id || `${prompt.content}-${idx}`)}
				<!-- svelte-ignore a11y-no-interactive-element-to-noninteractive-role -->
				<button
					role="listitem"
					class="suggestion-card waterfall group flex min-h-[172px] w-full items-start gap-5 overflow-hidden rounded-lg px-6 py-5 text-left transition duration-200"
					style="animation-delay: {idx * 60}ms"
					on:click={() => onSelect({ type: 'prompt', data: prompt.content, prompt })}
				>
					<div class="suggestion-content flex min-w-0 items-start gap-5">
						<div
							class="suggestion-icon flex size-14 shrink-0 items-center justify-center rounded-lg text-[#001f5b]"
						>
							<LucideIcon name={getPromptIconName(prompt)} className="size-7" strokeWidth="1.8" />
						</div>
						<div class="flex min-w-0 flex-col text-left">
							{#if prompt.title && prompt.title[0] !== ''}
								<div
									class="text-[1.05rem] font-semibold leading-6 text-[#071f4d] transition line-clamp-1 dark:text-gray-300 dark:group-hover:text-gray-100"
								>
									{prompt.title[0]}
								</div>
								{#if getPromptTags(prompt).length}
									<div class="mt-2 flex flex-nowrap items-center gap-1.5 whitespace-nowrap">
										{#each getPromptTags(prompt) as tag, tagIdx}
											<span
												class="suggestion-tag inline-flex h-5 items-center rounded-md border px-1.5 text-[10px] font-medium leading-none tracking-normal shadow-none"
												style:background-color={promptTagStyles[tagIdx].background}
												style:border-color={promptTagStyles[tagIdx].border}
												style:color={promptTagStyles[tagIdx].color}
											>
												{tag}
											</span>
										{/each}
									</div>
								{/if}
								<div
									class="mt-1.5 text-sm leading-6 text-[#61708f] dark:text-gray-400 font-normal line-clamp-3"
								>
									{prompt.title[1]}
								</div>
							{:else}
								<div
									class="text-[1.05rem] font-semibold leading-6 text-[#071f4d] transition line-clamp-1 dark:text-gray-300 dark:group-hover:text-gray-100"
								>
									{prompt.content}
								</div>
								{#if getPromptTags(prompt).length}
									<div class="mt-2 flex flex-nowrap items-center gap-1.5 whitespace-nowrap">
										{#each getPromptTags(prompt) as tag, tagIdx}
											<span
												class="suggestion-tag inline-flex h-5 items-center rounded-md border px-1.5 text-[10px] font-medium leading-none tracking-normal shadow-none"
												style:background-color={promptTagStyles[tagIdx].background}
												style:border-color={promptTagStyles[tagIdx].border}
												style:color={promptTagStyles[tagIdx].color}
											>
												{tag}
											</span>
										{/each}
									</div>
								{/if}
								<div
									class="mt-1.5 text-sm leading-6 text-[#61708f] dark:text-gray-400 font-normal line-clamp-3"
								>
									{$i18n.t('Prompt')}
								</div>
							{/if}
						</div>
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
		min-height: 180px;
	}

	.suggestion-content {
		position: relative;
		z-index: 1;
		padding-right: min(24%, 8rem);
	}

	.suggestion-tag {
		flex: 0 0 auto;
		white-space: nowrap;
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

	.suggestion-icon {
		background:
			linear-gradient(145deg, rgba(238, 247, 255, 0.96), rgba(218, 241, 255, 0.86)),
			radial-gradient(circle at 28% 24%, rgba(123, 220, 255, 0.36), transparent 42%);
		box-shadow: inset 0 0 0 1px rgba(123, 164, 216, 0.18);
	}

	.suggestion-card:hover .suggestion-icon {
		background:
			linear-gradient(145deg, rgba(225, 246, 255, 0.98), rgba(203, 232, 255, 0.9)),
			radial-gradient(circle at 32% 28%, rgba(123, 220, 255, 0.48), transparent 44%);
	}

	.suggestion-sketch {
		position: absolute;
		right: 0.5rem;
		bottom: 0.35rem;
		width: min(38%, 14rem);
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
