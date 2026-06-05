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
	let showSelectionGuide = false;
	$: displayedPrompts = filteredPrompts.slice(0, MAX_DISPLAYED_PROMPTS);
	$: activeLanguage = $i18n.language;
	$: showSelectionGuideCard =
		displayedPrompts.length > 0 &&
		displayedPrompts.length < MAX_DISPLAYED_PROMPTS &&
		inputValue.trim() === '';

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

	const DEFAULT_EFFICIENCY_TIMES = {
		human: '15-30分钟',
		ai: '1-3分钟'
	};

	const PROMPT_EFFICIENCY_TIMES = {
		[PROMPT_CARD_IDS.trayTransfer]: {
			human: '12-25分钟',
			ai: '0.8-1.5分钟'
		},
		[PROMPT_CARD_IDS.rotaryFixture]: {
			human: '14-30分钟',
			ai: '1.5-2.8分钟'
		},
		[PROMPT_CARD_IDS.palletLifter]: {
			human: '10-22分钟',
			ai: '0.6-1.2分钟'
		},
		[PROMPT_CARD_IDS.kkModuleHighSpeed]: {
			human: '25-45分钟',
			ai: '1.8-3分钟'
		},
		[PROMPT_CARD_IDS.flipMotorSelection]: {
			human: '28-50分钟',
			ai: '2-3分钟'
		}
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

	const getEfficiencyComparisonCopy = (prompt) => {
		const times = PROMPT_EFFICIENCY_TIMES[getPromptCase(prompt)] ?? DEFAULT_EFFICIENCY_TIMES;
		const isChinese = isChineseLanguage(activeLanguage);
		const formatTime = (time) => (isChinese ? time : time.replaceAll('分钟', ' min'));

		return {
			humanLabel: isChinese ? '工程师' : 'Engineer',
			humanTime: formatTime(times.human),
			aiLabel: 'AI',
			aiTime: formatTime(times.ai),
			ariaLabel: isChinese
				? `工程师 ${times.human}，AI ${times.ai}`
				: `Engineer time ${formatTime(times.human)}, AI ${formatTime(times.ai)}`
		};
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

	const getSuggestionsSectionTitle = () =>
		isChineseLanguage(activeLanguage) ? '快速体验 AI 选型' : 'Quick AI Selection';

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

	const getSelectionGuideCopy = () => {
		if (isChineseLanguage(activeLanguage)) {
			return {
				cardTitle: '需要帮助',
				cardAriaLabel: '需要帮助，AI 选型体验指南',
				title: '需要帮助',
				close: '关闭',
				guideTitle: '如何体验 AI 选型',
				steps: [
					{
						title: '点击一个选型卡片',
						description: '从卡片中选择一个典型设计场景，快速开始体验'
					},
					{
						title: '观察 AI 选型过程并查看结果',
						description: 'Agent 对设计需求进行分析与计算，并从标准件库中给出推荐型号及理由'
					},
					{
						title: '继续追问或调整需求',
						description: '您可进一步追问、对比方案或调整需求，获得更精准结果。'
					}
				],
				expertTitle: '标准件选型专家',
				features: ['自然语言需求', '机构理解与工程计算', '从企业标准库选型', '展示推荐型号及理由']
			};
		}

		return {
			cardTitle: 'Need Help',
			cardAriaLabel: 'Need help, AI selection guide',
			title: 'Need Help',
			close: 'Close',
			guideTitle: 'How to try AI selection',
			steps: [
				{
					title: 'Click a selection card',
					description: 'Choose a typical design scenario from the cards to start quickly'
				},
				{
					title: 'Watch AI select and review results',
					description:
						'Agent analyzes and calculates the design requirements, then recommends models from the standard-parts library with reasons'
				},
				{
					title: 'Ask follow-ups or adjust requirements',
					description:
						'Continue asking questions, compare options, or tune requirements for more precise results.'
				}
			],
			expertTitle: 'Standard Parts Selection Expert',
			features: [
				'Natural-language requirements',
				'Mechanism understanding and engineering calculation',
				'Selection from the enterprise standard library',
				'Recommended models and reasons'
			]
		};
	};

	const openPromptConfirmation = (prompt) => {
		pendingPrompt = prompt;
	};

	const closePromptConfirmation = () => {
		pendingPrompt = null;
	};

	const openSelectionGuide = () => {
		showSelectionGuide = true;
	};

	const closeSelectionGuide = () => {
		showSelectionGuide = false;
	};

	const confirmPromptSelection = () => {
		const prompt = pendingPrompt;
		closePromptConfirmation();

		if (prompt) {
			onSelect({ type: 'prompt', data: prompt.content, prompt });
		}
	};

	const handleConfirmationKeydown = (event) => {
		if (!pendingPrompt && !showSelectionGuide) {
			return;
		}

		if (event.key === 'Escape') {
			event.preventDefault();
			closePromptConfirmation();
			closeSelectionGuide();
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
	$: selectionGuideCopy = getSelectionGuideCopy();
</script>

<svelte:window on:keydown={handleConfirmationKeydown} />

{#if displayedPrompts.length > 0}
	<div
		class="mb-4 flex items-center gap-1.5 text-[13px] font-medium text-[#5f6f8f] dark:text-gray-400"
	>
		<Bolt />
		{getSuggestionsSectionTitle()}
	</div>
{/if}

<div class="w-full">
	{#if displayedPrompts.length > 0}
		<div
			role="list"
			class="grid w-full max-w-none grid-cols-1 items-stretch gap-4 @2xl:grid-cols-2 @4xl:grid-cols-3 {className}"
		>
			{#each displayedPrompts as prompt, idx (prompt.id || `${prompt.content}-${idx}`)}
				{@const efficiencyComparison = getEfficiencyComparisonCopy(prompt)}
				<div
					role="listitem"
					class="suggestion-card-stack waterfall w-full"
					style="animation-delay: {idx * 60}ms"
				>
					<button
						type="button"
						class="suggestion-card group flex min-h-[158px] w-full flex-col overflow-hidden rounded-lg text-left transition duration-200"
						on:click={() => openPromptConfirmation(prompt)}
					>
						{#if getPromptTypeLabel(prompt)}
							<div
								class="suggestion-type-badge"
								class:suggestion-type-badge--motor={getPromptType(prompt) ===
									PROMPT_CARD_TYPES.motor}
							>
								{getPromptTypeLabel(prompt)}
							</div>
						{/if}

						<div class="suggestion-card__body">
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
										class="mt-2 text-[13px] leading-5 text-[#6b7280] dark:text-gray-500 font-normal line-clamp-3"
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
										class="mt-2 text-[13px] leading-5 text-[#6b7280] dark:text-gray-500 font-normal line-clamp-3"
									>
										{$i18n.t('Prompt')}
									</div>
								{/if}
							</div>

							<div class="suggestion-sketch" aria-hidden="true">
								<img src={getPromptSketchImage(prompt)} alt="" loading="lazy" draggable="false" />
							</div>
						</div>

						<div class="efficiency-tab" aria-label={efficiencyComparison.ariaLabel}>
							<span class="efficiency-tab__metric efficiency-tab__metric--human">
								<span>{efficiencyComparison.humanLabel}</span>
								<strong>{efficiencyComparison.humanTime}</strong>
							</span>
							<span class="efficiency-tab__divider" aria-hidden="true">/</span>
							<span class="efficiency-tab__metric efficiency-tab__metric--ai">
								<span>{efficiencyComparison.aiLabel}</span>
								<strong>{efficiencyComparison.aiTime}</strong>
							</span>
						</div>
					</button>
				</div>
			{/each}

			{#if showSelectionGuideCard}
				<div
					role="listitem"
					class="suggestion-card-stack waterfall w-full"
					style="animation-delay: {displayedPrompts.length * 60}ms"
				>
					<button
						type="button"
						class="selection-guide-card group flex min-h-[158px] w-full flex-col items-center justify-center rounded-lg text-center transition duration-200"
						aria-label={selectionGuideCopy.cardAriaLabel}
						on:click={openSelectionGuide}
					>
						<span class="selection-guide-card__icon" aria-hidden="true">
							<LucideIcon
								name="circle-help"
								className="size-12 text-[#3478d9]"
								strokeWidth="1.45"
							/>
							<span class="selection-guide-card__sparkle selection-guide-card__sparkle--large">
								<LucideIcon name="sparkles" className="size-4 text-[#3478d9]" strokeWidth="1.8" />
							</span>
						</span>
						<span class="selection-guide-card__title">{selectionGuideCopy.cardTitle}</span>
					</button>
				</div>
			{/if}
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

{#if showSelectionGuide}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div class="selection-help-backdrop" role="presentation" on:pointerdown={closeSelectionGuide}>
		<div
			class="selection-help-dialog"
			role="dialog"
			aria-modal="true"
			aria-labelledby="selection-help-title"
			aria-describedby="selection-help-guide"
			tabindex="-1"
			on:pointerdown|stopPropagation
		>
			<div class="selection-help-header">
				<div class="selection-help-title-wrap">
					<span class="selection-help-title-icon" aria-hidden="true">
						<LucideIcon name="messages-square" className="size-4" strokeWidth="2" />
					</span>
					<div>
						<div id="selection-help-title" class="selection-help-title">
							<span class="selection-help-title__main">{selectionGuideCopy.title}</span>
							<span class="selection-help-title__separator">|</span>
							<span class="selection-help-title__sub">{selectionGuideCopy.guideTitle}</span>
						</div>
					</div>
				</div>
				<button
					type="button"
					class="selection-help-close"
					aria-label={selectionGuideCopy.close}
					on:click={closeSelectionGuide}
				>
					<LucideIcon name="x" className="size-4" strokeWidth="2" />
				</button>
			</div>

			<div id="selection-help-guide" class="selection-help-guide">
				<div class="selection-help-steps">
					<div class="selection-help-step">
						<span class="selection-help-step__number">1</span>
						<LucideIcon
							name="pointer"
							className="selection-help-step__icon size-7"
							strokeWidth="1.9"
						/>
						<div>
							<div class="selection-help-step__title">{selectionGuideCopy.steps[0].title}</div>
							<p>{selectionGuideCopy.steps[0].description}</p>
						</div>
					</div>
					<div class="selection-help-step">
						<span class="selection-help-step__number">2</span>
						<LucideIcon
							name="search-check"
							className="selection-help-step__icon size-7"
							strokeWidth="1.9"
						/>
						<div>
							<div class="selection-help-step__title">{selectionGuideCopy.steps[1].title}</div>
							<p>{selectionGuideCopy.steps[1].description}</p>
						</div>
					</div>
					<div class="selection-help-step">
						<span class="selection-help-step__number">3</span>
						<LucideIcon
							name="message-circle-question"
							className="selection-help-step__icon size-7"
							strokeWidth="1.9"
						/>
						<div>
							<div class="selection-help-step__title">{selectionGuideCopy.steps[2].title}</div>
							<p>{selectionGuideCopy.steps[2].description}</p>
						</div>
					</div>
				</div>
			</div>

			<div class="selection-help-expert">
				<img
					class="selection-help-visual"
					src="/assets/images/expert-agent/selection-help-standard-parts-transparent.png"
					alt=""
					aria-hidden="true"
				/>
				<div class="selection-help-capability">
					<div class="selection-help-section-title">{selectionGuideCopy.expertTitle}</div>
					<div class="selection-help-feature-list">
						{#each selectionGuideCopy.features as feature, idx}
							<div><span>{idx + 1}.</span> {feature}</div>
						{/each}
					</div>
				</div>
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

	@keyframes selectionGuideGlassGlow {
		0%,
		100% {
			opacity: 0.86;
			transform: translate3d(-0.5%, 0.35%, 0) scale(1);
		}
		50% {
			opacity: 1;
			transform: translate3d(0.7%, -0.55%, 0) scale(1.012);
		}
	}

	@keyframes selectionGuideGlassShine {
		0% {
			opacity: 0.12;
			transform: translate3d(-30%, -16%, 0) rotate(8deg) scale(0.96);
		}
		32% {
			opacity: 0.54;
			transform: translate3d(-8%, -5%, 0) rotate(8deg) scale(1.04);
		}
		66% {
			opacity: 0.36;
			transform: translate3d(18%, 8%, 0) rotate(8deg) scale(1.08);
		}
		100% {
			opacity: 0.12;
			transform: translate3d(34%, 16%, 0) rotate(8deg) scale(0.98);
		}
	}

	@keyframes selectionGuideSparklePulse {
		0%,
		100% {
			opacity: 0.78;
			transform: scale(0.98) rotate(-3deg);
		}
		46% {
			opacity: 0.94;
			transform: scale(1.04) rotate(4deg);
		}
	}

	.waterfall {
		opacity: 0;
		animation-name: fadeInUp;
		animation-duration: 200ms;
		animation-fill-mode: forwards;
		animation-timing-function: ease;
	}

	.suggestion-card-stack {
		display: flex;
		position: relative;
		flex-direction: column;
		align-items: stretch;
		overflow: visible;
	}

	.suggestion-card:focus-visible {
		outline: 2px solid rgba(47, 111, 196, 0.68);
		outline-offset: 4px;
		border-radius: 0.75rem;
	}

	.suggestion-card {
		position: relative;
		z-index: 1;
		isolation: isolate;
		border: 1px solid rgba(112, 183, 255, 0.72);
		background:
			linear-gradient(
				135deg,
				rgba(255, 255, 255, 0.98) 0%,
				rgba(250, 253, 255, 0.94) 52%,
				rgba(238, 249, 255, 0.94) 100%
			),
			radial-gradient(circle at 86% 22%, rgba(127, 203, 255, 0.16), transparent 32%);
		box-shadow:
			0 12px 26px rgba(24, 86, 154, 0.08),
			0 3px 8px rgba(24, 86, 154, 0.04),
			inset 0 1px 0 rgba(255, 255, 255, 0.94);
		backdrop-filter: blur(12px);
		min-height: 158px;
		cursor: pointer;
	}

	.suggestion-card__body {
		display: flex;
		position: relative;
		min-height: 133px;
		flex: 1 1 auto;
		align-items: flex-start;
		gap: 1rem;
		padding: 1.25rem 1.25rem 1.18rem;
	}

	.suggestion-content {
		position: relative;
		z-index: 1;
		padding-right: min(32%, 7.2rem);
	}

	.suggestion-type-badge {
		position: absolute;
		top: 1.2rem;
		right: 1.25rem;
		z-index: 2;
		border-radius: 0.4rem;
		background: rgba(218, 246, 225, 0.92);
		color: #166534;
		font-size: 0.875rem;
		font-weight: 650;
		line-height: 1rem;
		padding: 0.1rem 0.54rem;
		box-shadow:
			inset 0 0 0 1px rgba(34, 197, 94, 0.2),
			0 1px 2px rgba(7, 31, 77, 0.04);
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
		border-top: 1px solid rgba(159, 221, 255, 0.82);
		box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.5);
		opacity: 1;
		pointer-events: none;
	}

	.suggestion-card::after {
		content: '';
		position: absolute;
		inset: auto 0 1.58rem;
		height: 38%;
		background: linear-gradient(180deg, rgba(255, 255, 255, 0) 0%, rgba(233, 246, 255, 0.38) 100%);
		pointer-events: none;
	}

	.suggestion-card-stack:hover .suggestion-card {
		border-color: rgba(70, 156, 245, 0.8);
		background:
			linear-gradient(
				135deg,
				rgba(255, 255, 255, 1) 0%,
				rgba(250, 253, 255, 0.98) 52%,
				rgba(234, 247, 255, 0.98) 100%
			),
			radial-gradient(circle at 86% 22%, rgba(102, 194, 255, 0.2), transparent 32%);
		box-shadow:
			0 14px 30px rgba(24, 86, 154, 0.11),
			0 4px 10px rgba(24, 86, 154, 0.05),
			inset 0 1px 0 rgba(255, 255, 255, 0.96);
		transform: translateY(-1px);
	}

	.suggestion-sketch {
		position: absolute;
		right: 1rem;
		bottom: 0.72rem;
		width: min(33%, 8.1rem);
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

	.suggestion-card-stack:hover .suggestion-sketch {
		transform: translate(-1px, -1px);
	}

	.efficiency-tab {
		display: flex;
		position: relative;
		z-index: 1;
		align-items: center;
		justify-content: center;
		width: 100%;
		min-height: 1.58rem;
		border-top: 1px solid rgba(159, 211, 250, 0.6);
		border-radius: 0;
		background: linear-gradient(
			90deg,
			rgba(241, 247, 252, 0.98) 0%,
			rgba(232, 244, 252, 0.98) 46%,
			rgba(218, 241, 252, 0.98) 100%
		);
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75);
		color: #53647f;
		font-size: 10px;
		font-weight: 400;
		line-height: 1;
		letter-spacing: 0;
		overflow: hidden;
		padding: 0.34rem 0.72rem 0.24rem;
		white-space: nowrap;
	}

	.efficiency-tab__metric {
		display: inline-flex;
		min-width: 0;
		flex: 1 1 0;
		align-items: center;
		justify-content: center;
		gap: 0.28rem;
	}

	.efficiency-tab__metric span {
		font-weight: 400;
	}

	.efficiency-tab__metric strong {
		color: #37465f;
		font-weight: 800;
	}

	.efficiency-tab__metric--ai {
		color: #075985;
	}

	.efficiency-tab__metric--ai strong {
		color: #0369a1;
	}

	.efficiency-tab__divider {
		display: inline-flex;
		width: auto;
		height: auto;
		margin: 0 0.42rem;
		align-items: center;
		color: rgba(45, 85, 126, 0.62);
		font-weight: 650;
		background: transparent;
	}

	.selection-guide-card {
		position: relative;
		isolation: isolate;
		border: 1px solid rgba(81, 155, 237, 0.7);
		background:
			radial-gradient(circle at 18% 16%, rgba(255, 255, 255, 0.94), transparent 28%),
			radial-gradient(circle at 78% 76%, rgba(91, 174, 255, 0.28), transparent 38%),
			linear-gradient(
				135deg,
				rgba(255, 255, 255, 0.5) 0%,
				rgba(242, 250, 255, 0.34) 44%,
				rgba(190, 225, 255, 0.26) 100%
			),
			rgba(255, 255, 255, 0.18);
		background-clip: padding-box;
		backdrop-filter: blur(38px) saturate(1.55) brightness(1.06);
		-webkit-backdrop-filter: blur(38px) saturate(1.55) brightness(1.06);
		box-shadow:
			0 18px 42px rgba(24, 86, 154, 0.11),
			0 6px 18px rgba(71, 154, 236, 0.08),
			0 0 0 1px rgba(255, 255, 255, 0.44),
			inset 0 1px 0 rgba(255, 255, 255, 0.98),
			inset 0 -1px 0 rgba(70, 152, 237, 0.26),
			inset 8px 8px 18px rgba(255, 255, 255, 0.34),
			inset -10px -10px 22px rgba(91, 164, 242, 0.14);
		color: #3478d9;
		cursor: pointer;
		overflow: hidden;
	}

	.selection-guide-card::before {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: inherit;
		background:
			linear-gradient(
				118deg,
				rgba(255, 255, 255, 0.86) 0%,
				rgba(255, 255, 255, 0.32) 19%,
				transparent 45%
			),
			repeating-linear-gradient(
				135deg,
				rgba(255, 255, 255, 0.18) 0,
				rgba(255, 255, 255, 0.18) 1px,
				rgba(255, 255, 255, 0) 1px,
				rgba(255, 255, 255, 0) 7px
			),
			radial-gradient(circle at 52% 30%, rgba(91, 158, 255, 0.18), transparent 40%),
			linear-gradient(135deg, rgba(255, 255, 255, 0.48), rgba(219, 239, 255, 0.14));
		opacity: 0.98;
		pointer-events: none;
		transition:
			transform 220ms ease,
			opacity 220ms ease;
		animation: selectionGuideGlassGlow 4s ease-in-out infinite;
	}

	.selection-guide-card::after {
		content: '';
		position: absolute;
		inset: -44% -24%;
		border-radius: 999px;
		background:
			radial-gradient(
				ellipse at center,
				rgba(255, 255, 255, 0.78) 0%,
				rgba(204, 233, 255, 0.4) 32%,
				rgba(94, 173, 255, 0.18) 48%,
				transparent 70%
			),
			linear-gradient(112deg, transparent 28%, rgba(255, 255, 255, 0.32) 48%, transparent 66%);
		opacity: 0.38;
		pointer-events: none;
		transform: translate3d(-30%, -16%, 0) rotate(8deg) scale(0.96);
		filter: blur(12px);
		transition:
			transform 260ms ease,
			opacity 260ms ease;
		animation: selectionGuideGlassShine 3.6s cubic-bezier(0.42, 0, 0.28, 1) infinite;
		will-change: transform, opacity;
	}

	.selection-guide-card:hover {
		border-color: rgba(52, 120, 217, 0.56);
		background:
			linear-gradient(
				135deg,
				rgba(255, 255, 255, 0.66) 0%,
				rgba(244, 250, 255, 0.36) 48%,
				rgba(211, 235, 255, 0.24) 100%
			),
			rgba(255, 255, 255, 0.28);
		box-shadow:
			0 18px 38px rgba(24, 86, 154, 0.11),
			inset 0 1px 0 rgba(255, 255, 255, 0.96),
			inset 0 -1px 0 rgba(93, 164, 236, 0.22),
			inset 0 0 0 1px rgba(255, 255, 255, 0.6);
		transform: translateY(-1px);
	}

	.selection-guide-card:hover::before {
		transform: translate(1.5%, -1.5%);
		opacity: 1;
	}

	.selection-guide-card:hover::after {
		opacity: 0.38;
	}

	.selection-guide-card:focus-visible {
		outline: 2px solid rgba(47, 111, 196, 0.68);
		outline-offset: 4px;
	}

	.selection-guide-card__icon {
		display: grid;
		position: relative;
		z-index: 1;
		width: 4rem;
		height: 4rem;
		place-items: center;
	}

	.selection-guide-card__sparkle {
		position: absolute;
		top: -0.02rem;
		right: -0.42rem;
		animation: selectionGuideSparklePulse 2.8s ease-in-out infinite;
		transform-origin: center;
	}

	.selection-guide-card__title {
		position: relative;
		z-index: 1;
		margin-top: 0.55rem;
		color: #3478d9;
		font-size: 1.28rem;
		font-weight: 800;
		line-height: 1.2;
		letter-spacing: 0;
	}

	.selection-help-backdrop {
		position: fixed;
		inset: 0;
		z-index: 9999;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1.25rem;
		background: rgba(222, 237, 250, 0.2);
		backdrop-filter: blur(18px) saturate(1.08);
		-webkit-backdrop-filter: blur(18px) saturate(1.08);
	}

	.selection-help-dialog {
		width: min(59.4rem, calc(100vw - 2rem));
		max-height: min(88dvh, 46rem);
		overflow-y: auto;
		border: 1.5px solid rgba(49, 111, 199, 0.78);
		border-radius: 0.9rem;
		background:
			linear-gradient(
				135deg,
				rgba(255, 255, 255, 0.98) 0%,
				rgba(248, 252, 255, 0.96) 52%,
				rgba(234, 247, 255, 0.94) 100%
			),
			rgba(255, 255, 255, 0.94);
		backdrop-filter: blur(22px) saturate(1.12);
		-webkit-backdrop-filter: blur(22px) saturate(1.12);
		box-shadow:
			0 0 0 1px rgba(255, 255, 255, 0.88) inset,
			0 22px 58px rgba(7, 31, 77, 0.18);
		color: #071f4d;
	}

	.selection-help-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 1.25rem 1.5rem 1.1rem;
	}

	.selection-help-title-wrap {
		display: flex;
		align-items: center;
		gap: 0.9rem;
	}

	.selection-help-title-icon {
		display: grid;
		width: 1.9rem;
		height: 1.9rem;
		place-items: center;
		border-radius: 999px;
		background: #173b78;
		color: #fff;
		font-size: 1rem;
		font-weight: 760;
		line-height: 1;
		box-shadow:
			0 4px 10px rgba(23, 59, 120, 0.14),
			inset 0 1px 0 rgba(255, 255, 255, 0.28);
	}

	.selection-help-title {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.45rem;
		line-height: 1.2;
	}

	.selection-help-title__main {
		color: #102f69;
		font-size: 1.28rem;
		font-weight: 800;
	}

	.selection-help-title__separator,
	.selection-help-title__sub {
		color: #7a8495;
		font-size: 1rem;
		font-weight: 400;
	}

	.selection-help-subtitle {
		margin-top: 0.22rem;
		color: #62718a;
		font-size: 0.86rem;
		font-weight: 520;
		line-height: 1.2;
	}

	.selection-help-close {
		display: grid;
		width: 2rem;
		height: 2rem;
		place-items: center;
		border-radius: 999px;
		color: #173b78;
		transition:
			background-color 160ms ease,
			color 160ms ease;
	}

	.selection-help-close:hover {
		background: rgba(219, 234, 254, 0.8);
		color: #071f4d;
	}

	.selection-help-guide {
		margin: 0.45rem 1.5rem 1.85rem;
		padding-left: 0.8rem;
	}

	.selection-help-section-title {
		color: #143b78;
		font-size: 1.14rem;
		font-weight: 820;
		line-height: 1.25;
	}

	.selection-help-steps {
		display: grid;
		gap: 1.25rem;
		margin-top: 0;
	}

	.selection-help-step {
		display: grid;
		position: relative;
		grid-template-columns: 2rem 2.3rem minmax(0, 1fr);
		gap: 1.05rem;
		align-items: start;
	}

	.selection-help-step:not(:last-child)::after {
		content: '';
		position: absolute;
		left: 1rem;
		top: 2.05rem;
		bottom: -1.2rem;
		width: 1px;
		background: linear-gradient(180deg, rgba(126, 191, 248, 0.62), rgba(126, 191, 248, 0.16));
	}

	.selection-help-step__number {
		display: grid;
		position: relative;
		z-index: 1;
		width: 2rem;
		height: 2rem;
		place-items: center;
		border: 1px solid rgba(124, 193, 250, 0.72);
		border-radius: 0.44rem;
		background: linear-gradient(180deg, #e9f6ff, #ccecff);
		color: #2a6fca;
		font-size: 0.9rem;
		font-weight: 800;
	}

	.selection-help-step__icon {
		margin-top: 0.12rem;
		color: #173b78;
	}

	.selection-help-step p {
		margin: 0.28rem 0 0;
		color: #68768c;
		font-size: 0.94rem;
		font-weight: 400;
		line-height: 1.35;
	}

	.selection-help-step__title {
		color: #173b78;
		font-size: 1.04rem;
		font-weight: 820;
		line-height: 1.25;
	}

	.selection-help-expert {
		display: grid;
		grid-template-columns: minmax(0, 1.06fr) minmax(18rem, 0.94fr);
		gap: 1.4rem;
		align-items: center;
		border-top: 1px solid rgba(152, 205, 249, 0.42);
		background:
			linear-gradient(
				90deg,
				rgba(230, 246, 255, 0.78) 0%,
				rgba(247, 252, 255, 0.92) 56%,
				rgba(255, 255, 255, 0.94) 100%
			),
			radial-gradient(circle at 22% 58%, rgba(88, 177, 255, 0.14), transparent 36%);
		padding: 1.3rem 1.5rem 1.6rem;
	}

	.selection-help-visual {
		display: block;
		width: 100%;
		height: 12rem;
		object-fit: contain;
		object-position: center;
		border-radius: 0.7rem;
	}

	.selection-help-capability {
		min-width: 0;
		width: min(23rem, 100%);
		justify-self: end;
		padding-right: 1.15rem;
		text-align: right;
	}

	.selection-help-feature-list {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.8rem 1.3rem;
		justify-items: end;
		margin-top: 1.05rem;
		color: #7a8495;
		font-size: 0.9rem;
		font-weight: 400;
		line-height: 1.3;
	}

	.selection-help-feature-list div {
		min-width: 0;
		text-align: right;
	}

	.selection-help-feature-list span {
		margin-right: 0.28rem;
		color: #98a1b0;
		font-weight: 500;
	}

	.experience-confirm-backdrop {
		position: fixed;
		inset: 0;
		z-index: 9999;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1.5rem;
		background: rgba(222, 237, 250, 0.2);
		backdrop-filter: blur(18px) saturate(1.08);
		-webkit-backdrop-filter: blur(18px) saturate(1.08);
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
		border: 1.5px solid rgba(49, 111, 199, 0.78);
		border-radius: 0.9rem;
		background:
			linear-gradient(
				135deg,
				rgba(238, 249, 255, 0.72) 0%,
				rgba(250, 253, 255, 0.86) 28%,
				rgba(255, 255, 255, 0.96) 58%
			),
			rgba(255, 255, 255, 0.94);
		backdrop-filter: blur(22px) saturate(1.12);
		-webkit-backdrop-filter: blur(22px) saturate(1.12);
		box-shadow:
			0 0 0 1px rgba(255, 255, 255, 0.88) inset,
			0 22px 58px rgba(7, 31, 77, 0.18);
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
		background: rgba(15, 23, 42, 0.2);
	}

	:global(.dark) .experience-confirm-dialog {
		border-color: rgba(96, 165, 250, 0.5);
		background:
			linear-gradient(
				135deg,
				rgba(30, 64, 112, 0.38) 0%,
				rgba(20, 36, 62, 0.72) 30%,
				rgba(17, 24, 39, 0.9) 60%
			),
			rgba(17, 24, 39, 0.84);
		box-shadow:
			0 0 0 1px rgba(96, 165, 250, 0.16),
			0 26px 70px rgba(0, 0, 0, 0.42);
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

	:global(.dark) .efficiency-tab {
		border-color: rgba(96, 165, 250, 0.34);
		background: linear-gradient(
			90deg,
			rgba(30, 41, 59, 0.96) 0%,
			rgba(24, 55, 80, 0.94) 52%,
			rgba(12, 74, 110, 0.92) 100%
		);
		color: #cbd5e1;
	}

	:global(.dark) .efficiency-tab__metric strong {
		color: #e2e8f0;
	}

	:global(.dark) .efficiency-tab__metric--ai,
	:global(.dark) .efficiency-tab__metric--ai strong {
		color: #bae6fd;
	}

	:global(.dark) .selection-guide-card {
		border-color: rgba(96, 165, 250, 0.34);
		background:
			linear-gradient(135deg, rgba(30, 64, 112, 0.38), rgba(15, 23, 42, 0.2)),
			rgba(15, 23, 42, 0.26);
		color: #93c5fd;
	}

	:global(.dark) .selection-guide-card__title {
		color: #bfdbfe;
	}

	:global(.dark) .selection-help-backdrop {
		background: rgba(15, 23, 42, 0.2);
	}

	:global(.dark) .selection-help-dialog {
		border-color: rgba(96, 165, 250, 0.5);
		background: rgba(17, 24, 39, 0.84);
		color: #f8fafc;
		box-shadow:
			0 0 0 1px rgba(96, 165, 250, 0.16),
			0 26px 70px rgba(0, 0, 0, 0.42);
	}

	:global(.dark) .selection-help-header,
	:global(.dark) .selection-help-expert {
		border-color: rgba(96, 165, 250, 0.26);
	}

	:global(.dark) .selection-help-title__main,
	:global(.dark) .selection-help-step__title {
		color: #bfdbfe;
	}

	:global(.dark) .selection-help-title__separator,
	:global(.dark) .selection-help-title__sub {
		color: #94a3b8;
	}

	:global(.dark) .selection-help-step__icon {
		color: #bfdbfe;
	}

	:global(.dark) .selection-help-step__number {
		border-color: rgba(96, 165, 250, 0.42);
		background: linear-gradient(180deg, rgba(30, 64, 112, 0.9), rgba(12, 74, 110, 0.82));
		color: #dbeafe;
	}

	:global(.dark) .selection-help-subtitle,
	:global(.dark) .selection-help-step p,
	:global(.dark) .selection-help-feature-list {
		color: #94a3b8;
	}

	:global(.dark) .selection-help-feature-list span {
		color: #8492a7;
	}

	:global(.dark) .selection-help-section-title {
		color: #bfdbfe;
	}

	:global(.dark) .selection-help-title-icon {
		background: #1d4ed8;
		box-shadow:
			0 6px 14px rgba(29, 78, 216, 0.18),
			inset 0 1px 0 rgba(255, 255, 255, 0.18);
	}

	:global(.dark) .selection-help-expert {
		background: linear-gradient(90deg, rgba(15, 23, 42, 0.48), rgba(30, 41, 59, 0.32));
	}

	:global(.dark) .selection-help-visual {
		opacity: 0.86;
	}

	@media (max-width: 767px) {
		.selection-guide-card {
			min-height: 10.5rem;
		}

		.selection-help-backdrop {
			align-items: flex-start;
			padding: 1rem;
		}

		.selection-help-dialog {
			max-height: calc(100dvh - 2rem);
		}

		.selection-help-header,
		.selection-help-expert {
			padding-right: 1rem;
			padding-left: 1rem;
		}

		.selection-help-guide {
			margin-top: 0.4rem;
			margin-right: 1rem;
			margin-bottom: 1.6rem;
			margin-left: 1rem;
			padding-left: 0.35rem;
		}

		.selection-help-steps,
		.selection-help-expert,
		.selection-help-feature-list {
			grid-template-columns: 1fr;
		}

		.selection-help-visual {
			height: 10.5rem;
		}

		.efficiency-tab {
			width: 100%;
			font-size: 10px;
			padding-right: 0.42rem;
			padding-left: 0.42rem;
		}

		.efficiency-tab__metric {
			gap: 0.2rem;
		}

		.efficiency-tab__divider {
			margin: 0 0.28rem;
		}

		.experience-confirm-dialog {
			width: min(92vw, 28rem);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.waterfall {
			animation: none;
			opacity: 1;
		}

		.suggestion-card-stack:hover .suggestion-card {
			transform: none;
		}

		.suggestion-card-stack:hover .suggestion-sketch {
			transform: none;
		}

		.selection-guide-card::before,
		.selection-guide-card::after,
		.selection-guide-card__sparkle {
			animation: none;
		}

		.experience-confirm-button,
		.experience-confirm-button:hover {
			transform: none;
		}
	}
</style>
