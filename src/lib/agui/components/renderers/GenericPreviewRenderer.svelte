<script lang="ts">
	export let payload: any;

	$: data = payload && typeof payload === 'object' ? payload : { value: payload };
	$: title = data.title || data.name || 'AG-UI Preview Test';
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

<div class="min-h-full bg-[#f7f8fb] text-[#26384f]">
	<div class="px-5 py-5 space-y-4">
		<section class="rounded-lg border border-[#dbe3ef] bg-white p-4 shadow-sm">
			<div class="text-xs font-semibold uppercase text-[#64748b]">Generic AG-UI Artifact</div>
			<h2 class="mt-1 text-lg font-bold text-[#102a56]">{title}</h2>
			{#if subtitle}
				<p class="mt-2 text-sm leading-relaxed text-[#52647c]">{subtitle}</p>
			{/if}
		</section>

		{#if metrics.length > 0}
			<section class="grid grid-cols-2 gap-2">
				{#each metrics as [key, value]}
					<div class="rounded-lg border border-[#dbe3ef] bg-white p-3">
						<div class="text-xs text-[#64748b]">{key}</div>
						<div class="mt-1 break-words text-sm font-semibold text-[#102a56]">
							{formatValue(value)}
						</div>
					</div>
				{/each}
			</section>
		{/if}

		{#if items.length > 0}
			<section class="space-y-2">
				<div class="text-sm font-semibold text-[#102a56]">Items</div>
				{#each items as item, index}
					<div class="rounded-lg border border-[#dbe3ef] bg-white p-3">
						<div class="text-xs font-semibold text-[#64748b]">#{index + 1}</div>
						<pre
							class="mt-2 whitespace-pre-wrap break-words text-xs leading-relaxed text-[#334155]">{formatValue(
								item
							)}</pre>
					</div>
				{/each}
			</section>
		{/if}

		{#if sections.length > 0}
			<section class="space-y-2">
				<div class="text-sm font-semibold text-[#102a56]">Sections</div>
				{#each sections as section}
					<div class="rounded-lg border border-[#dbe3ef] bg-white p-3">
						<div class="text-sm font-semibold text-[#102a56]">
							{section.title || section.name || 'Section'}
						</div>
						<pre
							class="mt-2 whitespace-pre-wrap break-words text-xs leading-relaxed text-[#334155]">{formatValue(
								section.content ?? section.body ?? section
							)}</pre>
					</div>
				{/each}
			</section>
		{/if}

		<section class="rounded-lg border border-[#dbe3ef] bg-white p-4">
			<div class="text-sm font-semibold text-[#102a56]">Raw Payload</div>
			<pre
				class="mt-3 max-h-[38rem] overflow-auto rounded-md bg-[#0f172a] p-3 text-xs leading-relaxed text-[#e2e8f0]">{jsonText}</pre>
		</section>
	</div>
</div>
