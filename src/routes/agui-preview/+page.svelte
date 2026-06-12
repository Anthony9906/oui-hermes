<script lang="ts">
	import { onMount } from 'svelte';
	import StateRenderer from '$lib/agui/components/StateRenderer.svelte';
	import LucideIcon from '$lib/components/expert-agents/LucideIcon.svelte';

	const AGUI_PREVIEW_STORAGE_PREFIX = 'open-webui:agui-preview:';

	let artifact: { artifact_type: string; payload: any } | null = null;
	let error = '';
	let copied = false;

	const writeClipboardText = async (text: string) => {
		try {
			await navigator.clipboard.writeText(text);
			return true;
		} catch {
			const textarea = document.createElement('textarea');
			textarea.value = text;
			textarea.setAttribute('readonly', '');
			textarea.style.position = 'fixed';
			textarea.style.left = '-9999px';
			document.body.appendChild(textarea);
			textarea.select();
			const ok = document.execCommand('copy');
			document.body.removeChild(textarea);
			return ok;
		}
	};

	onMount(() => {
		const key = new URLSearchParams(window.location.search).get('key');
		if (!key) {
			error = '未找到 AG-UI 预览数据。';
			return;
		}

		const raw = window.localStorage.getItem(`${AGUI_PREVIEW_STORAGE_PREFIX}${key}`);
		if (!raw) {
			error = 'AG-UI 预览数据已过期，请回到会话重新打开。';
			return;
		}

		try {
			const parsed = JSON.parse(raw);
			artifact = parsed?.artifact || null;
			if (!artifact?.artifact_type) {
				error = 'AG-UI 预览数据格式无效。';
			}
		} catch {
			error = 'AG-UI 预览数据读取失败。';
		}
	});

	const copyLink = async () => {
		if (typeof window === 'undefined') return;

		if (await writeClipboardText(window.location.href)) {
			copied = true;
			setTimeout(() => {
				copied = false;
			}, 1600);
		}
	};
</script>

<svelte:head>
	<title>AG-UI Preview</title>
</svelte:head>

<div class="flex h-screen flex-col overflow-hidden bg-[#F8FAFC]">
	<header class="border-b border-gray-200 bg-white px-5 py-2.5">
		<div class="mx-auto flex max-w-[980px] items-center justify-between gap-3">
			<div class="text-xs font-medium text-gray-500">Expert Agent - Artifact Preview</div>
			<div class="flex items-center gap-2">
				{#if copied}
					<span class="text-xs font-semibold text-emerald-600">已复制链接</span>
				{/if}
				<button
					type="button"
					class="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-600 transition hover:bg-gray-50 hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
					on:click={copyLink}
				>
					<LucideIcon name="copy" className="size-3.5" strokeWidth="1.8" />
					复制链接
				</button>
			</div>
		</div>
	</header>

	<main class="min-h-0 flex-1 overflow-y-auto">
		<div class="mx-auto w-full max-w-[980px]">
			{#if artifact}
				<StateRenderer artifactType={artifact.artifact_type} payload={artifact.payload} />
			{:else}
				<div class="p-6 text-sm text-gray-500">
					{error || '正在加载 AG-UI 预览...'}
				</div>
			{/if}
		</div>
	</main>
</div>
