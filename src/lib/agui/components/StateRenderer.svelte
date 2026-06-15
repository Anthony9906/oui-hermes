<script lang="ts">
	import GenericPreviewRenderer from './renderers/GenericPreviewRenderer.svelte';
	import HtmlPreviewRenderer from './renderers/HtmlPreviewRenderer.svelte';
	import MarkdownPreviewRenderer from './renderers/MarkdownPreviewRenderer.svelte';
	import CylinderSelectionRenderer from './renderers/CylinderSelectionRenderer.svelte';
	import MotorSelectionRenderer from './renderers/MotorSelectionRenderer.svelte';

	export let artifactType: string;
	export let payload: any;

	const renderers: Record<string, any> = {
		'generic-preview': GenericPreviewRenderer,
		'generic-json': GenericPreviewRenderer,
		'agui-generic': GenericPreviewRenderer,
		'html-preview': HtmlPreviewRenderer,
		'markdown-preview': MarkdownPreviewRenderer,
		'cylinder-selection-public': CylinderSelectionRenderer,
		'motor-selection-public': MotorSelectionRenderer
	};

	$: Renderer = renderers[artifactType] || null;
</script>

{#if Renderer}
	<svelte:component this={Renderer} {payload} />
{:else}
	<div class="p-4 text-sm text-gray-500">不支持的制品类型: {artifactType}</div>
{/if}
