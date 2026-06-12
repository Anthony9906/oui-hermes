<script lang="ts">
	import { aguiStore } from '../stores/agui';
	import StateRenderer from './StateRenderer.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import LucideIcon from '$lib/components/expert-agents/LucideIcon.svelte';

	const AGUI_PREVIEW_STORAGE_PREFIX = 'open-webui:agui-preview:';
	let previewLinkCopied = false;

	const createPreviewUrl = () => {
		const key = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
		window.localStorage.setItem(
			`${AGUI_PREVIEW_STORAGE_PREFIX}${key}`,
			JSON.stringify({
				artifact: $aguiStore.artifact,
				createdAt: Date.now()
			})
		);

		return `${window.location.origin}/agui-preview?key=${encodeURIComponent(key)}`;
	};

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

	const copyArtifactPreviewLink = async () => {
		if (!$aguiStore.artifact || typeof window === 'undefined') return;

		if (await writeClipboardText(createPreviewUrl())) {
			previewLinkCopied = true;
			setTimeout(() => {
				previewLinkCopied = false;
			}, 1600);
		}
	};

	const openArtifactInNewWindow = () => {
		if (!$aguiStore.artifact || typeof window === 'undefined') return;

		window.open(createPreviewUrl(), '_blank', 'noopener,noreferrer');
	};
</script>

<div class="agui-panel flex h-full flex-col bg-white dark:bg-gray-850">
	<div
		class="flex items-center justify-between border-b border-gray-100 px-4 py-2.5 dark:border-gray-800"
	>
		<span class="flex items-center gap-2 text-base font-semibold text-gray-700 dark:text-gray-200">
			<LucideIcon name="sparkles" className="size-6 text-blue-600" strokeWidth="1.45" />
			<span>AI 工作区</span>
		</span>
		<div class="flex items-center gap-2">
			{#if $aguiStore.artifact}
				<button
					type="button"
					class="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30 dark:hover:bg-gray-800 dark:hover:text-gray-100"
					aria-label={previewLinkCopied ? '已复制链接分享' : '复制链接分享'}
					title={previewLinkCopied ? '已复制链接分享' : '复制链接分享'}
					on:click={copyArtifactPreviewLink}
				>
					<LucideIcon
						name={previewLinkCopied ? 'check' : 'copy'}
						className="size-4"
						strokeWidth="1.8"
					/>
				</button>
				<button
					type="button"
					class="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30 dark:hover:bg-gray-800 dark:hover:text-gray-100"
					aria-label="在新窗口打开 AG-UI 预览"
					title="在新窗口打开"
					on:click={openArtifactInNewWindow}
				>
					<LucideIcon name="external-link" className="size-4" strokeWidth="1.8" />
				</button>
			{/if}
			<button
				type="button"
				class="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30 dark:hover:bg-gray-800 dark:hover:text-gray-100"
				aria-label="关闭 AI 工作区"
				on:click={() => aguiStore.hidePanel()}
			>
				<XMark className="size-4" />
			</button>
		</div>
	</div>

	<div class="min-h-0 flex-1 overflow-auto">
		{#if $aguiStore.artifact}
			<StateRenderer
				artifactType={$aguiStore.artifact.artifact_type}
				payload={$aguiStore.artifact.payload}
			/>
		{:else}
			<div class="flex h-full items-center justify-center px-8 text-center">
				<div class="text-sm text-gray-500 dark:text-gray-400">当前暂无制品预览</div>
			</div>
		{/if}
	</div>
</div>
