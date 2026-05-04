<script lang="ts">
	import { decode } from 'html-entities';

	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import Spinner from './Spinner.svelte';
	import Terminal from '../icons/Terminal.svelte';
	import Search from '../icons/Search.svelte';
	import GlobeAlt from '../icons/GlobeAlt.svelte';
	import Wrench from '../icons/Wrench.svelte';
	import CheckCircle from '../icons/CheckCircle.svelte';
	import XMark from '../icons/XMark.svelte';

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
	type TodoStatus = 'completed' | 'in_progress' | 'pending' | 'cancelled';
	type TodoItem = {
		id?: string;
		content: string;
		status: TodoStatus;
	};

	export let buttonClassName =
		'w-fit text-gray-400 hover:text-gray-500 dark:text-gray-500 dark:hover:text-gray-400 transition';

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

	function normalizeTodoStatus(value: unknown): TodoStatus {
		const status = String(value ?? 'pending')
			.trim()
			.toLowerCase()
			.replace(/[-\s]+/g, '_');

		if (['completed', 'complete', 'done', 'finished', 'success'].includes(status)) {
			return 'completed';
		}
		if (['in_progress', 'progress', 'running', 'active', 'working'].includes(status)) {
			return 'in_progress';
		}
		if (['cancelled', 'canceled', 'cancel', 'aborted'].includes(status)) {
			return 'cancelled';
		}
		return 'pending';
	}

	function findTodos(value: unknown): unknown[] | undefined {
		for (const item of walkValues(value)) {
			if (isRecord(item) && Array.isArray(item.todos)) {
				return item.todos;
			}
		}
		return undefined;
	}

	function getTodoItems(value: unknown): TodoItem[] {
		const todos = findTodos(value);
		if (!todos) {
			return [];
		}

		return todos
			.map((item) => {
				if (!isRecord(item)) {
					return null;
				}

				const content = compactText(
					valueToPreview(item.content ?? item.title ?? item.task ?? item.id)
				);
				if (!content) {
					return null;
				}

				return {
					id: valueToPreview(item.id),
					content,
					status: normalizeTodoStatus(item.status)
				};
			})
			.filter(Boolean) as TodoItem[];
	}

	function getTodoSummaryText(value: unknown): string {
		const summary = readValueByKeys(value, ['summary']);
		if (!isRecord(summary)) {
			const todos = getTodoItems(value);
			if (todos.length === 0) {
				return '';
			}
			return `Agent 正在分步完成任务：${todos.filter((todo) => todo.status === 'completed').length} / ${todos.length}`;
		}

		const total = Number(summary.total ?? 0);
		const completed = Number(summary.completed ?? 0);
		if (!Number.isFinite(total) || total <= 0) {
			return '';
		}

		return `Agent 正在分步完成任务：${Number.isFinite(completed) ? completed : 0} / ${todos.length}`;
	}

	function isTodoTool(rawName: string, parsedArgs: unknown, parsedResult: unknown): boolean {
		const names = [
			rawName,
			valueToPreview(readValueByKeys(parsedArgs, ['tool', 'name', 'function_name'])),
			valueToPreview(readValueByKeys(parsedResult, ['tool', 'name', 'function_name']))
		];

		return names.some((name) => name.trim().toLowerCase() === 'todo');
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
	$: todoItems = isTodoTool(toolName, parsedArgs, parsedResult)
		? getTodoItems(parsedResult).length > 0
			? getTodoItems(parsedResult)
			: getTodoItems(parsedArgs)
		: [];
	$: todoSummaryText = isTodoTool(toolName, parsedArgs, parsedResult)
		? getTodoSummaryText(parsedResult) || getTodoSummaryText(parsedArgs)
		: '';
	$: previewText = limitText(
		todoSummaryText ||
			getPreviewText(parsedArgs, parsedResult, visibleArgsText, visibleResultText, displayToolName),
		HEADER_PREVIEW_LIMIT
	);
</script>

<div {id} class={className}>
	<div class="{buttonClassName} hermes-tool-call">
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
		</div>
	</div>

	{#if todoItems.length > 0}
		<ul class="hermes-tool-todos" aria-label="Todo tasks">
			{#each todoItems as todo}
				<li class="hermes-tool-todo hermes-tool-todo-{todo.status}">
					<span class="hermes-tool-todo-icon" aria-hidden="true">
						{#if todo.status === 'completed'}
							<CheckCircle className="size-4" strokeWidth="2" />
						{:else if todo.status === 'in_progress'}
							<span class="hermes-tool-todo-dot"></span>
						{:else if todo.status === 'cancelled'}
							<XMark className="size-3.5" />
						{:else}
							<span class="hermes-tool-todo-ring"></span>
						{/if}
					</span>
					<span class="hermes-tool-todo-content">{todo.content}</span>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	:global(.light .chat-assistant .hermes-tool-call),
	:global(.light .chat-assistant .hermes-tool-call *) {
		color: #828ca3 !important;
		margin: 6px 0;
		font-size: 16px;
	}

	:global(.dark .hermes-tool-call),
	:global(.dark .hermes-tool-call *) {
		color: rgb(156 163 175) !important;
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

	.hermes-tool-todos {
		margin: 2px 0 8px 1.55rem;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
		list-style: none;
	}

	.hermes-tool-todo {
		display: grid;
		grid-template-columns: 1rem minmax(0, 1fr);
		align-items: start;
		gap: 0.45rem;
		max-width: 100%;
		font-size: 13px;
		line-height: 1.45;
	}

	.hermes-tool-todo-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1rem;
		height: 1.25rem;
		flex: none;
	}

	.hermes-tool-todo-dot,
	.hermes-tool-todo-ring {
		display: block;
		width: 0.55rem;
		height: 0.55rem;
		border-radius: 9999px;
	}

	.hermes-tool-todo-dot {
		background: currentColor;
		box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 18%, transparent);
	}

	.hermes-tool-todo-ring {
		border: 1.5px solid currentColor;
	}

	.hermes-tool-todo-content {
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.hermes-tool-todo-completed .hermes-tool-todo-icon {
		color: #50ac45 !important;
	}

	.hermes-tool-todo-completed .hermes-tool-todo-icon :global(svg) {
		color: #50ac45 !important;
		stroke: #50ac45 !important;
	}

	.hermes-tool-todo-completed .hermes-tool-todo-content {
		color: #bbc0cc !important;
	}

	.hermes-tool-todo-in_progress .hermes-tool-todo-dot {
		color: rgb(139, 148, 193) !important;
	}

	.hermes-tool-todo-pending .hermes-tool-todo-content {
		color: #bbc0cc !important;
	}

	.hermes-tool-todo-cancelled .hermes-tool-todo-content {
		text-decoration: line-through;
		color: #bbc0cc !important;
	}
</style>
