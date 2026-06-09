<script lang="ts">
	import { createEventDispatcher, getContext, onMount } from 'svelte';
	import type { Readable } from 'svelte/store';
	import { parseDocument } from 'yaml';

	import {
		getExpertAgentDetail,
		getExpertAgents,
		openExpertAgentDirectory,
		updateExpertAgentAppearance,
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
	import { isLocalLucideIconName } from './lucideIconNames';

	export let show = false;

	const i18n = getContext<Readable<{ language?: string }>>('i18n');
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
	let appearanceSaveRequest = 0;
	let selectedIcon = 'sparkles';
	let selectedIconBackground = '#e6edf7';
	let showIconPicker = false;
	let customIconName = '';
	let iconPickerButton: HTMLButtonElement | null = null;
	let iconPickerPanel: HTMLDivElement | null = null;
	let sourceEditor: HTMLTextAreaElement | null = null;
	let sourceDirty = false;
	let searchQuery = '';
	let showCategoryFilters = false;

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
	const tagStyles = [
		{ background: '#eef2f6', color: '#5f6f82', border: '#dde5ee' },
		{ background: '#eef4f0', color: '#607568', border: '#dfe9e2' },
		{ background: '#f4f1ec', color: '#7a6955', border: '#e8e1d7' },
		{ background: '#f1f0f5', color: '#6d6681', border: '#e3e0eb' },
		{ background: '#edf3f4', color: '#5f7479', border: '#dce8ea' }
	];

	const hashString = (value: string) =>
		Array.from(value || 'expert-agent').reduce((acc, char) => acc + char.charCodeAt(0), 0);
	const featuredSkillName = 'expert-agent-builder';
	const isChineseLanguage = (language?: string) => language?.toLowerCase().startsWith('zh');
	const drawerCopy = {
		zh: {
			subtitle: '开始使用专家技能，或创建一个新的专家',
			closePanel: '关闭专家面板',
			refreshPanel: '刷新专家技能列表',
			searchPlaceholder: '搜索专家技能',
			searchAria: '搜索专家技能',
			clearSearch: '清空专家技能搜索',
			showFilters: '显示专家技能筛选标签',
			hideFilters: '隐藏专家技能筛选标签',
			categoryFilters: ['全部', '设计需求', '设计选型', '风险分析', 'BOM'],
			loading: '正在加载专家技能...',
			loadError: '无法加载专家技能',
			retry: '重试',
			emptyTitle: '还没有可用的专家技能',
			emptyDescription: '创建 Hermes Skill 后，它会显示在这里。',
			noMatchTitle: '没有匹配的专家技能',
			noMatchDescription: '请尝试按专家名称或标签搜索。',
			invalidIconName: '请输入有效的 lucide icon 名称',
			unversioned: '未标版本',
			detailTitle: '专家技能详情',
			chooseIcon: '选择专家技能图标',
			chooseBackground: '选择背景色',
			chooseIconOption: '选择',
			customIconPlaceholder: '输入 lucide icon 名称',
			add: '添加',
			sourceStatsTitle: '源文件总行数 / 总字数',
			sourceStats: (lines: number, characters: number) => `${lines} 行 / ${characters} 字`,
			closeDetail: '关闭专家技能详情',
			preview: '预览',
			source: '源文件',
			saving: '保存中...',
			save: '保存',
			openDirectory: '打开目录',
			saved: '专家技能已保存',
			detailLoadError: '无法加载专家技能详情',
			detailLoading: '正在加载完整技能文档...',
			detailEmpty: '暂无完整技能文档',
			iconLabels: {
				bot: 'AI 专家',
				'brain-circuit': '知识推理',
				'messages-square': '访谈沟通',
				'book-open': '知识库',
				search: '搜索研究',
				'scan-search': '检查识别',
				'clipboard-list': '需求清单',
				'file-text': '文档报告',
				table: '表格数据',
				'chart-no-axes-combined': '分析图表',
				presentation: '演示文稿',
				workflow: '流程编排',
				database: '数据资产',
				package: '制品交付',
				boxes: '组件模块',
				blocks: '系统结构',
				code: '代码开发',
				terminal: '命令工具',
				wrench: '工具维护',
				cog: '配置工程',
				cpu: '控制硬件',
				'circuit-board': '电气控制',
				factory: '制造现场',
				ruler: '尺寸规范',
				'pencil-ruler': '设计绘制',
				'drafting-compass': '工程制图',
				compass: '方案导航',
				'shield-check': '质量校验',
				lightbulb: '创意方案',
				rocket: '发布交付',
				hammer: '构建实施',
				sparkles: '智能生成'
			}
		},
		en: {
			subtitle: 'Start with an expert skill, or create a new expert',
			closePanel: 'Close expert panel',
			refreshPanel: 'Refresh expert skill list',
			searchPlaceholder: 'Search expert skills',
			searchAria: 'Search expert skills',
			clearSearch: 'Clear expert skill search',
			showFilters: 'Show expert skill filters',
			hideFilters: 'Hide expert skill filters',
			categoryFilters: ['All', 'Requirements', 'Selection', 'Risk Analysis', 'BOM'],
			loading: 'Loading expert skills...',
			loadError: 'Unable to load expert skills',
			retry: 'Retry',
			emptyTitle: 'No expert skills available yet',
			emptyDescription: 'Create a Hermes Skill and it will appear here.',
			noMatchTitle: 'No matching expert skills',
			noMatchDescription: 'Try searching by expert name or tag.',
			invalidIconName: 'Enter a valid lucide icon name',
			unversioned: 'Unversioned',
			detailTitle: 'Expert skill details',
			chooseIcon: 'Choose expert skill icon',
			chooseBackground: 'Choose background color',
			chooseIconOption: 'Choose',
			customIconPlaceholder: 'Enter lucide icon name',
			add: 'Add',
			sourceStatsTitle: 'Source lines / words',
			sourceStats: (lines: number, characters: number) => `${lines} lines / ${characters} words`,
			closeDetail: 'Close expert skill details',
			preview: 'Preview',
			source: 'Source',
			saving: 'Saving...',
			save: 'Save',
			openDirectory: 'Open directory',
			saved: 'Expert skill saved',
			detailLoadError: 'Unable to load expert skill details',
			detailLoading: 'Loading full skill document...',
			detailEmpty: 'No full skill document available',
			iconLabels: {
				bot: 'AI expert',
				'brain-circuit': 'Knowledge reasoning',
				'messages-square': 'Conversation',
				'book-open': 'Knowledge base',
				search: 'Search research',
				'scan-search': 'Inspection',
				'clipboard-list': 'Requirements',
				'file-text': 'Documents',
				table: 'Tables',
				'chart-no-axes-combined': 'Analytics',
				presentation: 'Presentation',
				workflow: 'Workflow',
				database: 'Data assets',
				package: 'Delivery',
				boxes: 'Components',
				blocks: 'System structure',
				code: 'Code',
				terminal: 'Command tools',
				wrench: 'Maintenance',
				cog: 'Configuration',
				cpu: 'Hardware control',
				'circuit-board': 'Electrical control',
				factory: 'Manufacturing',
				ruler: 'Dimensions',
				'pencil-ruler': 'Design drafting',
				'drafting-compass': 'Engineering drawing',
				compass: 'Solution navigation',
				'shield-check': 'Quality check',
				lightbulb: 'Ideation',
				rocket: 'Launch',
				hammer: 'Build',
				sparkles: 'Generation'
			}
		}
	};
	$: copy = isChineseLanguage($i18n.language) ? drawerCopy.zh : drawerCopy.en;
	$: categoryFilters = copy.categoryFilters;

	const skillMatchesSearch = (skill: ExpertSkillCard, query: string) => {
		if (!query) return true;
		return [skill.skill_name, ...(skill.tags ?? [])].some((value) =>
			value.toLowerCase().includes(query)
		);
	};
	const sortExpertSkillsByUsage = (skills: ExpertSkillCard[]) =>
		[...skills].sort(
			(a, b) =>
				(b.usage_count ?? 0) - (a.usage_count ?? 0) || a.skill_name.localeCompare(b.skill_name)
		);

	const fallbackIcon = (skillName: string) => iconOptions[hashString(skillName) % 8].name;
	const fallbackIconBackground = (skillName: string) =>
		iconBackgroundOptions[hashString(skillName) % iconBackgroundOptions.length];

	const formatVersion = (version?: string | null) => {
		if (!version) return copy.unversioned;
		return version.toLowerCase().startsWith('v') ? version : `v${version}`;
	};

	const getIconLabel = (iconName: string) =>
		copy.iconLabels[iconName as keyof typeof copy.iconLabels] ?? iconName;

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
		value.length > 0 &&
		value.length <= 64 &&
		/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(value) &&
		isLocalLucideIconName(value);

	const getLineCount = (content: string) =>
		content.length ? content.split(/\r\n|\r|\n/).length : 1;
	const getLineNumbers = (content: string) =>
		Array.from({ length: getLineCount(content) }, (_, index) => index + 1);
	const getContentStats = (content: string) => ({
		lines: getLineCount(content),
		characters: Array.from(content.replace(/\s/g, '')).length
	});

	const addCustomIcon = () => {
		const iconName = normalizeLucideIconName(customIconName);
		if (!isValidLucideIconName(iconName)) {
			toast.error(copy.invalidIconName);
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

	const syncSelectedSkillAppearance = (icon: string, iconBackground: string) => {
		if (!selectedSkill) return;

		const previousSkillName = selectedSkill.skill_name;
		const updatedCard = {
			...selectedSkill,
			icon,
			icon_background: iconBackground
		};

		selectedSkill = updatedCard;
		items = items.map((item) => (item.skill_name === previousSkillName ? updatedCard : item));
	};

	const updateDraftIconMetadata = (
		icon = selectedIcon,
		iconBackground = selectedIconBackground,
		persist = true
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
		syncSelectedSkillAppearance(icon, iconBackground);
		refreshDetailMarkdownContent();
		if (persist) {
			void saveSkillAppearance(icon, iconBackground);
		}
	};

	const applyUpdatedDetail = (updatedDetail: ExpertSkillDetail, previousSkillName: string) => {
		const savedAt = updatedDetail.updated_at || new Date().toISOString();
		selectedSkillDetail = {
			...withSourceFallbackMetadata(updatedDetail),
			updated_at: savedAt
		};
		detailSourceContent = selectedSkillDetail.content ?? '';
		detailMarkdownContent = formatSkillDetailContent(
			selectedSkillDetail,
			selectedSkill ?? { skill_name: '', description: '' }
		);

		const updatedCard = {
			...(selectedSkill ?? {
				skill_name: previousSkillName,
				description: selectedSkillDetail.description || ''
			}),
			skill_name: selectedSkillDetail.name || previousSkillName,
			description: selectedSkillDetail.description || selectedSkill?.description || '',
			version: selectedSkillDetail.version,
			updated_at: savedAt,
			author: selectedSkillDetail.author,
			icon: selectedSkillDetail.icon,
			icon_background: selectedSkillDetail.icon_background,
			tags: selectedSkillDetail.tags || selectedSkill?.tags
		};

		selectedSkill = updatedCard;
		items = items.map((item) => (item.skill_name === previousSkillName ? updatedCard : item));
		selectedIcon = selectedSkillDetail.icon || selectedIcon;
		selectedIconBackground = selectedSkillDetail.icon_background || selectedIconBackground;
	};

	const saveSkillAppearance = async (icon: string, iconBackground: string) => {
		if (!selectedSkill) return;

		const requestId = ++appearanceSaveRequest;
		const previousSkillName = selectedSkill.skill_name;

		try {
			const updatedDetail = await updateExpertAgentAppearance(
				previousSkillName,
				{
					icon,
					icon_background: iconBackground
				},
				localStorage.token
			);

			if (requestId !== appearanceSaveRequest) return;

			const savedAt = updatedDetail.updated_at || new Date().toISOString();
			const mergedDetail = withSourceFallbackMetadata(updatedDetail);
			selectedSkillDetail = {
				...mergedDetail,
				updated_at: savedAt,
				content: sourceDirty ? detailSourceContent : mergedDetail.content
			};

			const updatedCard = {
				...selectedSkill,
				skill_name: mergedDetail.name || previousSkillName,
				description: mergedDetail.description || selectedSkill.description,
				version: mergedDetail.version,
				updated_at: savedAt,
				author: mergedDetail.author,
				icon: mergedDetail.icon || icon,
				icon_background: mergedDetail.icon_background || iconBackground,
				tags: mergedDetail.tags || selectedSkill.tags
			};

			selectedSkill = updatedCard;
			items = items.map((item) => (item.skill_name === previousSkillName ? updatedCard : item));

			if (!sourceDirty) {
				detailSourceContent = mergedDetail.content ?? '';
				detailMarkdownContent = formatSkillDetailContent(mergedDetail, updatedCard);
			}
		} catch (err) {
			console.error(err);
			toast.error(`${err}`);
		}
	};

	const openSkillDirectory = async () => {
		if (!selectedSkill) return;

		try {
			await openExpertAgentDirectory(selectedSkill.skill_name, localStorage.token);
		} catch (err) {
			console.error(err);
			toast.error(`${err}`);
		}
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
					if (
						item.version &&
						item.author &&
						item.icon &&
						item.icon_background &&
						item.tags?.length
					) {
						return item;
					}

					try {
						const detail = withSourceFallbackMetadata(
							await getExpertAgentDetail(item.skill_name, localStorage.token)
						);
						return {
							...item,
							version: item.version || detail.version,
							updated_at: item.updated_at || detail.updated_at,
							author: item.author || detail.author,
							icon: item.icon || detail.icon,
							icon_background: item.icon_background || detail.icon_background,
							tags: item.tags?.length ? item.tags : detail.tags
						};
					} catch {
						return item;
					}
				})
			);
			loaded = true;
		} catch (err) {
			console.error(err);
			error = copy.loadError;
		} finally {
			loading = false;
		}
	};

	const refreshExpertAgents = async () => {
		loaded = false;
		await loadExpertAgents();
	};

	const openSkillDetail = async (skill: ExpertSkillCard) => {
		selectedSkill = skill;
		selectedSkillDetail = null;
		detailMarkdownContent = '';
		detailSourceContent = '';
		detailError = null;
		detailLoading = true;
		detailMode = 'preview';
		sourceDirty = false;
		selectedIcon = skill.icon || fallbackIcon(skill.skill_name);
		selectedIconBackground = skill.icon_background || fallbackIconBackground(skill.skill_name);
		showIconPicker = false;
		showDetailModal = true;

		try {
			const loadedDetail = withSourceFallbackMetadata(
				await getExpertAgentDetail(skill.skill_name, localStorage.token)
			);
			selectedSkillDetail = loadedDetail;
			detailMarkdownContent = formatSkillDetailContent(loadedDetail, skill);
			detailSourceContent = loadedDetail.content ?? '';
			selectedIcon = loadedDetail.icon || selectedIcon;
			selectedIconBackground = loadedDetail.icon_background || selectedIconBackground;
			selectedSkill = {
				...skill,
				version: skill.version || loadedDetail.version,
				updated_at: skill.updated_at || loadedDetail.updated_at,
				author: skill.author || loadedDetail.author,
				icon: skill.icon || loadedDetail.icon,
				icon_background: skill.icon_background || loadedDetail.icon_background,
				tags: skill.tags?.length ? skill.tags : loadedDetail.tags
			};
		} catch (err) {
			console.error(err);
			detailError = copy.detailLoadError;
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

			applyUpdatedDetail(updatedDetail, previousSkillName);
			sourceDirty = false;
			toast.success(copy.saved);
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

	$: sourceLineNumbers = getLineNumbers(detailSourceContent);
	$: previewLineNumbers = getLineNumbers(detailMarkdownContent);
	$: detailSourceStats = getContentStats(detailSourceContent);
	$: normalizedSearchQuery = searchQuery.trim().toLowerCase();
	$: filteredItems = items.filter((item) => skillMatchesSearch(item, normalizedSearchQuery));
	$: featuredSkill = filteredItems.find((item) => item.skill_name === featuredSkillName);
	$: regularItems = featuredSkill
		? sortExpertSkillsByUsage(filteredItems.filter((item) => item.skill_name !== featuredSkillName))
		: sortExpertSkillsByUsage(filteredItems);
</script>

{#if show}
	<div
		class="expert-agent-drawer flex h-full min-h-0 flex-col bg-transparent text-gray-900 dark:text-gray-100"
	>
		<div class="flex shrink-0 items-start justify-between gap-3 px-4 pb-2 pt-4">
			<div class="min-w-0">
				<div class="text-xl font-semibold leading-7 text-[#20283a] dark:text-gray-100">
					Expert Agent
				</div>
				<div class="mt-1 text-[13px] leading-5 text-[#718097] dark:text-gray-400">
					{copy.subtitle}
				</div>
			</div>

			<div class="flex shrink-0 items-center gap-2">
				<button
					type="button"
					class="rounded-lg p-1.5 text-[#7f8aa0] transition hover:bg-[#edf1f7] hover:text-[#293246] disabled:cursor-not-allowed disabled:opacity-60 dark:hover:bg-gray-800 dark:hover:text-gray-100"
					aria-label={copy.refreshPanel}
					title={copy.refreshPanel}
					disabled={loading}
					on:click={() => {
						void refreshExpertAgents();
					}}
				>
					<LucideIcon
						name="refresh-cw"
						className="size-4 {loading ? 'animate-spin' : ''}"
						strokeWidth="1.9"
					/>
				</button>
				<button
					type="button"
					class="rounded-lg p-1.5 text-[#7f8aa0] transition hover:bg-[#edf1f7] hover:text-[#293246] dark:hover:bg-gray-800 dark:hover:text-gray-100"
					aria-label={copy.closePanel}
					title={copy.closePanel}
					on:click={close}
				>
					<XMark className="size-4" />
				</button>
			</div>
		</div>

		<div class="shrink-0 px-4 pb-3">
			<div
				class="flex h-9 items-center gap-2 rounded-xl border border-[#d7e7f7] bg-white/72 px-3 text-[#6f819d] shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] dark:border-gray-800 dark:bg-gray-900/72 dark:text-gray-400"
			>
				<LucideIcon name="search" className="size-4 shrink-0" strokeWidth="1.8" />
				<input
					class="min-w-0 flex-1 bg-transparent text-[12px] font-medium text-[#314461] outline-none placeholder:text-[#8da0ba] dark:text-gray-100 dark:placeholder:text-gray-500"
					bind:value={searchQuery}
					placeholder={copy.searchPlaceholder}
					aria-label={copy.searchAria}
					spellcheck="false"
				/>
				{#if searchQuery}
					<button
						type="button"
						class="flex size-5 shrink-0 items-center justify-center rounded-md text-[#9db0c7] transition hover:bg-[#eef6ff] hover:text-[#4f6f98] dark:hover:bg-gray-800"
						aria-label={copy.clearSearch}
						on:click={() => {
							searchQuery = '';
						}}
					>
						<XMark className="size-3.5" />
					</button>
				{/if}
				<button
					type="button"
					class="flex size-6 shrink-0 items-center justify-center rounded-md text-[#8da0ba] transition hover:bg-[#eef6ff] hover:text-[#4f6f98] dark:hover:bg-gray-800"
					aria-label={showCategoryFilters ? copy.hideFilters : copy.showFilters}
					aria-pressed={showCategoryFilters}
					on:click={() => {
						showCategoryFilters = !showCategoryFilters;
					}}
				>
					<LucideIcon name="filter" className="size-3.5" strokeWidth="1.8" />
				</button>
			</div>

			{#if showCategoryFilters}
				<div class="mt-2 flex flex-wrap items-center gap-1.5">
					{#each categoryFilters as filterLabel, filterIdx}
						<span
							class="expert-agent-filter-chip inline-flex h-6 items-center rounded-full border px-2.5 text-[11px] font-semibold transition {filterIdx ===
							0
								? 'border-[#90c2f2] bg-[#eaf6ff] text-[#0f4f96]'
								: 'border-[#d7e7f7] bg-white/72 text-[#6f819d] dark:border-gray-800 dark:bg-gray-900/72 dark:text-gray-400'}"
						>
							{filterLabel}
						</span>
					{/each}
				</div>
			{/if}
		</div>

		<div class="shrink-0 px-4 pb-3">
			<div
				class="flex h-9 items-center gap-2 rounded-xl border border-[#d7e7f7] bg-white/72 px-3 text-[#6f819d] shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] dark:border-gray-800 dark:bg-gray-900/72 dark:text-gray-400"
			>
				<LucideIcon name="search" className="size-4 shrink-0" strokeWidth="1.8" />
				<input
					class="min-w-0 flex-1 bg-transparent text-[12px] font-medium text-[#314461] outline-none placeholder:text-[#8da0ba] dark:text-gray-100 dark:placeholder:text-gray-500"
					bind:value={searchQuery}
					placeholder="搜索专家技能"
					aria-label="搜索专家技能"
					spellcheck="false"
				/>
				{#if searchQuery}
					<button
						type="button"
						class="flex size-5 shrink-0 items-center justify-center rounded-md text-[#9db0c7] transition hover:bg-[#eef6ff] hover:text-[#4f6f98] dark:hover:bg-gray-800"
						aria-label="清空专家技能搜索"
						on:click={() => {
							searchQuery = '';
						}}
					>
						<XMark className="size-3.5" />
					</button>
				{/if}
				<button
					type="button"
					class="flex size-6 shrink-0 items-center justify-center rounded-md text-[#8da0ba] transition hover:bg-[#eef6ff] hover:text-[#4f6f98] dark:hover:bg-gray-800"
					aria-label={showCategoryFilters ? '隐藏专家技能筛选标签' : '显示专家技能筛选标签'}
					aria-pressed={showCategoryFilters}
					on:click={() => {
						showCategoryFilters = !showCategoryFilters;
					}}
				>
					<LucideIcon name="filter" className="size-3.5" strokeWidth="1.8" />
				</button>
			</div>

			{#if showCategoryFilters}
				<div class="mt-2 flex flex-wrap items-center gap-1.5">
					{#each categoryFilters as filterLabel, filterIdx}
						<span
							class="expert-agent-filter-chip inline-flex h-6 items-center rounded-full border px-2.5 text-[11px] font-semibold transition {filterIdx ===
							0
								? 'border-[#90c2f2] bg-[#eaf6ff] text-[#0f4f96]'
								: 'border-[#d7e7f7] bg-white/72 text-[#6f819d] dark:border-gray-800 dark:bg-gray-900/72 dark:text-gray-400'}"
						>
							{filterLabel}
						</span>
					{/each}
				</div>
			{/if}
		</div>

		<div class="expert-agent-card-list min-h-0 flex-1 overflow-y-auto px-4 pb-4">
			{#if loading}
				<div
					class="flex h-full flex-col items-center justify-center gap-3 text-sm text-gray-500 dark:text-gray-400"
				>
					<Spinner className="size-5" />
					<div>{copy.loading}</div>
				</div>
			{:else if error}
				<div class="flex h-full flex-col items-center justify-center text-center">
					<div class="text-base font-medium text-gray-900 dark:text-gray-100">{copy.loadError}</div>
					<button
						type="button"
						class="mt-4 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-800"
						on:click={() => {
							void refreshExpertAgents();
						}}
					>
						{copy.retry}
					</button>
				</div>
			{:else if items.length === 0}
				<div class="flex h-full flex-col items-center justify-center text-center">
					<div class="text-base font-medium text-gray-900 dark:text-gray-100">
						{copy.emptyTitle}
					</div>
					<div class="mt-2 max-w-64 text-sm text-gray-500 dark:text-gray-400">
						{copy.emptyDescription}
					</div>
				</div>
			{:else if filteredItems.length === 0}
				<div class="flex h-full flex-col items-center justify-center text-center">
					<div class="text-base font-medium text-gray-900 dark:text-gray-100">
						{copy.noMatchTitle}
					</div>
					<div class="mt-2 max-w-64 text-sm text-gray-500 dark:text-gray-400">
						{copy.noMatchDescription}
					</div>
				</div>
			{:else if filteredItems.length === 0}
				<div class="flex h-full flex-col items-center justify-center text-center">
					<div class="text-base font-medium text-gray-900 dark:text-gray-100">
						没有匹配的专家技能
					</div>
					<div class="mt-2 max-w-64 text-sm text-gray-500 dark:text-gray-400">
						请尝试按专家名称或标签搜索。
					</div>
				</div>
			{:else}
				<div class="flex flex-col gap-3 pb-4">
					{#if featuredSkill}
						<ExpertSkillCardComponent
							skill={featuredSkill}
							variant="featured"
							onStart={(skill) => {
								dispatch('start', skill);
							}}
							onDetails={(skill) => {
								void openSkillDetail(skill);
							}}
						/>
					{/if}

					<div class="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-3">
						{#each regularItems as item (item.skill_name)}
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
						aria-label={copy.chooseIcon}
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
										aria-label={`${copy.chooseBackground} ${background}`}
										on:click={() => {
											updateDraftIconMetadata(selectedIcon, background);
										}}
									></button>
								{/each}
							</div>

							<div class="mt-3 grid grid-cols-8 gap-1.5">
								{#each iconOptions as iconName}
									<button
										type="button"
										class="flex size-9 items-center justify-center rounded-lg border transition {selectedIcon ===
										iconName
											? 'border-[#2f3a52] bg-[#2f3a52] text-white dark:border-gray-200 dark:bg-gray-200 dark:text-gray-900'
											: 'border-[#d8deea] bg-white text-[#667289] hover:border-[#aeb9cc] hover:bg-[#f7f9fc] dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800'}"
										title={getIconLabel(iconName)}
										aria-label={`${copy.chooseIconOption} ${getIconLabel(iconName)} icon`}
										on:click={() => {
											updateDraftIconMetadata(iconName, selectedIconBackground);
										}}
									>
										<LucideIcon name={iconName} className="size-4" strokeWidth="1.9" />
									</button>
								{/each}
							</div>

							<div
								class="mt-3 flex items-center gap-2 border-t border-[#edf1f6] pt-3 dark:border-gray-800"
							>
								<input
									class="h-8 min-w-0 flex-1 rounded-lg border border-[#d8deea] bg-[#fbfcff] px-2.5 text-xs text-[#293246] outline-none transition placeholder:text-[#9aa4b5] focus:border-[#8b96aa] focus:ring-2 focus:ring-[#8b96aa]/15 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-100"
									bind:value={customIconName}
									placeholder={copy.customIconPlaceholder}
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
									{copy.add}
								</button>
							</div>
						</div>
					{/if}
				</div>

				<div class="min-w-0">
					<div class="line-clamp-2 text-lg font-semibold leading-6">
						{selectedSkillDetail?.name || selectedSkill?.skill_name || copy.detailTitle}
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
						{#each selectedSkillDetail?.tags || selectedSkill?.tags || [] as tag, tagIdx}
							<span
								class="inline-flex h-5 max-w-[9rem] items-center truncate rounded-md border px-1.5 text-[10px] font-medium leading-none tracking-normal"
								style:background-color={tagStyles[tagIdx % tagStyles.length].background}
								style:border-color={tagStyles[tagIdx % tagStyles.length].border}
								style:color={tagStyles[tagIdx % tagStyles.length].color}
								title={tag}
							>
								{tag}
							</span>
						{/each}
					</div>
					{#if selectedSkillDetail?.description || selectedSkill?.description}
						<div class="mt-2 text-sm leading-5 text-gray-500 dark:text-gray-400">
							{selectedSkillDetail?.description || selectedSkill?.description}
						</div>
					{/if}
				</div>
			</div>

			<div class="flex shrink-0 items-start gap-2">
				<div
					class="mt-0.5 whitespace-nowrap rounded-md border border-[#d8deea] bg-white/70 px-2.5 py-1 text-[11px] font-semibold text-[#667289] shadow-xs dark:border-gray-700 dark:bg-gray-900/60 dark:text-gray-300"
					title={copy.sourceStatsTitle}
				>
					{copy.sourceStats(detailSourceStats.lines, detailSourceStats.characters)}
				</div>
				<button
					type="button"
					class="rounded-lg p-1.5 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-gray-100"
					aria-label={copy.closeDetail}
					on:click={() => {
						showIconPicker = false;
						showDetailModal = false;
					}}
				>
					<XMark className="size-5" />
				</button>
			</div>
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
						{copy.preview}
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
						{copy.source}
					</button>
				</div>

				{#if detailMode === 'source'}
					<button
						type="button"
						class="inline-flex h-8 items-center justify-center rounded-lg bg-[#2f3a52] px-3 text-xs font-semibold text-white transition hover:bg-[#222b3f] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-gray-200 dark:text-gray-900 dark:hover:bg-white"
						disabled={savingDetail || detailLoading || !!detailError}
						on:click={saveSkillDetail}
					>
						{savingDetail ? copy.saving : copy.save}
					</button>
				{:else}
					<button
						type="button"
						class="inline-flex h-8 items-center justify-center rounded-lg border border-[#d8deea] bg-white px-3 text-xs font-semibold text-[#667289] transition hover:border-[#aeb9cc] hover:bg-[#f7f9fc] hover:text-[#293246] disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
						disabled={detailLoading || !!detailError}
						on:click={openSkillDirectory}
					>
						{copy.openDirectory}
					</button>
				{/if}
			</div>
		</div>

		<div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
			{#if detailLoading}
				<div
					class="flex h-full min-h-72 flex-col items-center justify-center gap-3 text-sm text-gray-500"
				>
					<Spinner className="size-5" />
					<div>{copy.detailLoading}</div>
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
						{copy.retry}
					</button>
				</div>
			{:else if detailMode === 'source'}
				<div
					class="expert-skill-source-shell grid h-full min-h-0 grid-cols-[3.5rem_minmax(0,1fr)] items-start overflow-auto rounded-xl border border-[#d8deea] bg-[#fbfcff] dark:border-gray-700 dark:bg-gray-950"
				>
					<div
						class="expert-skill-line-gutter min-h-full self-stretch border-r border-[#e4e9f2] bg-[#f3f6fb] py-4 pr-3 text-right font-mono text-[12px] leading-5 text-[#9aa4b5] dark:border-gray-800 dark:bg-gray-900 dark:text-gray-600"
						aria-hidden="true"
					>
						{#each sourceLineNumbers as lineNumber}
							<div>{lineNumber}</div>
						{/each}
					</div>
					<textarea
						bind:this={sourceEditor}
						class="expert-skill-source-editor min-h-full w-full resize-none overflow-hidden border-0 bg-transparent p-4 font-mono text-[12px] leading-5 text-[#293246] outline-none dark:text-gray-100"
						bind:value={detailSourceContent}
						rows={getLineCount(detailSourceContent)}
						spellcheck="false"
						on:input={() => {
							sourceDirty = true;
						}}
					></textarea>
				</div>
			{:else if detailMarkdownContent}
				<div
					class="expert-skill-preview-shell grid w-full max-w-none grid-cols-[3.5rem_minmax(0,1fr)] overflow-hidden rounded-xl border border-[#e4e9f2] bg-white dark:border-gray-800 dark:bg-gray-950"
				>
					<div
						class="expert-skill-line-gutter min-h-full self-stretch border-r border-[#e4e9f2] bg-[#f7f9fc] py-4 pr-3 text-right font-mono text-[12px] leading-5 text-[#a3adbd] dark:border-gray-800 dark:bg-gray-900 dark:text-gray-600"
						aria-hidden="true"
					>
						{#each previewLineNumbers as lineNumber}
							<div>{lineNumber}</div>
						{/each}
					</div>
					<div class="expert-skill-markdown min-w-0 px-4 py-4 text-[13px]">
						<Markdown
							id={`expert-skill-detail-${selectedSkillDetail?.name || selectedSkill?.skill_name}`}
							content={detailMarkdownContent}
							editCodeBlock={false}
						/>
					</div>
				</div>
			{:else}
				<div class="flex h-full min-h-72 items-center justify-center text-sm text-gray-500">
					{copy.detailEmpty}
				</div>
			{/if}
		</div>
	</div>
</Modal>

<style>
	.expert-agent-drawer {
		background: linear-gradient(
			180deg,
			rgba(255, 255, 255, 0.96) 0%,
			rgba(243, 249, 255, 0.86) 100%
		);
	}

	.expert-agent-card-list {
		scrollbar-width: thin;
		scrollbar-color: rgba(116, 155, 200, 0.42) transparent;
	}

	.expert-agent-card-list::-webkit-scrollbar {
		width: 8px;
	}

	.expert-agent-card-list::-webkit-scrollbar-track {
		background: transparent;
	}

	.expert-agent-card-list::-webkit-scrollbar-thumb {
		border: 2px solid transparent;
		border-radius: 999px;
		background: rgba(116, 155, 200, 0.42);
		background-clip: padding-box;
	}

	.expert-agent-filter-chip {
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.86);
	}

	:global(.dark) .expert-agent-drawer {
		background: linear-gradient(180deg, rgba(17, 24, 39, 0.96) 0%, rgba(17, 24, 39, 0.9) 100%);
	}

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
