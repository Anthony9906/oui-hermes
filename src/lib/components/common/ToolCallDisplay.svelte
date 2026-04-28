<script lang="ts">
	import { decode } from 'html-entities';
	import { v4 as uuidv4 } from 'uuid';

	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';

	import ChevronUp from '../icons/ChevronUp.svelte';
	import ChevronDown from '../icons/ChevronDown.svelte';
	import Spinner from './Spinner.svelte';
	import Terminal from '../icons/Terminal.svelte';
	import Search from '../icons/Search.svelte';
	import GlobeAlt from '../icons/GlobeAlt.svelte';
	import Wrench from '../icons/Wrench.svelte';
	import Image from './Image.svelte';
	import FullHeightIframe from './FullHeightIframe.svelte';
	import { settings } from '$lib/stores';

	export let id: string = '';
	export let attributes: {
		type?: string;
		id?: string;
		name?: string;
		arguments?: string;
		result?: string;
		files?: string;
		embeds?: string;
		done?: string;
	} = {};

	export let open = false;
	export let grouped = false;
	export let className = '';

	const HEADER_PREVIEW_LIMIT = 128;
	const EXPANDED_RESULT_PREVIEW_LIMIT = 128;
	const TOOL_RESULT_PENDING_TEXT = '等待 Tool 返回信息';
	const EMPTY_PREVIEW_TEXTS = new Set(['{}', '[]', '""', 'null']);
	const GENERIC_TOOL_NAMES = new Set(['tool', 'tools', 'function', 'function_call', 'call']);
	const COMMAND_KEYS = ['command', 'cmd', 'shell', 'bash', 'terminal'];
	const SEARCH_KEYS = ['query', 'queries', 'pattern', 'search'];
	const URL_KEYS = ['url', 'urls', 'link', 'href'];
	const FILE_KEYS = ['path', 'file', 'filename', 'directory', 'cwd', 'working_directory'];
	const PREVIEW_KEYS = [
		'label',
		'description',
		'summary',
		'preview',
		'command',
		'cmd',
		'query',
		'pattern',
		'path',
		'file',
		'filename',
		'url',
		'cwd',
		'working_directory'
	];
	const EMOJI_KEYS = ['emoji'];
	const TOOL_NAME_KEYS = [
		'tool_name',
		'function_name',
		'skill_name',
		'command_name',
		'tool',
		'name'
	];

	export let buttonClassName =
		'w-fit text-gray-400 hover:text-gray-500 dark:text-gray-500 dark:hover:text-gray-400 transition';

	const componentId = id || uuidv4();

	function parseJSONString(str: string) {
		try {
			return parseJSONString(JSON.parse(str));
		} catch (e) {
			return str;
		}
	}

	function formatJSONString(str: string) {
		try {
			const parsed = parseJSONString(str);
			if (typeof parsed === 'object') {
				return JSON.stringify(parsed, null, 2);
			} else {
				return String(parsed);
			}
		} catch (e) {
			return str;
		}
	}

	function toDisplayText(value: unknown): string {
		if (value === null || value === undefined) {
			return '';
		}

		if (typeof value === 'string') {
			return value;
		}

		try {
			return JSON.stringify(value, null, 2);
		} catch {
			return String(value);
		}
	}

	function compactText(value: string): string {
		return value.replace(/\s+/g, ' ').trim();
	}

	function limitText(value: string, limit: number): string {
		return value.length > limit ? value.slice(0, limit) : value;
	}

	function isRecord(value: unknown): value is Record<string, unknown> {
		return typeof value === 'object' && value !== null && !Array.isArray(value);
	}

	function* walkValues(value: unknown): Generator<unknown> {
		yield value;
		if (Array.isArray(value)) {
			for (const item of value) {
				yield* walkValues(item);
			}
		} else if (isRecord(value)) {
			for (const item of Object.values(value)) {
				yield* walkValues(item);
			}
		}
	}

	function readValueByKeys(value: unknown, keys: string[]): unknown {
		const normalizedKeys = new Set(keys.map((key) => key.toLowerCase()));
		for (const item of walkValues(value)) {
			if (!isRecord(item)) {
				continue;
			}

			for (const [key, nestedValue] of Object.entries(item)) {
				if (
					normalizedKeys.has(key.toLowerCase()) &&
					nestedValue !== null &&
					nestedValue !== undefined
				) {
					return nestedValue;
				}
			}
		}

		return undefined;
	}

	function valueToPreview(value: unknown): string {
		if (value === null || value === undefined) {
			return '';
		}

		if (typeof value === 'string') {
			return compactText(value);
		}

		if (typeof value === 'number' || typeof value === 'boolean') {
			return String(value);
		}

		if (Array.isArray(value)) {
			return compactText(
				value
					.map((item) => valueToPreview(item))
					.filter(Boolean)
					.join(', ')
			);
		}

		return compactText(toDisplayText(value));
	}

	function hasAnyKey(value: unknown, keys: string[]): boolean {
		const normalizedKeys = new Set(keys.map((key) => key.toLowerCase()));
		for (const item of walkValues(value)) {
			if (!isRecord(item)) {
				continue;
			}
			if (Object.keys(item).some((key) => normalizedKeys.has(key.toLowerCase()))) {
				return true;
			}
		}
		return false;
	}

	function isGenericToolName(value: string): boolean {
		return !value || GENERIC_TOOL_NAMES.has(value.trim().toLowerCase());
	}

	function humanizeToolName(value: string): string {
		const name = value.trim();
		const normalized = name.toLowerCase();

		if (
			['bash', 'shell', 'terminal', 'command', 'exec', 'execute', 'run_command'].includes(
				normalized
			)
		) {
			return '执行命令';
		}
		if (['web_search', 'search', 'tavily_search', 'google_search'].includes(normalized)) {
			return '搜索';
		}
		if (['open_url', 'browser', 'web', 'fetch'].includes(normalized)) {
			return '访问网页';
		}
		if (['read_file', 'write_file', 'list_files', 'file'].includes(normalized)) {
			return '文件操作';
		}
		if (['skill_view', 'skill', 'load_skill'].includes(normalized)) {
			return '读取技能';
		}

		return name
			.replace(/[_-]+/g, ' ')
			.replace(/\b\w/g, (letter) => letter.toUpperCase())
			.trim();
	}

	function inferToolKind(rawName: string, parsedArgs: unknown, parsedResult: unknown): string {
		const name = rawName.toLowerCase();
		if (hasAnyKey(parsedArgs, COMMAND_KEYS) || /bash|shell|terminal|command|exec/.test(name)) {
			return 'command';
		}
		if (hasAnyKey(parsedArgs, SEARCH_KEYS) || /search/.test(name)) {
			return 'search';
		}
		if (hasAnyKey(parsedArgs, URL_KEYS) || /web|browser|url|fetch/.test(name)) {
			return 'web';
		}
		if (hasAnyKey(parsedArgs, FILE_KEYS) || /file|path|directory/.test(name)) {
			return 'file';
		}
		if (hasAnyKey(parsedArgs, TOOL_NAME_KEYS) || hasAnyKey(parsedResult, TOOL_NAME_KEYS)) {
			return 'tool';
		}
		return 'tool';
	}

	function getDisplayToolName(rawName: string, parsedArgs: unknown, parsedResult: unknown): string {
		const hermesToolName =
			valueToPreview(readValueByKeys(parsedArgs, ['tool'])) ||
			valueToPreview(readValueByKeys(parsedResult, ['tool']));
		if (hermesToolName && !isGenericToolName(hermesToolName)) {
			return hermesToolName;
		}

		const nestedName =
			valueToPreview(readValueByKeys(parsedArgs, TOOL_NAME_KEYS)) ||
			valueToPreview(readValueByKeys(parsedResult, TOOL_NAME_KEYS)) ||
			rawName;
		if (!isGenericToolName(nestedName)) {
			return humanizeToolName(nestedName);
		}

		const kind = inferToolKind(rawName, parsedArgs, parsedResult);
		if (kind === 'command') {
			return '执行命令';
		}
		if (kind === 'search') {
			return '搜索';
		}
		if (kind === 'web') {
			return '访问网页';
		}
		if (kind === 'file') {
			return '文件操作';
		}
		return '工具调用';
	}

	function stripLeadingToolName(preview: string, displayToolName: string): string {
		const normalizedName = displayToolName.trim();
		if (!preview || !normalizedName) {
			return preview;
		}

		const lowerPreview = preview.toLowerCase();
		const lowerName = normalizedName.toLowerCase();
		if (lowerPreview === lowerName) {
			return '';
		}
		if (lowerPreview.startsWith(`${lowerName} `)) {
			return preview.slice(normalizedName.length).trim();
		}
		if (lowerPreview.startsWith(`${lowerName}:`)) {
			return preview.slice(normalizedName.length + 1).trim();
		}
		return preview;
	}

	function getPreviewText(
		parsedArgs: unknown,
		parsedResult: unknown,
		argsText: string,
		resultText: string,
		displayToolName = ''
	): string {
		const previewValue =
			readValueByKeys(parsedArgs, PREVIEW_KEYS) ?? readValueByKeys(parsedResult, PREVIEW_KEYS);
		const preview = stripLeadingToolName(valueToPreview(previewValue), displayToolName);
		if (preview && preview !== '{}' && preview !== '[]') {
			return preview;
		}

		const fallback = compactText(argsText) || compactText(resultText);
		if (EMPTY_PREVIEW_TEXTS.has(fallback)) {
			return '';
		}
		return fallback;
	}

	$: args = decode(attributes?.arguments ?? '');
	export let resultContent: string = '';

	$: result = resultContent || decode(attributes?.result ?? '');
	$: files = parseJSONString(decode(attributes?.files ?? ''));
	$: embeds = parseJSONString(decode(attributes?.embeds ?? ''));
	$: isDone = attributes?.done === 'true';
	$: isExecuting = attributes?.done && attributes?.done !== 'true';

	$: parsedArgs = parseJSONString(args);
	$: parsedResult = parseJSONString(result);
	$: argsText = formatJSONString(args);
	$: resultText = toDisplayText(parsedResult);
	$: toolName = attributes?.name || attributes?.id || 'tool';
	$: toolKind = inferToolKind(toolName, parsedArgs, parsedResult);
	$: displayToolName = getDisplayToolName(toolName, parsedArgs, parsedResult);
	$: hermesEmoji =
		valueToPreview(readValueByKeys(parsedArgs, EMOJI_KEYS)) ||
		valueToPreview(readValueByKeys(parsedResult, EMOJI_KEYS));
	$: visibleArgsText = EMPTY_PREVIEW_TEXTS.has(compactText(argsText)) ? '' : argsText;
	$: visibleResultText = EMPTY_PREVIEW_TEXTS.has(compactText(resultText)) ? '' : resultText;
	$: previewText = limitText(
		getPreviewText(parsedArgs, parsedResult, visibleArgsText, visibleResultText, displayToolName),
		HEADER_PREVIEW_LIMIT
	);
	$: expandedDetailText = limitText(
		compactText(visibleResultText) || TOOL_RESULT_PENDING_TEXT,
		EXPANDED_RESULT_PREVIEW_LIMIT
	);
