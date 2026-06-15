<script lang="ts">
	export let payload: any;

	$: data = payload && typeof payload === 'object' ? payload : {};
	$: title = data.title || '';
	$: rawContent = typeof data.content === 'string' ? data.content : '';
</script>

<div class="min-h-full bg-gray-50 dark:bg-gray-900">
	{#if title}
		<div class="px-5 pb-2 pt-5">
			<h2 class="text-lg font-bold text-gray-900 dark:text-gray-100">{title}</h2>
		</div>
	{/if}
	<div class="px-5 pb-5">
		<div
			class="overflow-hidden rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-850"
		>
			{#if rawContent}
				<div class="html-preview-content text-gray-800 dark:text-gray-100">
					{@html rawContent}
				</div>
			{:else}
				<p class="text-sm text-gray-400">暂无内容</p>
			{/if}
		</div>
	</div>
</div>

<style>
	.html-preview-content :global(table) {
		width: 100%;
		border-collapse: collapse;
		margin: 12px 0;
	}
	.html-preview-content :global(th),
	.html-preview-content :global(td) {
		padding: 10px 12px;
		text-align: left;
		border-bottom: 1px solid #e2e8f0;
	}
	.html-preview-content :global(th) {
		background: #f1f5f9;
		font-weight: 600;
		color: #475569;
		font-size: 12px;
		text-transform: uppercase;
	}
	.html-preview-content :global(h1),
	.html-preview-content :global(h2),
	.html-preview-content :global(h3) {
		margin: 16px 0 8px;
		font-weight: 700;
	}
	.html-preview-content :global(a) {
		color: #2563eb;
	}
	.html-preview-content :global(pre) {
		background: #0f172a;
		color: #e2e8f0;
		padding: 12px;
		border-radius: 8px;
		overflow-x: auto;
		margin: 12px 0;
	}
	.html-preview-content :global(img) {
		max-width: 100%;
	}
</style>
