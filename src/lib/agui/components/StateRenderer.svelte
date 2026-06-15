<script lang="ts">
	import GenericPreviewRenderer from './renderers/GenericPreviewRenderer.svelte';
	import HtmlPreviewRenderer from './renderers/HtmlPreviewRenderer.svelte';
	import MarkdownPreviewRenderer from './renderers/MarkdownPreviewRenderer.svelte';

	export let artifactType: string;
	export let payload: any;

	const renderers: Record<string, any> = {
		'generic-preview': GenericPreviewRenderer,
		'generic-json': GenericPreviewRenderer,
		'html-preview': HtmlPreviewRenderer,
		'markdown-preview': MarkdownPreviewRenderer
	};

	$: Renderer = renderers[artifactType] || null;
</script>

{#if Renderer}
	<svelte:component this={Renderer} {payload} />
{:else}
	<div class="p-4 text-sm text-gray-500">不支持的制品类型: {artifactType}</div>
{/if}
