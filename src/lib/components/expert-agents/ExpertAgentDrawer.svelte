<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	import {
		getExpertAgentDetail,
		getExpertAgents,
		type ExpertSkillCard,
		type ExpertSkillDetail
	} from '$lib/apis/expert-agents';
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import ExpertSkillCardComponent from './ExpertSkillCard.svelte';

	export let show = false;

	const dispatch = createEventDispatcher<{
		start: ExpertSkillCard;
		close: void;
	}>();

	let items: ExpertSkillCard[] = [];
	let loading = false;
	let loaded = false;
	let error: string | null = null;
	let showDetailModal = false;
	let selectedSkill: ExpertSkillCard | null = null;
	let selectedSkillDetail: ExpertSkillDetail | null = null;
	let detailLoading = false;
	let detailError: string | null = null;
	let detailMarkdownContent = '';

	const close = () => {
		show = false;
		showDetailModal = false;
		dispatch('close');
	};

	const loadExpertAgents = async () => {
		loading = true;
		error = null;

		try {
			items = await getExpertAgents(localStorage.token);
			loaded = true;
		} catch (err) {
			console.error(err);
			error = '无法加载专家技能';
		} finally {
			loading = false;
		}
	};

	const openSkillDetail = async (skill: ExpertSkillCard) => {
		selectedSkill = skill;
		selectedSkillDetail = null;
		detailMarkdownContent = '';
		detailError = null;
		detailLoading = true;
		showDetailModal = true;

		try {
			selectedSkillDetail = await getExpertAgentDetail(skill.skill_name, localStorage.token);
			detailMarkdownContent = formatSkillDetailContent(selectedSkillDetail, skill);
		} catch (err) {
			console.error(err);
			detailError = '无法加载专家技能详情';
		} finally {
			detailLoading = false;
		}
	};

	const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

	const formatSkillDetailContent = (detail: ExpertSkillDetail, fallback: ExpertSkillCard) => {
		let content = detail.content ?? '';
		const title = (detail.name || fallback.skill_name || '').trim();
		const description = (detail.description || fallback.description || '').trim();

		content = content.replace(/^---\s*[\r\n]+[\s\S]*?[\r\n]+---\s*[\r\n]*/m, '').trimStart();

		if (title) {
			const titlePattern = new RegExp(`^#\\s+${escapeRegExp(title)}\\s*(?:\\r?\\n)+`, 'i');
			content = content.replace(titlePattern, '').trimStart();
		}

		if (description) {
			const normalizedDescription = description.replace(/\s+/g, ' ').trim();
			const paragraphs = content.split(/\n{2,}/);
			const firstParagraph = paragraphs[0]?.replace(/\s+/g, ' ').trim();
			if (firstParagraph === normalizedDescription) {
				content = paragraphs.slice(1).join('\n\n').trimStart();
			}
		}

		return content;
	};

	$: if (show && !loaded && !loading) {
		void loadExpertAgents();
	}

	$: if (!show && showDetailModal) {
		showDetailModal = false;
	}
</script>

