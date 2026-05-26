<script lang="ts">
	import hljs from 'highlight.js';
	import { toast } from 'svelte-sonner';
	import { getContext, onMount, tick } from 'svelte';
	import { config } from '$lib/stores';
	import { getArtifactTitle as getRemoteArtifactTitle } from '$lib/apis/utils';

	import {
		copyToClipboard,
		initMermaid,
		renderMermaidDiagram,
		renderVegaVisualization,
		unescapeHtml
	} from '$lib/utils';

	import 'highlight.js/styles/github-dark.min.css';
	import equal from 'fast-deep-equal';

	import CodeEditor from '$lib/components/common/CodeEditor.svelte';
	import SvgPanZoom from '$lib/components/common/SVGPanZoom.svelte';

	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import ChevronUpDown from '$lib/components/icons/ChevronUpDown.svelte';
	import CommandLine from '$lib/components/icons/CommandLine.svelte';
	import Cube from '$lib/components/icons/Cube.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	const i18n = getContext('i18n');

	export let id = '';
	export let edit = true;

	export let onSave = (e) => {};
	export let onUpdate = (e) => {};
	export let onPreview = (e) => {};

	export let save = false;
	export let run = true;
	export let preview = false;
	export let collapsed = false;

	export let token;
	export let lang = '';
	export let code = '';
	export let attributes = {};

	export let className = '';
	export let editorClassName = '';
	export let stickyButtonsClassName = 'top-0';

	let _code = '';
	$: if (code) {
		updateCode();
	}

	const updateCode = () => {
		_code = code;
	};

	let _token = null;

	let renderHTML = null;
	let renderError = null;

	let highlightedCode = null;
	let executing = false;

	let stdout = null;
	let stderr = null;
	let result = null;
	let files = null;

	let copied = false;
	let saved = false;

	const collapseCodeBlock = () => {
		collapsed = !collapsed;
	};

	const saveCode = () => {
		saved = true;

		code = _code;
		onSave(code);

		setTimeout(() => {
			saved = false;
		}, 1000);
	};

	const copyCode = async () => {
		copied = true;
		await copyToClipboard(_code);

		setTimeout(() => {
			copied = false;
		}, 1000);
	};

	const previewCode = () => {
		onPreview(code);
	};

	const decodeEntityText = (value = '') =>
		value
			.replace(/&quot;/g, '"')
			.replace(/&#39;/g, "'")
			.replace(/&apos;/g, "'")
			.replace(/&amp;/g, '&')
			.replace(/&lt;/g, '<')
			.replace(/&gt;/g, '>');

	const getHtmlAttribute = (tag = '', name = '') => {
		const match = tag.match(new RegExp(`${name}\\s*=\\s*("([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i'));
		return decodeEntityText(match?.[2] ?? match?.[3] ?? match?.[4] ?? '').trim();
	};

	const getArtifactIframeTag = (value = '') => value.match(/<iframe\b[^>]*>/i)?.[0] ?? '';

	const getArtifactIframeSrc = (value = '') => getHtmlAttribute(getArtifactIframeTag(value), 'src');

	const isArtifactIframe = (value = '', language = '') => {
		const normalizedLang = language.toLowerCase();
		if (normalizedLang !== 'html') return false;

		const src = getArtifactIframeSrc(value);
		if (!src) return false;

		return /(^|\/)v\/[^/?#"' ]+|\/api\/artifacts\//i.test(src);
	};

	const getArtifactTitleFromHtml = (value = '') => {
		const iframeTag = getArtifactIframeTag(value);
		const iframeTitle =
			getHtmlAttribute(iframeTag, 'title') || getHtmlAttribute(iframeTag, 'aria-label');
		const titleMatch = value.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
		const h1Match = value.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i);
		const src = getArtifactIframeSrc(value);
		const idMatch = src.match(/\/v\/([^/?#]+)/i) || src.match(/\/api\/artifacts\/([^/?#]+)/i);

		const candidates = [
			iframeTitle,
			titleMatch?.[1],
			h1Match?.[1]?.replace(/<[^>]+>/g, ' '),
			idMatch?.[1]
		]
			.map((item) =>
				decodeEntityText(
					String(item ?? '')
						.replace(/\s+/g, ' ')
						.trim()
				)
			)
			.filter(Boolean)
			.filter((item) => !/^(content|iframe|html|artifact)$/i.test(item));

		return candidates[0] || 'HTML Artifact';
	};

	$: showArtifactIframeCard = preview && isArtifactIframe(code, lang);
	let remoteArtifactTitle = '';
	let remoteArtifactTitleKey = '';
	let loadingArtifactTitleKey = '';

	const resolveArtifactTitle = async (value = '') => {
		const src = getArtifactIframeSrc(value);
		if (typeof localStorage === 'undefined') return;
		if (!localStorage.token) return;
		if (!src || remoteArtifactTitleKey === value || loadingArtifactTitleKey === value) return;

		loadingArtifactTitleKey = value;
		try {
			const title = await getRemoteArtifactTitle(localStorage.token, src);
			if (loadingArtifactTitleKey === value) {
				remoteArtifactTitle = title;
				remoteArtifactTitleKey = value;
			}
		} catch {
			if (loadingArtifactTitleKey === value) {
				remoteArtifactTitle = '';
				remoteArtifactTitleKey = value;
			}
		} finally {
			if (loadingArtifactTitleKey === value) {
				loadingArtifactTitleKey = '';
			}
		}
	};

	$: localArtifactTitle = getArtifactTitleFromHtml(code);
	$: artifactTitle =
		remoteArtifactTitleKey === code && remoteArtifactTitle
			? remoteArtifactTitle
			: localArtifactTitle;
	$: if (showArtifactIframeCard && code) {
		void resolveArtifactTitle(code);
	}

	const checkPythonCode = (str) => {
		// Check if the string contains typical Python syntax characters
		const pythonSyntax = [
			'def ',
			'else:',
			'elif ',
			'try:',
			'except:',
			'finally:',
			'yield ',
			'lambda ',
			'assert ',
			'nonlocal ',
			'del ',
			'True',
			'False',
			'None',
			' and ',
			' or ',
			' not ',
			' in ',
			' is ',
			' with '
		];

		for (let syntax of pythonSyntax) {
			if (str.includes(syntax)) {
				return true;
			}
		}

		// If none of the above conditions met, it's probably not Python code
		return false;
	};

	const executePython = async (_code) => {
		result = null;
		stdout = null;
		stderr = 'Browser Python execution is disabled for Hermes.';
		executing = false;
	};

	let mermaid = null;
	const renderMermaid = async (code) => {
		if (!mermaid) {
			mermaid = await initMermaid();
		}
		return await renderMermaidDiagram(mermaid, code);
	};

	const render = async () => {
		onUpdate(token);
		if (lang === 'mermaid' && (token?.raw ?? '').slice(-4).includes('```')) {
			try {
				renderHTML = await renderMermaid(code);
			} catch (error) {
				console.error('Failed to render mermaid diagram:', error);
				const errorMsg = error instanceof Error ? error.message : String(error);
				renderError = $i18n.t('Failed to render diagram') + `: ${errorMsg}`;
				renderHTML = null;
			}
		} else if (
			(lang === 'vega' || lang === 'vega-lite') &&
			(token?.raw ?? '').slice(-4).includes('```')
		) {
			try {
				renderHTML = await renderVegaVisualization(code);
			} catch (error) {
				console.error('Failed to render Vega visualization:', error);
				const errorMsg = error instanceof Error ? error.message : String(error);
				renderError = $i18n.t('Failed to render visualization') + `: ${errorMsg}`;
				renderHTML = null;
			}
		}
	};

	$: if (token) {
		if (token.text !== _token?.text || token.raw !== _token?.raw) {
			_token = token;
		} else if (!equal(token, _token)) {
			_token = token;
		}
	}

	$: if (_token) {
		render();
	}

	$: if (attributes) {
		onAttributesUpdate();
	}

	const onAttributesUpdate = () => {
		if (attributes?.output) {
			try {
				const output = JSON.parse(unescapeHtml(attributes.output));
				stdout = output.stdout;
				stderr = output.stderr;
				result = output.result;
			} catch (error) {
				console.error('Error:', error);
			}
		}
	};

	onMount(async () => {
		if (token) {
			onUpdate(token);
		}
	});
</script>

<div>
	<div
		class="relative {className} flex flex-col rounded-2xl border border-gray-100/30 dark:border-gray-850/30 my-0.5"
		dir="ltr"
	>
		{#if showArtifactIframeCard}
			<button
				type="button"
				class="group flex w-full items-center gap-3 rounded-2xl border border-[#b8cde8]/80 bg-white px-4 py-3 text-left shadow-xs transition hover:border-[#7fb2e5] hover:bg-[#f7fbff] dark:border-gray-800 dark:bg-gray-900 dark:hover:bg-gray-850"
				on:click={previewCode}
				aria-label={$i18n.t('Preview')}
			>
				<div
					class="flex size-12 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-[#dcecff] to-[#f7fbff] text-[#001f5b] ring-1 ring-[#cfe0f3] dark:from-gray-800 dark:to-gray-900 dark:text-gray-100 dark:ring-gray-700"
				>
					<Cube className="size-5" />
				</div>
				<div class="min-w-0 flex-1">
					<div class="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
						{artifactTitle}
					</div>
					<div class="mt-1 text-xs font-medium text-gray-500 dark:text-gray-400">HTML Artifact</div>
				</div>
				<div
					class="shrink-0 text-lg leading-none text-gray-400 transition group-hover:translate-x-0.5 group-hover:text-[#001f5b] dark:group-hover:text-gray-100"
				>
					&gt;
				</div>
			</button>
		{:else if ['mermaid', 'vega', 'vega-lite'].includes(lang)}
			{#if renderHTML}
				<SvgPanZoom
					className=" rounded-2xl max-h-fit overflow-hidden"
					svg={renderHTML}
					content={_token.text}
				/>
			{:else}
				<div class="p-3">
					{#if renderError}
						<div
							class="flex gap-2.5 border px-4 py-3 border-red-600/10 bg-red-600/10 rounded-2xl mb-2"
						>
							{renderError}
						</div>
					{/if}
					<pre>{code}</pre>
				</div>
			{/if}
		{:else}
			<div
				class="sticky {stickyButtonsClassName} left-0 right-0 py-1.5 px-3.5 gap-2 flex items-center justify-end w-full z-10 text-xs text-black dark:text-white bg-white dark:bg-black rounded-t-2xl"
			>
				<div class="flex-1 truncate">
					<Tooltip content={lang} placement="top-start">
						<span class=" truncate text-ellipsis">
							{lang}
						</span>
					</Tooltip>
				</div>

				<div class="flex items-center gap-0.5 shrink-0">
					<button
						class="flex gap-1 items-center bg-none border-none transition rounded-md px-1.5 py-0.5 bg-white dark:bg-black"
						on:click={collapseCodeBlock}
					>
						<div class=" -translate-y-[0.5px]">
							<ChevronUpDown className="size-3" />
						</div>

						<div>
							{collapsed ? $i18n.t('Expand') : $i18n.t('Collapse')}
						</div>
					</button>

					{#if ($config?.features?.enable_code_execution ?? true) && (lang.toLowerCase() === 'python' || lang.toLowerCase() === 'py' || (lang === '' && checkPythonCode(code)))}
						{#if executing}
							<div
								class="run-code-button bg-none border-none p-0.5 cursor-not-allowed bg-white dark:bg-black"
							>
								{$i18n.t('Running')}
							</div>
						{:else if run}
							<button
								class="flex gap-1 items-center run-code-button bg-none border-none transition rounded-md px-1.5 py-0.5 bg-white dark:bg-black"
								on:click={async () => {
									code = _code;
									await tick();
									executePython(code);
								}}
							>
								<div>
									{$i18n.t('Run')}
								</div>
							</button>
						{/if}
					{/if}

					{#if save}
						<button
							class="save-code-button bg-none border-none transition rounded-md px-1.5 py-0.5 bg-white dark:bg-black"
							on:click={saveCode}
						>
							{saved ? $i18n.t('Saved') : $i18n.t('Save')}
						</button>
					{/if}

					<button
						class="copy-code-button bg-none border-none transition rounded-md px-1.5 py-0.5 bg-white dark:bg-black"
						on:click={copyCode}>{copied ? $i18n.t('Copied') : $i18n.t('Copy')}</button
					>

					{#if preview && ['html', 'svg'].includes(lang)}
						<button
							class="flex gap-1 items-center run-code-button bg-none border-none transition rounded-md px-1.5 py-0.5 bg-white dark:bg-black"
							on:click={previewCode}
						>
							<div>
								{$i18n.t('Preview')}
							</div>
						</button>
					{/if}
				</div>
			</div>

			<div
				class="language-{lang} rounded-t-2xl -mt-8 {editorClassName
					? editorClassName
					: executing || stdout || stderr || result
						? ''
						: 'rounded-b-2xl'} overflow-hidden"
			>
				<div class=" pt-6.5 bg-white dark:bg-black"></div>

				{#if !collapsed}
					{#if edit}
						<CodeEditor
							value={code}
							{id}
							{lang}
							onSave={() => {
								saveCode();
							}}
							onChange={(value) => {
								_code = value;
							}}
						/>
					{:else}
						<pre
							class=" hljs p-4 px-5 overflow-x-auto"
							style="border-top-left-radius: 0px; border-top-right-radius: 0px; {(executing ||
								stdout ||
								stderr ||
								result) &&
								'border-bottom-left-radius: 0px; border-bottom-right-radius: 0px;'}"><code
								class="language-{lang} rounded-t-none whitespace-pre text-sm"
								>{@html hljs.highlightAuto(code, hljs.getLanguage(lang)?.aliases).value ||
									code}</code
							></pre>
					{/if}
				{:else}
					<div
						class="bg-white dark:bg-black dark:text-white rounded-b-2xl! pt-1 pb-2 px-4 flex flex-col gap-2 text-xs"
					>
						<span class="text-gray-500 italic">
							{$i18n.t('{{COUNT}} hidden lines', {
								COUNT: code.split('\n').length
							})}
						</span>
					</div>
				{/if}
			</div>

			{#if !collapsed}
				<div
					id="plt-canvas-{id}"
					class="bg-gray-50 dark:bg-black dark:text-white max-w-full overflow-x-auto scrollbar-hidden"
				></div>

				{#if executing || stdout || stderr || result || files}
					<div
						class="bg-gray-50 dark:bg-black dark:text-white rounded-b-2xl! pt-2 pb-3 px-3.5 flex flex-col gap-2"
					>
						{#if executing}
							<div class=" ">
								<div class=" text-gray-500 text-xs mb-1">{$i18n.t('STDOUT/STDERR')}</div>
								<div class="text-sm">{$i18n.t('Running...')}</div>
							</div>
						{:else}
							{#if stdout || stderr}
								<div class=" ">
									<div class=" text-gray-500 text-xs mb-1">{$i18n.t('STDOUT/STDERR')}</div>
									<div
										class="text-sm font-mono whitespace-pre-wrap {stdout?.split('\n')?.length > 100
											? `max-h-96`
											: ''}  overflow-y-auto"
									>
										{stdout || stderr}
									</div>
								</div>
							{/if}
							{#if result || files}
								<div class=" ">
									<div class=" text-gray-500 text-xs mb-1">{$i18n.t('RESULT')}</div>
									{#if result}
										<div class="text-sm">{`${JSON.stringify(result)}`}</div>
									{/if}
									{#if files}
										<div class="flex flex-col gap-2">
											{#each files as file}
												{#if file.type.startsWith('image')}
													<img src={file.data} alt="Output" class=" w-full max-w-[36rem]" />
												{/if}
											{/each}
										</div>
									{/if}
								</div>
							{/if}
						{/if}
					</div>
				{/if}
			{/if}
		{/if}
	</div>
</div>
