<script lang="ts">
	import { aguiStore } from '../stores/agui';
	import StateRenderer from './StateRenderer.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import LucideIcon from '$lib/components/expert-agents/LucideIcon.svelte';
</script>

<div class="flex h-full flex-col bg-white dark:bg-gray-850">
	<div
		class="flex items-center justify-between border-b border-gray-100 px-4 py-2.5 dark:border-gray-800"
	>
		<span
			class="flex min-w-0 items-center gap-2 text-base font-semibold text-gray-700 dark:text-gray-200"
		>
			<LucideIcon name="sparkles" className="size-5 text-blue-600" strokeWidth="1.6" />
			<span class="truncate">AI 工作区</span>
		</span>
		<button
			type="button"
			class="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30 dark:hover:bg-gray-800 dark:hover:text-gray-100"
			aria-label="关闭 AI 工作区"
			on:click={() => aguiStore.hidePanel()}
		>
			<XMark className="size-4" />
		</button>
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