{#if show}
	<div
		class="flex h-full min-h-0 flex-col bg-white text-gray-900 dark:bg-gray-850 dark:text-gray-100"
	>
		<div
			class="flex shrink-0 items-start justify-between border-b border-gray-100 px-3 py-3 dark:border-gray-800"
		>
			<div class="min-w-0">
				<div class="text-md font-medium text-gray-900 dark:text-gray-100">Expert Agent</div>
				<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">选择一个专家技能开始会话</div>
			</div>

			<button
				type="button"
				class="rounded-lg p-1.5 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-gray-100"
				aria-label="关闭专家面板"
				on:click={close}
			>
				<XMark className="size-4" />
			</button>
		</div>

		<div class="flex-1 overflow-y-auto p-3">
			{#if loading}
				<div
					class="flex h-full flex-col items-center justify-center gap-3 text-sm text-gray-500 dark:text-gray-400"
				>
					<Spinner className="size-5" />
					<div>正在加载专家技能...</div>
				</div>
			{:else if error}
				<div class="flex h-full flex-col items-center justify-center text-center">
					<div class="text-base font-medium text-gray-900 dark:text-gray-100">无法加载专家技能</div>
					<button
						type="button"
						class="mt-4 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-800"
						on:click={() => {
							loaded = false;
							void loadExpertAgents();
						}}
					>
						重试
					</button>
				</div>
			{:else if items.length === 0}
				<div class="flex h-full flex-col items-center justify-center text-center">
					<div class="text-base font-medium text-gray-900 dark:text-gray-100">
						还没有可用的专家技能
					</div>
					<div class="mt-2 max-w-64 text-sm text-gray-500 dark:text-gray-400">
						创建 Hermes Skill 后，它会显示在这里。
					</div>
				</div>
			{:else}
				<div class="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3">
					{#each items as item (item.skill_name)}
						<ExpertSkillCardComponent
							skill={item}
							onStart={(skill) => {
								dispatch('start', skill);
							}}
							onDetails={(skill) => {
								void openSkillDetail(skill);
							}}
						/>
					{/each}
				</div>
			{/if}
		</div>
	</div>
{/if}

<Modal
	size="lg"
	bind:show={showDetailModal}
	containerClassName="p-4 backdrop-blur-sm"
	className="overflow-hidden bg-white dark:bg-gray-900 rounded-2xl"
>
	<div class="flex max-h-[82vh] min-h-[32rem] flex-col text-gray-900 dark:text-gray-100">
		<div
			class="expert-skill-detail-header flex shrink-0 items-start justify-between gap-4 border-b border-gray-100 px-5 py-4 dark:border-gray-800"
		>
			<div class="min-w-0">
				<div class="line-clamp-2 text-lg font-semibold leading-6">
					{selectedSkillDetail?.name || selectedSkill?.skill_name || '专家技能详情'}
				</div>
				{#if selectedSkillDetail?.description || selectedSkill?.description}
					<div class="mt-2 text-sm leading-5 text-gray-500 dark:text-gray-400">
						{selectedSkillDetail?.description || selectedSkill?.description}
					</div>
				{/if}
			</div>

			<button
				type="button"
				class="rounded-lg p-1.5 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-gray-100"
				aria-label="关闭专家技能详情"
				on:click={() => {
					showDetailModal = false;
				}}
			>
				<XMark className="size-5" />
			</button>
		</div>

		<div class="flex-1 overflow-y-auto px-5 py-4">
			{#if detailLoading}
				<div
					class="flex h-full min-h-72 flex-col items-center justify-center gap-3 text-sm text-gray-500"
				>
					<Spinner className="size-5" />
					<div>正在加载完整技能文档...</div>
				</div>
			{:else if detailError}
				<div class="flex h-full min-h-72 flex-col items-center justify-center text-center">
					<div class="text-base font-medium text-gray-900 dark:text-gray-100">{detailError}</div>
					<button
						type="button"
						class="mt-4 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-800"
						on:click={() => {
							if (selectedSkill) {
								void openSkillDetail(selectedSkill);
							}
						}}
					>
						重试
					</button>
				</div>
			{:else if detailMarkdownContent}
				<div class="expert-skill-markdown w-full max-w-none text-[13px]">
					<Markdown
						id={`expert-skill-detail-${selectedSkillDetail.name}`}
						content={detailMarkdownContent}
						editCodeBlock={false}
					/>
				</div>
			{:else}
				<div class="flex h-full min-h-72 items-center justify-center text-sm text-gray-500">
					暂无完整技能文档
				</div>
			{/if}
		</div>
	</div>
</Modal>

<style>
	.expert-skill-detail-header {
		background:
			radial-gradient(circle at 12% 12%, rgba(134, 144, 175, 0.16), transparent 44%),
			radial-gradient(circle at 92% 0%, rgba(170, 180, 205, 0.18), transparent 40%),
			linear-gradient(135deg, #fbfcff 0%, #f2f5fb 52%, #f8faff 100%);
	}

	:global(.dark) .expert-skill-detail-header {
		background:
			radial-gradient(circle at 12% 12%, rgba(134, 144, 175, 0.15), transparent 44%),
			radial-gradient(circle at 92% 0%, rgba(93, 104, 135, 0.18), transparent 40%),
			linear-gradient(135deg, #252d42 0%, #30384e 52%, #2f374d 100%);
	}

	.expert-skill-markdown :global(h1) {
		margin-top: 0;
		margin-bottom: 0.875rem;
		border-bottom: 1px solid var(--color-gray-100);
		padding-bottom: 0.5rem;
		color: var(--color-gray-900);
		font-size: 1.25rem;
		font-weight: 600;
		line-height: 1.75rem;
	}

	.expert-skill-markdown :global(h2) {
		margin-top: 1.5rem;
		margin-bottom: 0.625rem;
		border-bottom: 1px solid var(--color-gray-100);
		padding-bottom: 0.375rem;
		color: var(--color-gray-900);
		font-size: 1.05rem;
		font-weight: 600;
		line-height: 1.5rem;
	}

	.expert-skill-markdown :global(h3) {
		margin-top: 1.25rem;
		margin-bottom: 0.5rem;
		color: var(--color-gray-800);
		font-size: 0.95rem;
		font-weight: 600;
		line-height: 1.4rem;
	}

	.expert-skill-markdown :global(p) {
		margin-top: 0.625rem;
		margin-bottom: 0.625rem;
		color: var(--color-gray-700);
		line-height: 1.55rem;
	}

	.expert-skill-markdown :global(ul),
	.expert-skill-markdown :global(ol) {
		margin-top: 0.625rem;
		margin-bottom: 0.625rem;
		padding-left: 1.25rem;
		color: var(--color-gray-700);
	}

	.expert-skill-markdown :global(li) {
		margin-top: 0.25rem;
		margin-bottom: 0.25rem;
		line-height: 1.55rem;
	}

	.expert-skill-markdown :global(blockquote) {
		margin-top: 0.875rem;
		margin-bottom: 0.875rem;
		border-left: 3px solid var(--color-gray-400);
		border-radius: 0.5rem;
		background-color: rgba(134, 144, 175, 0.08);
		padding: 0.625rem 0.875rem;
		color: var(--color-gray-700);
	}

	.expert-skill-markdown :global(code:not(pre code)) {
		border: 1px solid rgba(134, 144, 175, 0.24);
		border-radius: 0.375rem;
		background-color: rgba(134, 144, 175, 0.1);
		padding: 0.125rem 0.375rem;
		color: var(--color-gray-800);
		font-size: 0.85em;
		font-weight: 500;
	}

	.expert-skill-markdown :global(pre),
	.expert-skill-markdown :global(.hljs) {
		width: 100%;
		max-width: 100%;
		border-color: rgba(134, 144, 175, 0.22) !important;
		background-color: #f7f8fb !important;
		color: var(--color-gray-700) !important;
	}

	.expert-skill-markdown :global(pre) {
		margin-top: 0.875rem;
		margin-bottom: 0.875rem;
		overflow: hidden;
		border-radius: 0.75rem;
		box-shadow: 0 1px 2px rgba(23, 29, 45, 0.06);
	}

	.expert-skill-markdown :global(.hljs) {
		overflow-x: auto;
		padding: 0.875rem 1rem;
		font-size: 0.8rem;
		line-height: 1.45rem;
	}

	.expert-skill-markdown :global(pre *),
	.expert-skill-markdown :global(.hljs *) {
		color: inherit !important;
		background: transparent !important;
		font-weight: inherit !important;
		text-decoration: none !important;
	}

	.expert-skill-markdown :global(.sticky) {
		background-color: #eef1f7 !important;
		color: var(--color-gray-600) !important;
	}

	:global(.dark) .expert-skill-markdown :global(pre),
	:global(.dark) .expert-skill-markdown :global(.hljs),
	:global(.dark) .expert-skill-markdown :global(.sticky) {
		background-color: var(--color-gray-850) !important;
		color: var(--color-gray-300) !important;
	}

	:global(.dark) .expert-skill-markdown :global(h1),
	:global(.dark) .expert-skill-markdown :global(h2) {
		border-color: var(--color-gray-800);
		color: var(--color-gray-100);
	}

	:global(.dark) .expert-skill-markdown :global(p),
	:global(.dark) .expert-skill-markdown :global(ul),
	:global(.dark) .expert-skill-markdown :global(ol),
	:global(.dark) .expert-skill-markdown :global(blockquote) {
		color: var(--color-gray-300);
	}

	:global(.dark) .expert-skill-markdown :global(blockquote),
	:global(.dark) .expert-skill-markdown :global(code:not(pre code)) {
		background-color: rgba(134, 144, 175, 0.12);
	}

	:global(.dark) .expert-skill-markdown :global(code:not(pre code)) {
		color: var(--color-gray-100);
	}
</style>
