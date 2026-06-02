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

	const MAX_DISPLAYED_PROMPTS = 6;

	let sortedPrompts = [];

	const fuseOptions = {
		keys: ['content', 'title'],
		threshold: 0.5
	};

	let fuse;
	let filteredPrompts = [];
	let pendingPrompt = null;
	$: displayedPrompts = filteredPrompts.slice(0, MAX_DISPLAYED_PROMPTS);
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

	const PROMPT_CARD_IDS = {
		trayTransfer: 'tray-transfer',
		rotaryFixture: 'rotary-fixture',
		palletLifter: 'pallet-lifter',
		kkModuleHighSpeed: 'kk-module-high-speed',
		flipMotorSelection: 'flip-motor-selection'
	};

	const promptCardIdSet = new Set(Object.values(PROMPT_CARD_IDS));

	const normalizePromptId = (id) => (typeof id === 'string' ? id.trim().toLowerCase() : '');

	const PROMPT_CARD_TYPES = {
		cylinder: 'cylinder',
		motor: 'motor'
	};

	const getPromptCase = (prompt) => {
		const promptId = normalizePromptId(prompt?.id);
		if (promptCardIdSet.has(promptId)) {
			return promptId;
		}

		const text = getPromptText(prompt);

		if (
			text.includes('kk module high-speed') ||
			text.includes('kk module high speed') ||
			(text.includes('kk module') && text.includes('pick') && text.includes('place')) ||
			text.includes('kk模组高速取放') ||
			(text.includes('kk模组') && text.includes('高速取放')) ||
			text.includes('kk60d10c')
		) {
			return PROMPT_CARD_IDS.kkModuleHighSpeed;
		}

		if (
			text.includes('flip mechanism motor selection') ||
			(text.includes('flip mechanism') && text.includes('motor')) ||
			text.includes('horizontal-axis flip') ||
			text.includes('翻转机构电机选型') ||
			(text.includes('翻转机构') && text.includes('电机'))
		) {
			return PROMPT_CARD_IDS.flipMotorSelection;
		}

		if (
			text.includes('tray transfer') ||
			text.includes('tray盘') ||
			text.includes('tray 盘') ||
			text.includes('水平搬运') ||
			text.includes('水平移载') ||
			text.includes('345')
		) {
			return PROMPT_CARD_IDS.trayTransfer;
		}

		if (
			text.includes('180° rotary fixture') ||
			text.includes('180 rotary fixture') ||
			text.includes('rotary fixture') ||
			text.includes('rotary cylinder') ||
			text.includes('旋转') ||
			text.includes('180')
		) {
			return PROMPT_CARD_IDS.rotaryFixture;
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
			return PROMPT_CARD_IDS.palletLifter;
		}

		return '';
	};

	const getPromptPriority = (prompt) => {
		const promptCase = getPromptCase(prompt);

		if (promptCase === PROMPT_CARD_IDS.trayTransfer) {
			return 0;
		}

		if (promptCase === PROMPT_CARD_IDS.rotaryFixture) {
			return 1;
		}

		if (promptCase === PROMPT_CARD_IDS.palletLifter) {
			return 2;
		}

		if (promptCase === PROMPT_CARD_IDS.kkModuleHighSpeed) {
			return 3;
		}

		if (promptCase === PROMPT_CARD_IDS.flipMotorSelection) {
			return 4;
		}

		return 10;
	};

	const getPromptType = (prompt) => {
		const promptCase = getPromptCase(prompt);

		if (
			promptCase === PROMPT_CARD_IDS.trayTransfer ||
			promptCase === PROMPT_CARD_IDS.rotaryFixture ||
			promptCase === PROMPT_CARD_IDS.palletLifter
		) {
			return PROMPT_CARD_TYPES.cylinder;
		}

		if (
			promptCase === PROMPT_CARD_IDS.kkModuleHighSpeed ||
			promptCase === PROMPT_CARD_IDS.flipMotorSelection
		) {
			return PROMPT_CARD_TYPES.motor;
		}

		return '';
	};

	const getPromptTypeLabel = (prompt) => {
		const promptType = getPromptType(prompt);
		const isChinese = isChineseLanguage(activeLanguage);

		if (promptType === PROMPT_CARD_TYPES.cylinder) {
			return isChinese ? '气缸' : 'Cylinder';
		}

		if (promptType === PROMPT_CARD_TYPES.motor) {
			return isChinese ? '电机' : 'Motor';
		}

		return '';
	};

	const sortPromptSuggestions = (prompts) =>
		[...(prompts ?? [])]
			.map((prompt, index) => ({ prompt, index, priority: getPromptPriority(prompt) }))
			.sort((a, b) => a.priority - b.priority || a.index - b.index)
			.map((item) => item.prompt);

	const getPromptIconName = (prompt) => {
		const text = getPromptText(prompt);
		const promptCase = getPromptCase(prompt);

		if (promptCase === PROMPT_CARD_IDS.trayTransfer) {
			return 'combine';
		}

		if (promptCase === PROMPT_CARD_IDS.rotaryFixture) {
			return 'repeat';
		}

		if (promptCase === PROMPT_CARD_IDS.palletLifter) {
			return 'banknote-arrow-up';
		}

		if (promptCase === PROMPT_CARD_IDS.kkModuleHighSpeed) {
			return 'send-to-back';
		}

		if (promptCase === PROMPT_CARD_IDS.flipMotorSelection) {
			return 'refresh-ccw-dot';
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

		if (promptCase === PROMPT_CARD_IDS.trayTransfer) {
			return '/assets/images/expert-agent/skill-card-tray-transfer-sketch.png';
		}

		if (promptCase === PROMPT_CARD_IDS.rotaryFixture) {
			return '/assets/images/expert-agent/skill-card-rotary-fixture-sketch.png';
		}

		if (promptCase === PROMPT_CARD_IDS.palletLifter) {
			return '/assets/images/expert-agent/skill-card-pallet-lifter-sketch.png';
		}

		if (promptCase === PROMPT_CARD_IDS.kkModuleHighSpeed) {
			return '/assets/images/expert-agent/skill-card-kk-module-high-speed-sketch.png';
		}

		if (promptCase === PROMPT_CARD_IDS.flipMotorSelection) {
			return '/assets/images/expert-agent/skill-card-flip-motor-selection-sketch.png';
		}

		return '/assets/images/expert-agent/skill-card-standard-parts-sketch.png';
	};

	const getPromptDisplayTitle = (prompt) => {
		const title = normalizeTitle(prompt?.title);
		return (
			title[0] ||
			prompt?.content ||
			(isChineseLanguage(activeLanguage) ? '快速体验' : 'Quick Experience')
		);
	};

	const getConfirmationCopy = (promptTitle) => {
		if (isChineseLanguage(activeLanguage)) {
			return {
				title: '开始体验 AI 选型',
				messagePrefix: '看看 AI 如何完成 ',
				scenario: promptTitle,
				messageSuffix: ' 场景的标准件选型任务，\n这会开启一个新的会话。',
				start: '开始',
				cancel: '取消'
			};
		}

		return {
			title: 'Start AI Selection',
			messagePrefix: 'See how AI completes the standard-parts selection task for the ',
			scenario: `"${promptTitle}"`,
			messageSuffix: ' scenario.\nThis will open a new chat.',
			start: 'Start',
			cancel: 'Cancel'
		};
	};

	const openPromptConfirmation = (prompt) => {
		pendingPrompt = prompt;
	};

	const closePromptConfirmation = () => {
		pendingPrompt = null;
	};

	const confirmPromptSelection = () => {
		const prompt = pendingPrompt;
		closePromptConfirmation();

		if (prompt) {
			onSelect({ type: 'prompt', data: prompt.content, prompt });
		}
	};

	const handleConfirmationKeydown = (event) => {
		if (!pendingPrompt) {
			return;
		}

		if (event.key === 'Escape') {
			event.preventDefault();
			closePromptConfirmation();
		}
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
	$: pendingPromptTitle = pendingPrompt ? getPromptDisplayTitle(pendingPrompt) : '';
	$: confirmationCopy = getConfirmationCopy(pendingPromptTitle);
</script>

<svelte:window on:keydown={handleConfirmationKeydown} />

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
					class="suggestion-card waterfall group flex min-h-[131px] w-full items-start gap-4 overflow-hidden rounded-lg px-4 py-4 text-left transition duration-200"
					style="animation-delay: {idx * 60}ms"
					on:click={() => openPromptConfirmation(prompt)}
				>
					{#if getPromptTypeLabel(prompt)}
						<div
							class="suggestion-type-badge"
							class:suggestion-type-badge--motor={getPromptType(prompt) === PROMPT_CARD_TYPES.motor}
						>
							{getPromptTypeLabel(prompt)}
						</div>
					{/if}

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

{#if pendingPrompt}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div
		class="experience-confirm-backdrop"
		role="presentation"
		on:pointerdown={closePromptConfirmation}
	>
		<div
			class="experience-confirm-dialog"
			role="dialog"
			aria-modal="true"
			aria-labelledby="experience-confirm-title"
			aria-describedby="experience-confirm-message"
			tabindex="-1"
			on:pointerdown|stopPropagation
		>
			<div class="experience-confirm-emoji" aria-hidden="true">✨</div>
			<div id="experience-confirm-title" class="experience-confirm-title">
				{confirmationCopy.title}
			</div>
			<div id="experience-confirm-message" class="experience-confirm-message">
				{confirmationCopy.messagePrefix}<strong>{confirmationCopy.scenario}</strong
				>{confirmationCopy.messageSuffix}
			</div>
			<div class="experience-confirm-actions">
				<button
					type="button"
					class="experience-confirm-button experience-confirm-button--cancel"
					on:click={closePromptConfirmation}
				>
					{confirmationCopy.cancel}
				</button>
				<button
					type="button"
					class="experience-confirm-button experience-confirm-button--start"
					on:click={confirmPromptSelection}
				>
					{confirmationCopy.start}
				</button>
			</div>
		</div>
	</div>
{/if}

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
		min-height: 131px;
	}

	.suggestion-content {
		position: relative;
		z-index: 1;
		padding-right: min(26%, 6rem);
	}

	.suggestion-type-badge {
		position: absolute;
		top: 0.75rem;
		right: 0.75rem;
		z-index: 2;
		border-radius: 999px;
		background: rgba(218, 246, 225, 0.92);
		color: #166534;
		font-size: 11px;
		font-weight: 650;
		line-height: 1;
		padding: 0.32rem 0.52rem;
		box-shadow: inset 0 0 0 1px rgba(34, 197, 94, 0.16);
	}

	.suggestion-type-badge--motor {
		background: rgba(219, 236, 255, 0.94);
		color: #0b2a55;
		box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.16);
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

	.experience-confirm-backdrop {
		position: fixed;
		inset: 0;
		z-index: 9999;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1.5rem;
		background: transparent;
		backdrop-filter: blur(20px) saturate(1.12);
		-webkit-backdrop-filter: blur(20px) saturate(1.12);
	}

	.experience-confirm-dialog {
		display: flex;
		width: clamp(24rem, 42vw, 36rem);
		aspect-ratio: 5 / 3;
		max-width: calc(100vw - 2rem);
		max-height: min(80dvh, 30rem);
		flex-direction: column;
		align-items: center;
		justify-content: center;
		border: 1px solid rgba(159, 202, 255, 0.72);
		border-radius: 1.5rem;
		background: rgba(255, 255, 255, 0.62);
		backdrop-filter: blur(24px) saturate(1.18);
		-webkit-backdrop-filter: blur(24px) saturate(1.18);
		box-shadow:
			0 0 0 1px rgba(91, 169, 255, 0.2),
			0 0 42px rgba(56, 145, 255, 0.34),
			0 26px 70px rgba(7, 31, 77, 0.22),
			inset 0 1px 0 rgba(255, 255, 255, 0.94);
		padding: clamp(1.5rem, 2.6vw, 2.25rem);
		text-align: center;
	}

	.experience-confirm-emoji {
		display: grid;
		width: 3.25rem;
		height: 3.25rem;
		place-items: center;
		background: transparent;
		font-size: 2.35rem;
		line-height: 1;
		text-shadow:
			0 2px 8px rgba(255, 255, 255, 0.92),
			0 0 18px rgba(67, 150, 255, 0.34);
	}

	.experience-confirm-title {
		margin-top: 1rem;
		color: #071f4d;
		font-size: clamp(1.45rem, 2vw, 1.75rem);
		font-weight: 700;
		line-height: 1.35;
	}

	.experience-confirm-message {
		margin-top: 0.85rem;
		max-width: 28rem;
		color: #5f6f8f;
		font-size: 1rem;
		font-weight: 400;
		line-height: 1.55;
		white-space: pre-line;
	}

	.experience-confirm-actions {
		display: flex;
		width: 100%;
		gap: 1rem;
		margin-top: 1.75rem;
	}

	.experience-confirm-button {
		min-height: 3.15rem;
		flex: 1 1 0;
		border-radius: 999px;
		font-size: 1.05rem;
		font-weight: 650;
		line-height: 1;
		transition:
			background-color 160ms ease,
			box-shadow 160ms ease,
			transform 160ms ease;
	}

	.experience-confirm-button:hover {
		transform: translateY(-1px);
	}

	.experience-confirm-button--start {
		background: #071f4d;
		color: #fff;
		box-shadow: 0 10px 22px rgba(7, 31, 77, 0.22);
	}

	.experience-confirm-button--start:hover {
		background: #0b2a55;
	}

	.experience-confirm-button--cancel {
		background: rgba(238, 242, 247, 0.82);
		color: #52617e;
	}

	.experience-confirm-button--cancel:hover {
		background: rgba(228, 233, 240, 0.92);
	}

	:global(.dark) .experience-confirm-backdrop {
		background: transparent;
	}

	:global(.dark) .experience-confirm-dialog {
		border-color: rgba(96, 165, 250, 0.58);
		background: rgba(17, 24, 39, 0.62);
		box-shadow:
			0 0 0 1px rgba(96, 165, 250, 0.18),
			0 0 42px rgba(59, 130, 246, 0.28),
			0 26px 70px rgba(0, 0, 0, 0.4);
	}

	:global(.dark) .experience-confirm-emoji {
		text-shadow:
			0 2px 8px rgba(15, 23, 42, 0.72),
			0 0 18px rgba(96, 165, 250, 0.44);
	}

	:global(.dark) .experience-confirm-title {
		color: #f8fafc;
	}

	:global(.dark) .experience-confirm-message {
		color: #cbd5e1;
	}

	:global(.dark) .experience-confirm-button--cancel {
		background: rgba(55, 65, 81, 0.84);
		color: #e5e7eb;
	}

	:global(.dark) .experience-confirm-button--cancel:hover {
		background: rgba(75, 85, 99, 0.94);
	}

	@media (max-width: 767px) {
		.experience-confirm-dialog {
			width: min(92vw, 28rem);
		}
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

		.experience-confirm-button,
		.experience-confirm-button:hover {
			transform: none;
		}
	}
</style>
