<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { parseDocument } from 'yaml';

	import {
		getExpertAgentDetail,
		getExpertAgents,
		updateExpertAgentDetail,
		type ExpertSkillCard,
		type ExpertSkillDetail
	} from '$lib/apis/expert-agents';
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import { toast } from 'svelte-sonner';
	import ExpertSkillCardComponent from './ExpertSkillCard.svelte';
	import LucideIcon from './LucideIcon.svelte';

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
	let detailSourceContent = '';
	let detailMode: 'preview' | 'source' = 'preview';
	let savingDetail = false;
	let selectedIcon = 'sparkles';
	let selectedIconBackground = '#e6edf7';
	let showIconPicker = false;
	let customIconName = '';
	let iconPickerButton: HTMLButtonElement | null = null;
	let iconPickerPanel: HTMLDivElement | null = null;

	const iconOptions = [
		{ name: 'bot', label: 'AI 专家' },
		{ name: 'brain-circuit', label: '知识推理' },
		{ name: 'messages-square', label: '访谈沟通' },
		{ name: 'book-open', label: '知识库' },
		{ name: 'search', label: '搜索研究' },
		{ name: 'scan-search', label: '检查识别' },
		{ name: 'clipboard-list', label: '需求清单' },
		{ name: 'file-text', label: '文档报告' },
		{ name: 'table', label: '表格数据' },
		{ name: 'chart-no-axes-combined', label: '分析图表' },
		{ name: 'presentation', label: '演示文稿' },
		{ name: 'workflow', label: '流程编排' },
		{ name: 'database', label: '数据资产' },
		{ name: 'package', label: '制品交付' },
		{ name: 'boxes', label: '组件模块' },
		{ name: 'blocks', label: '系统结构' },
		{ name: 'code', label: '代码开发' },
		{ name: 'terminal', label: '命令工具' },
		{ name: 'wrench', label: '工具维护' },
		{ name: 'cog', label: '配置工程' },
		{ name: 'cpu', label: '控制硬件' },
		{ name: 'circuit-board', label: '电气控制' },
		{ name: 'factory', label: '制造现场' },
		{ name: 'ruler', label: '尺寸规范' },
		{ name: 'pencil-ruler', label: '设计绘制' },
		{ name: 'drafting-compass', label: '工程制图' },
		{ name: 'compass', label: '方案导航' },
		{ name: 'shield-check', label: '质量校验' },
		{ name: 'lightbulb', label: '创意方案' },
		{ name: 'rocket', label: '发布交付' },
		{ name: 'hammer', label: '构建实施' },
		{ name: 'sparkles', label: '智能生成' }
	];
	const iconBackgroundOptions = [
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

	const fallbackIcon = (skillName: string) => iconOptions[hashString(skillName) % 8].name;
	const fallbackIconBackground = (skillName: string) =>
		iconBackgroundOptions[hashString(skillName) % iconBackgroundOptions.length];

	const formatVersion = (version?: string | null) => {
		if (!version) return '未标版本';
		return version.toLowerCase().startsWith('v') ? version : `v${version}`;
	};

	const normalizeLucideIconName = (value: string) => {
		const urlMatch = value.trim().match(/lucide\.dev\/icons\/([a-z0-9-]+)/i);
		const source = urlMatch?.[1] ?? value;

		return source
			.trim()
			.replace(/\.svg$/i, '')
			.replace(/^lucide[-_]/i, '')
			.replace(/([a-z0-9])([A-Z])/g, '$1-$2')
			.replace(/[\s_]+/g, '-')
			.replace(/[^a-zA-Z0-9-]/g, '')
			.replace(/-+/g, '-')
			.replace(/^-|-$/g, '')
			.toLowerCase();
	};

	const isValidLucideIconName = (value: string) =>
		value.length > 0 && value.length <= 64 && /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(value);

	const addCustomIcon = () => {
		const iconName = normalizeLucideIconName(customIconName);
		if (!isValidLucideIconName(iconName)) {
			toast.error('请输入有效的 lucide icon 名称');
			return;
		}

		updateDraftIconMetadata(iconName, selectedIconBackground);
		customIconName = iconName;
	};

	const splitSourceFrontmatter = (content: string) => {
		const match = content.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n)?/);
		if (!match) return { frontmatter: {}, body: content };

		try {
			const parsed = parseDocument(match[1]).toJS() ?? {};
			return {
				frontmatter: typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {},
				body: content.slice(match[0].length)
			};
		} catch {
			return { frontmatter: {}, body: content };
		}
	};

	const getIndent = (line: string) => line.length - line.trimStart().length;

	const findYamlBlockEnd = (lines: string[], start: number, baseIndent: number) => {
		for (let index = start + 1; index < lines.length; index += 1) {
			const line = lines[index];
			if (!line.trim()) continue;
			if (getIndent(line) <= baseIndent) return index;
		}
		return lines.length;
	};

	const buildOpenWebuiMetadataBlock = (icon: string, iconBackground: string) => [
		'  open_webui:',
		'    expert_agent:',
		`      icon: ${icon}`,
		`      icon_background: '${iconBackground}'`
	];

	const normalizeMetadataKeySpacing = (rawFrontmatter: string) =>
		rawFrontmatter
			.split(/\r?\n/)
			.map((line) =>
				line.replace(/^(\s*(?:tags|category|related_skills|icon|icon_background):)(\S)/, '$1 $2')
			)
			.join('\n');

	const normalizeSourceFrontmatterKeySpacing = (content: string) => {
		const match = content.match(/^(---\s*\r?\n)([\s\S]*?)(\r?\n---\s*(?:\r?\n)?)([\s\S]*)$/);
		if (!match) return content;

		return `${match[1]}${normalizeMetadataKeySpacing(match[2])}${match[3]}${match[4]}`;
	};

	const injectOpenWebuiMetadata = (
		rawFrontmatter: string,
		icon: string,
		iconBackground: string
	) => {
		const lines = rawFrontmatter.split(/\r?\n/);
		const block = buildOpenWebuiMetadataBlock(icon, iconBackground);
		const metadataIndex = lines.findIndex((line) => /^metadata:\s*(?:#.*)?$/.test(line));

		if (metadataIndex === -1) {
			while (lines.length && !lines.at(-1)?.trim()) {
				lines.pop();
			}
			lines.push('metadata:', ...block);
			return normalizeMetadataKeySpacing(lines.join('\n'));
		}

		const metadataIndent = getIndent(lines[metadataIndex]);
		const metadataEnd = findYamlBlockEnd(lines, metadataIndex, metadataIndent);
		const openWebuiIndex = lines.findIndex((line, index) => {
			if (index <= metadataIndex || index >= metadataEnd) return false;
			return line.trim().startsWith('open_webui:') && getIndent(line) === metadataIndent + 2;
		});

		if (openWebuiIndex !== -1) {
			const openWebuiEnd = findYamlBlockEnd(lines, openWebuiIndex, metadataIndent + 2);
			lines.splice(openWebuiIndex, openWebuiEnd - openWebuiIndex, ...block);
		} else {
			lines.splice(metadataEnd, 0, ...block);
		}

		return normalizeMetadataKeySpacing(lines.join('\n'));
	};

	const getSourceMetadata = (content: string) => {
		const { frontmatter } = splitSourceFrontmatter(content);
		const metadata = frontmatter?.metadata;
		const expertAgentMetadata = metadata?.open_webui?.expert_agent;

		return {
			version: frontmatter?.version ? `${frontmatter.version}` : null,
			author: frontmatter?.author ? `${frontmatter.author}` : null,
			icon: expertAgentMetadata?.icon ? `${expertAgentMetadata.icon}` : null,
			icon_background: expertAgentMetadata?.icon_background
				? `${expertAgentMetadata.icon_background}`
				: null
		};
	};

	const applyExpertAgentMetadataToSource = (
		content: string,
		icon: string,
		iconBackground: string
	) => {
		const match = content.match(/^(---\s*\r?\n)([\s\S]*?)(\r?\n---\s*(?:\r?\n)?)([\s\S]*)$/);
		if (!match) {
			return `---\n${injectOpenWebuiMetadata('', icon, iconBackground)}\n---\n\n${content.trimStart()}`;
		}

		return `${match[1]}${injectOpenWebuiMetadata(match[2], icon, iconBackground)}${match[3]}${match[4]}`;
	};

	const withSourceFallbackMetadata = (detail: ExpertSkillDetail) => {
		const sourceMetadata = getSourceMetadata(detail.content ?? '');
		return {
			...detail,
			version: detail.version || sourceMetadata.version,
			author: detail.author || sourceMetadata.author,
			icon: detail.icon || sourceMetadata.icon,
			icon_background: detail.icon_background || sourceMetadata.icon_background
		};
	};

	const updateDraftIconMetadata = (
		icon = selectedIcon,
		iconBackground = selectedIconBackground
	) => {
		selectedIcon = icon;
		selectedIconBackground = iconBackground;
		if (detailSourceContent.trim()) {
			detailSourceContent = applyExpertAgentMetadataToSource(
				detailSourceContent,
				icon,
				iconBackground
			);
		}
		if (selectedSkillDetail) {
			selectedSkillDetail = {
				...selectedSkillDetail,
				icon,
				icon_background: iconBackground,
				content: detailSourceContent
			};
		}
		refreshDetailMarkdownContent();
	};

	onMount(() => {
		const handlePointerDown = (event: PointerEvent) => {
			if (!showIconPicker) return;

			const target = event.target as Node | null;
			if (target && (iconPickerPanel?.contains(target) || iconPickerButton?.contains(target))) {
				return;
			}

			showIconPicker = false;
		};

		document.addEventListener('pointerdown', handlePointerDown, true);
		return () => document.removeEventListener('pointerdown', handlePointerDown, true);
	});

	const close = () => {
		show = false;
		showDetailModal = false;
		showIconPicker = false;
		dispatch('close');
	};

	const loadExpertAgents = async () => {
		loading = true;
		error = null;

		try {
			const loadedItems = await getExpertAgents(localStorage.token);
			items = await Promise.all(
				loadedItems.map(async (item) => {
					if (item.version && item.author && item.icon && item.icon_background) return item;

					try {
						const detail = withSourceFallbackMetadata(
							await getExpertAgentDetail(item.skill_name, localStorage.token)
						);
						return {
							...item,
							version: item.version || detail.version,
							author: item.author || detail.author,
							icon: item.icon || detail.icon,
							icon_background: item.icon_background || detail.icon_background
						};
					} catch {
						return item;
					}
				})
			);
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
		detailSourceContent = '';
		detailError = null;
		detailLoading = true;
		detailMode = 'preview';
		selectedIcon = skill.icon || fallbackIcon(skill.skill_name);
		selectedIconBackground = skill.icon_background || fallbackIconBackground(skill.skill_name);
		showIconPicker = false;
		showDetailModal = true;

		try {
			selectedSkillDetail = withSourceFallbackMetadata(
				await getExpertAgentDetail(skill.skill_name, localStorage.token)
			);
			detailMarkdownContent = formatSkillDetailContent(selectedSkillDetail, skill);
			detailSourceContent = selectedSkillDetail.content ?? '';
			selectedIcon = selectedSkillDetail.icon || selectedIcon;
			selectedIconBackground = selectedSkillDetail.icon_background || selectedIconBackground;
			selectedSkill = {
				...skill,
				version: skill.version || selectedSkillDetail.version,
				author: skill.author || selectedSkillDetail.author,
				icon: skill.icon || selectedSkillDetail.icon,
				icon_background: skill.icon_background || selectedSkillDetail.icon_background
			};
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

	const refreshDetailMarkdownContent = () => {
		if (!selectedSkillDetail) return;
		detailMarkdownContent = formatSkillDetailContent(
			{ ...selectedSkillDetail, content: detailSourceContent },
			selectedSkill ?? { skill_name: '', description: '' }
		);
	};

	const saveSkillDetail = async () => {
		if (!selectedSkill) return;

		savingDetail = true;
		try {
			const previousSkillName = selectedSkill.skill_name;
			const updatedDetail = await updateExpertAgentDetail(
				selectedSkill.skill_name,
				{
					content: normalizeSourceFrontmatterKeySpacing(detailSourceContent),
					icon: selectedIcon,
					icon_background: selectedIconBackground
				},
				localStorage.token
			);

			selectedSkillDetail = updatedDetail;
			detailSourceContent = updatedDetail.content ?? '';
			detailMarkdownContent = formatSkillDetailContent(updatedDetail, selectedSkill);
			const updatedCard = {
				...selectedSkill,
				skill_name: updatedDetail.name || selectedSkill.skill_name,
				description: updatedDetail.description || selectedSkill.description,
				version: updatedDetail.version,
				author: updatedDetail.author,
				icon: updatedDetail.icon,
				icon_background: updatedDetail.icon_background
			};
			selectedSkill = updatedCard;
			items = items.map((item) => (item.skill_name === previousSkillName ? updatedCard : item));
			toast.success('专家技能已保存');
		} catch (err) {
			console.error(err);
			toast.error(`${err}`);
		} finally {
			savingDetail = false;
		}
	};

	$: if (show && !loaded && !loading) {
		void loadExpertAgents();
	}

	$: if (!show && showDetailModal) {
		showDetailModal = false;
	}
</script>

{#if show}
	<div class="flex h-full min-h-0 flex-col bg-transparent text-gray-900 dark:text-gray-100">
		<div class="flex shrink-0 items-start justify-between gap-3 px-4 pb-3 pt-4">
			<div class="min-w-0">
				<div class="text-base font-semibold leading-6 text-[#20283a] dark:text-gray-100">
					Expert Agent
				</div>
				<div class="mt-1 text-[13px] leading-5 text-[#718097] dark:text-gray-400">
					选择一个专家技能开始会话
				</div>
			</div>

			<button
				type="button"
				class="rounded-lg p-1.5 text-[#7f8aa0] transition hover:bg-[#edf1f7] hover:text-[#293246] dark:hover:bg-gray-800 dark:hover:text-gray-100"
				aria-label="关闭专家面板"
				on:click={close}
			>
				<XMark className="size-4" />
			</button>
		</div>

		<div class="expert-agent-card-list min-h-0 flex-1 overflow-y-auto px-4 pb-4">
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
				<div class="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-3 pb-4">
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
	size="xl"
	bind:show={showDetailModal}
	containerClassName="p-4 backdrop-blur-sm"
	className="overflow-hidden bg-white dark:bg-gray-900 rounded-2xl"
>
	<div class="flex h-[82vh] min-h-[32rem] flex-col text-gray-900 dark:text-gray-100">
		<div
			class="expert-skill-detail-header flex shrink-0 items-start justify-between gap-4 border-b border-gray-100 px-5 py-4 dark:border-gray-800"
		>
			<div class="flex min-w-0 items-start gap-3">
				<div class="relative shrink-0">
					<button
						bind:this={iconPickerButton}
						type="button"
						class="skill-detail-icon flex h-12 w-12 items-center justify-center rounded-xl text-[#31506b] transition hover:ring-2 hover:ring-[#2f3a52]/15 focus:outline-none focus:ring-2 focus:ring-[#2f3a52]/20 dark:hover:ring-gray-200/20"
						style:background-color={selectedIconBackground}
						aria-label="选择专家技能图标"
						on:click={() => {
							showIconPicker = !showIconPicker;
						}}
					>
						<LucideIcon name={selectedIcon} className="size-5" strokeWidth="1.9" />
					</button>

					{#if showIconPicker}
						<div
							bind:this={iconPickerPanel}
							class="absolute left-0 top-14 z-50 w-[26rem] rounded-xl border border-[#d8deea] bg-white p-3 shadow-[0_18px_48px_rgba(47,58,82,0.18)] dark:border-gray-700 dark:bg-gray-900"
						>
							<div class="grid grid-cols-8 gap-1.5">
								{#each iconBackgroundOptions as background}
									<button
										type="button"
										class="size-7 rounded-full border transition {selectedIconBackground ===
										background
											? 'border-[#2f3a52] ring-2 ring-[#2f3a52]/20 dark:border-gray-200 dark:ring-gray-200/20'
											: 'border-[#d8deea] hover:border-[#aeb9cc] dark:border-gray-700'}"
										style:background-color={background}
										aria-label={`选择背景色 ${background}`}
										on:click={() => {
											updateDraftIconMetadata(selectedIcon, background);
										}}
									></button>
								{/each}
							</div>

							<div class="mt-3 grid grid-cols-8 gap-1.5">
								{#each iconOptions as iconOption}
									<button
										type="button"
										class="flex size-9 items-center justify-center rounded-lg border transition {selectedIcon ===
										iconOption.name
											? 'border-[#2f3a52] bg-[#2f3a52] text-white dark:border-gray-200 dark:bg-gray-200 dark:text-gray-900'
											: 'border-[#d8deea] bg-white text-[#667289] hover:border-[#aeb9cc] hover:bg-[#f7f9fc] dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800'}"
										title={iconOption.label}
										aria-label={`选择 ${iconOption.label} 图标`}
										on:click={() => {
											updateDraftIconMetadata(iconOption.name, selectedIconBackground);
										}}
									>
										<LucideIcon name={iconOption.name} className="size-4" strokeWidth="1.9" />
									</button>
								{/each}
							</div>

							<div
								class="mt-3 flex items-center gap-2 border-t border-[#edf1f6] pt-3 dark:border-gray-800"
							>
								<input
									class="h-8 min-w-0 flex-1 rounded-lg border border-[#d8deea] bg-[#fbfcff] px-2.5 text-xs text-[#293246] outline-none transition placeholder:text-[#9aa4b5] focus:border-[#8b96aa] focus:ring-2 focus:ring-[#8b96aa]/15 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-100"
									bind:value={customIconName}
									placeholder="输入 lucide icon 名称"
									spellcheck="false"
									on:keydown={(event) => {
										if (event.key === 'Enter') {
											event.preventDefault();
											addCustomIcon();
										}
									}}
								/>
								<button
									type="button"
									class="inline-flex h-8 shrink-0 items-center justify-center rounded-lg bg-[#2f3a52] px-3 text-xs font-semibold text-white transition hover:bg-[#222b3f] dark:bg-gray-200 dark:text-gray-900 dark:hover:bg-white"
									on:click={addCustomIcon}
								>
									添加
								</button>
							</div>
						</div>
					{/if}
				</div>

				<div class="min-w-0">
					<div class="line-clamp-2 text-lg font-semibold leading-6">
						{selectedSkillDetail?.name || selectedSkill?.skill_name || '专家技能详情'}
					</div>
					<div class="mt-2 flex flex-wrap items-center gap-2">
						<div
							class="rounded-md border border-[#d8deea] bg-white/70 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#7a8498] dark:border-gray-700 dark:bg-gray-900/60 dark:text-gray-300"
						>
							{formatVersion(selectedSkillDetail?.version || selectedSkill?.version)}
						</div>
						{#if selectedSkillDetail?.author || selectedSkill?.author}
							<div
								class="max-w-[18rem] truncate rounded-md border border-[#d8deea] bg-white/70 px-2 py-0.5 text-[11px] font-medium text-[#667289] dark:border-gray-700 dark:bg-gray-900/60 dark:text-gray-300"
								title={selectedSkillDetail?.author || selectedSkill?.author}
							>
								{selectedSkillDetail?.author || selectedSkill?.author}
							</div>
						{/if}
					</div>
					{#if selectedSkillDetail?.description || selectedSkill?.description}
						<div class="mt-2 text-sm leading-5 text-gray-500 dark:text-gray-400">
							{selectedSkillDetail?.description || selectedSkill?.description}
						</div>
					{/if}
				</div>
			</div>

			<button
				type="button"
				class="rounded-lg p-1.5 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-gray-100"
				aria-label="关闭专家技能详情"
				on:click={() => {
					showIconPicker = false;
					showDetailModal = false;
				}}
			>
				<XMark className="size-5" />
			</button>
		</div>

		<div
			class="flex shrink-0 flex-col gap-3 border-b border-gray-100 px-5 py-3 dark:border-gray-800"
		>
			<div class="flex items-center justify-between gap-3">
				<div class="flex items-center rounded-lg bg-[#edf1f7] p-1 dark:bg-gray-800">
					<button
						type="button"
						class="rounded-md px-3 py-1.5 text-xs font-medium transition {detailMode === 'preview'
							? 'bg-white text-[#293246] shadow-xs dark:bg-gray-700 dark:text-gray-100'
							: 'text-[#667289] hover:text-[#293246] dark:text-gray-300 dark:hover:text-gray-100'}"
						on:click={() => {
							refreshDetailMarkdownContent();
							detailMode = 'preview';
						}}
					>
						预览
					</button>
					<button
						type="button"
						class="rounded-md px-3 py-1.5 text-xs font-medium transition {detailMode === 'source'
							? 'bg-white text-[#293246] shadow-xs dark:bg-gray-700 dark:text-gray-100'
							: 'text-[#667289] hover:text-[#293246] dark:text-gray-300 dark:hover:text-gray-100'}"
						on:click={() => {
							detailMode = 'source';
						}}
					>
						源文件
					</button>
				</div>

				<button
					type="button"
					class="inline-flex h-8 items-center justify-center rounded-lg bg-[#2f3a52] px-3 text-xs font-semibold text-white transition hover:bg-[#222b3f] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-gray-200 dark:text-gray-900 dark:hover:bg-white"
					disabled={savingDetail || detailLoading || !!detailError}
					on:click={saveSkillDetail}
				>
					{savingDetail ? '保存中...' : '保存'}
				</button>
			</div>
		</div>

		<div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
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
			{:else if detailMode === 'source'}
				<textarea
					class="expert-skill-source-editor h-full min-h-0 w-full resize-none rounded-xl border border-[#d8deea] bg-[#fbfcff] p-4 font-mono text-[12px] leading-5 text-[#293246] outline-none transition focus:border-[#8b96aa] focus:ring-2 focus:ring-[#8b96aa]/15 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-100 dark:focus:border-gray-500"
					bind:value={detailSourceContent}
					spellcheck="false"
				/>
			{:else if detailMarkdownContent}
				<div class="expert-skill-markdown w-full max-w-none text-[13px]">
					<Markdown
						id={`expert-skill-detail-${selectedSkillDetail?.name || selectedSkill?.skill_name}`}
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
