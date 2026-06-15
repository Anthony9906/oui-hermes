<script lang="ts">
	export let payload: any;

	$: data = payload && typeof payload === 'object' ? payload : { value: payload };
	$: title = data.title || data.name || 'AG-UI Preview';
	$: subtitle = data.subtitle || data.summary || data.description || '';
	$: metrics =
		data.metrics && typeof data.metrics === 'object' && !Array.isArray(data.metrics)
			? Object.entries(data.metrics)
			: [];
	$: items = Array.isArray(data.items) ? data.items : [];
	$: sections = Array.isArray(data.sections) ? data.sections : [];
	$: jsonText = JSON.stringify(data, null, 2);

	const formatValue = (value: any) => {
		if (value === null || value === undefined) return '';
		if (typeof value === 'object') return JSON.stringify(value, null, 2);
		return String(value);
	};
</script>

<div class="min-h-full bg-gray-50 text-gray-800 dark:bg-gray-900 dark:text-gray-100">
	<div class="space-y-4 px-5 py-5">
		<section
			class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-850"
		>
			<div class="text-xs font-semibold uppercase text-gray-500">AG-UI Artifact</div>
			<h2 class="mt-1 text-lg font-bold">{title}</h2>
			{#if subtitle}
				<p class="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-300">{subtitle}</p>
			{/if}
		</section>

		{#if metrics.length > 0}
			<section class="grid grid-cols-2 gap-2">
				{#each metrics as [key, value]}
					<div
						class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-850"
					>
						<div class="text-xs text-gray-500">{key}</div>
						<div class="mt-1 break-words text-sm font-semibold">{formatValue(value)}</div>
					</div>
				{/each}
			</section>
		{/if}

		{#if items.length > 0}
			<section class="space-y-2">
				<div class="text-sm font-semibold">Items</div>
				{#each items as item, index}
					<div
						class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-850"
					>
						<div class="text-xs font-semibold text-gray-500">#{index + 1}</div>
						<pre class="mt-2 whitespace-pre-wrap break-words text-xs leading-relaxed">{formatValue(
								item
							)}</pre>
					</div>
				{/each}
			</section>
		{/if}

		{#if sections.length > 0}
			<section class="space-y-2">
				<div class="text-sm font-semibold">Sections</div>
				{#each sections as section}
					<div
						class="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-850"
					>
						<div class="text-sm font-semibold">{section.title || section.name || 'Section'}</div>
						<pre class="mt-2 whitespace-pre-wrap break-words text-xs leading-relaxed">{formatValue(
								section.content ?? section.body ?? section
							)}</pre>
					</div>
				{/each}
			</section>
		{/if}

		<section
			class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-850"
		>
			<div class="text-sm font-semibold">Raw Payload</div>
			<pre
				class="mt-3 max-h-[38rem] overflow-auto rounded-md bg-gray-950 p-3 text-xs leading-relaxed text-gray-100">{jsonText}</pre>
		</section>
	</div>
</div>
