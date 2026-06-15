<script lang="ts">
	import { marked } from 'marked';

	export let payload: any;

	$: data = payload && typeof payload === 'object' ? payload : {};
	$: title = data.title || '';
	$: rawContent = typeof data.content === 'string' ? data.content : '';
	$: html = rawContent ? marked.parse(rawContent) : '';
</script>

<div class="min-h-full bg-gray-50 dark:bg-gray-900">
	{#if title}
		<div class="px-5 pb-2 pt-5">
			<h2 class="text-lg font-bold text-gray-900 dark:text-gray-100">{title}</h2>
		</div>
	{/if}
	<div class="px-5 pb-5">
		<div
			class="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-850"
		>
			{#if html}
				<div class="prose prose-sm max-w-none text-gray-800 dark:prose-invert dark:text-gray-100">
					{@html html}
				</div>
			{:else}
				<p class="text-sm text-gray-400">暂无内容</p>
			{/if}
		</div>
	</div>
</div>