</script>

<div {id} class={className}>
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div
		class="{buttonClassName} cursor-pointer hermes-tool-call"
		on:pointerup={() => {
			open = !open;
		}}
	>
		<div class="w-full max-w-full flex items-center gap-1.5 {isExecuting ? 'shimmer' : ''}">
			{#if isExecuting}
				<div class="hermes-tool-call-icon">
					<Spinner className="size-4" />
				</div>
			{:else if hermesEmoji}
				<div class="hermes-tool-call-icon hermes-tool-call-emoji">
					{hermesEmoji}
				</div>
			{:else if toolKind === 'command'}
				<div class="hermes-tool-call-icon">
					<Terminal className="size-4" strokeWidth="1.8" />
				</div>
			{:else if toolKind === 'search'}
				<div class="hermes-tool-call-icon">
					<Search className="size-4" strokeWidth="1.8" />
				</div>
			{:else if toolKind === 'web'}
				<div class="hermes-tool-call-icon">
					<GlobeAlt className="size-4" strokeWidth="1.8" />
				</div>
			{:else}
				<div class="hermes-tool-call-icon">
					<Wrench className="size-4" strokeWidth="1.8" />
				</div>
			{/if}

			<div class="flex-1 min-w-0 line-clamp-1 text-xs font-normal hermes-tool-call-label">
				<span class="font-semibold hermes-tool-call-name">{displayToolName}</span>
				{#if previewText}
					<span class="hermes-tool-call-preview"> {previewText}</span>
				{/if}
			</div>

			<div class="flex shrink-0 self-center translate-y-[1px] hermes-tool-call-icon">
				{#if open}
					<ChevronUp strokeWidth="3.5" className="size-3.5" />
				{:else}
					<ChevronDown strokeWidth="3.5" className="size-3.5" />
				{/if}
			</div>
		</div>
	</div>

	{#if open}
		<div transition:slide={{ duration: 300, easing: quintOut, axis: 'y' }}>
			<div class="hermes-tool-call-panel my-1.5 rounded-lg border p-2.5">
				<pre
					class="hermes-tool-call-detail max-h-40 overflow-hidden whitespace-pre-wrap break-words font-mono text-xs">{expandedDetailText}</pre>

				{#if !grouped && embeds && Array.isArray(embeds) && embeds.length > 0}
					{#each embeds as embed, idx}
						<div class="my-2" id={`${componentId}-tool-call-embed-${idx}`}>
							<FullHeightIframe
								src={embed}
								{args}
								allowScripts={true}
								allowForms={$settings?.iframeSandboxAllowForms ?? false}
								allowSameOrigin={$settings?.iframeSandboxAllowSameOrigin ?? false}
								allowPopups={true}
							/>
						</div>
					{/each}
				{/if}
			</div>
		</div>
	{/if}

	<!-- Files display (images etc.) when done -->
	{#if open && isDone}
		{#if typeof files === 'object'}
			{#each files ?? [] as file, idx}
				{#if typeof file === 'string'}
					{#if file.startsWith('data:image/')}
						<Image id={`${componentId}-tool-call-result-${idx}`} src={file} alt="Image" />
					{/if}
				{:else if typeof file === 'object'}
					{#if (file.type === 'image' || (file?.content_type ?? '').startsWith('image/')) && file.url}
						<Image id={`${componentId}-tool-call-result-${idx}`} src={file.url} alt="Image" />
					{/if}
				{/if}
			{/each}
		{/if}
	{/if}
</div>

<style>
	.hermes-tool-call-panel {
		background: transparent;
		border-color: rgba(164, 174, 194, 0.22);
	}

	:global(.light .chat-assistant .hermes-tool-call),
	:global(.light .chat-assistant .hermes-tool-call *),
	:global(.light .chat-assistant .hermes-tool-call-panel),
	:global(.light .chat-assistant .hermes-tool-call-panel *) {
		color: #828ca3 !important;
		margin:4px 0;
		font-size: 14px;
	}

	:global(.dark .hermes-tool-call),
	:global(.dark .hermes-tool-call *),
	:global(.dark .hermes-tool-call-panel),
	:global(.dark .hermes-tool-call-panel *) {
		color: rgb(156 163 175) !important;
	}

	:global(.dark) .hermes-tool-call-panel {
		border-color: rgba(75, 85, 99, 0.28);
	}

	:global(.light .chat-assistant .hermes-tool-call-name) {
		color: #3f4658 !important;
	}

	:global(.dark .hermes-tool-call-name) {
		color: rgb(209 213 219) !important;
	}

	.hermes-tool-call-preview {
		opacity: 0.82;
	}

	.hermes-tool-call-emoji {
		width: 1rem;
		font-size: 0.875rem;
		line-height: 1rem;
		text-align: center;
	}
</style>
