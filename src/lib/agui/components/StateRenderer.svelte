<script lang="ts">
	/**
	 * StateRenderer — renders artifact payloads based on artifact_type.
	 *
	 * Renderer registry maps artifact_type → Svelte component.
	 * Phase 1: cylinder-selection-public + generic test renderer.
	 * Phase 2+: motor-selection-public, chart, markdown, html, etc.
	 */
	import CylinderSelectionRenderer from './renderers/CylinderSelectionRenderer.svelte';
	import GenericPreviewRenderer from './renderers/GenericPreviewRenderer.svelte';

	export let artifactType: string;
	export let payload: any;

	// ── Renderer registry ───────────────────────────────────────────────
	const renderers: Record<string, any> = {
		'cylinder-selection-public': CylinderSelectionRenderer,
		'generic-preview': GenericPreviewRenderer,
		'generic-json': GenericPreviewRenderer,
		'agui-generic': GenericPreviewRenderer
	};

	$: Renderer = renderers[artifactType] || null;
</script>

{#if Renderer}
	<svelte:component this={Renderer} {payload} />
{:else}
	<div class="p-4 text-sm text-gray-500">
		不支持的制品类型: {artifactType}
	</div>
{/if}
