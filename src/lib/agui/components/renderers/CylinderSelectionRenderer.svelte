<script lang="ts">
	import LucideIcon from '$lib/components/expert-agents/LucideIcon.svelte';

	/**
	 * CylinderSelectionRenderer — renders cylinder-selection-public artifact.
	 *
	 * Replicates the key visual structure from minio-artifact-viewer.html:
	 *   - Scenario info card
	 *   - Process steps (4-step bar)
	 *   - Recommendations (1 primary + 2 alternate)
	 *   - Selection basis
	 *   - Information sources
	 *   - Manual review conditions
	 */
	export let payload: any;

	$: data = payload?.data || payload || {};
	$: scenario = data?.scenarioInfo || {};
	$: steps = data?.processSteps || [];
	$: recommendations = data?.recommendations || [];
	$: selectionBasis = data?.selectionBasis || [];
	$: infoSources = data?.informationSources || [];
	$: manualReview = data?.manualReviewConditions || [];
	$: calcSummary = data?.calculationSummary || {};

	$: primaryRec = recommendations.find((r: any) => r.rank === 'primary');
	$: alternateRecs = recommendations.filter((r: any) => r.rank === 'alternate');

	let imagePreview: { url: string; alt: string } | null = null;

	const processCards = [
		{
			icon: '🔎',
			title: '机构识别',
			subtitle: 'Mechanism',
			color: '#FF9800',
			background: '#FFF4DF'
		},
		{
			icon: '⚡',
			title: '受力计算',
			subtitle: 'Force Calc',
			color: '#4CAF50',
			background: '#EAF7EA'
		},
		{
			icon: '📐',
			title: '缸径选定',
			subtitle: 'Bore',
			color: '#2196F3',
			background: '#E4F3FF'
		},
		{
			icon: '🗂️',
			title: '标库命中',
			subtitle: 'Catalog',
			color: '#9C27B0',
			background: '#F3E5F5'
		}
	];

	const calcLabels: Record<string, string> = {
		totalLoad: '负载',
		load: '负载',
		payload: '负载',
		speed: '速度',
		velocity: '速度',
		frictionCoefficient: '摩擦系数',
		frictionForce: '摩擦力',
		accelForce: '加速力',
		accelerationForce: '加速力',
		requiredForce: '需求力',
		forceRequired: '需求力',
		safetyFactor: '安全系数',
		selectedBore: '缸径',
		bore: '缸径',
		stroke: '行程',
		pressure: '压力',
		theoreticalForce: '理论推力',
		forceMargin: '推力裕量'
	};

	const staticThumbnailBySeries: Record<string, string> = {
		RMS: '/assets/images/expert-agent/cylinder-selection/airtac-rms.png',
		HFZ: '/assets/images/expert-agent/cylinder-selection/airtac-hfz.png',
		HLS: '/assets/images/expert-agent/cylinder-selection/airtac-hls.png',
		HRQ: '/assets/images/expert-agent/cylinder-selection/airtac-hrq.png',
		MD: '/assets/images/expert-agent/cylinder-selection/airtac-md.png',
		TNTR: '/assets/images/expert-agent/cylinder-selection/airtac-tntr.png'
	};

	const normalizeSummaryValue = (val: any) =>
		typeof val === 'object' && val !== null
			? val
			: { value: String(val ?? ''), detail: '', label: '' };

	const humanizeKey = (key: string) =>
		key
			.replace(/([a-z0-9])([A-Z])/g, '$1 $2')
			.replace(/[_-]+/g, ' ')
			.trim();

	const getCalcLabel = (key: string, val: any) => {
		if (val?.label) return val.label;
		if (val?.name) return val.name;
		if (calcLabels[key]) return calcLabels[key];
		return humanizeKey(key);
	};

	const isWarningSummary = (key: string) => {
		const normalized = key.toLowerCase();
		return normalized.includes('safety') || key.includes('复核') || normalized.includes('note');
	};

	const getThumbnailUrl = (rec: any) => {
		const rawUrl = rec?.thumbnailUrl || rec?.imageUrl || rec?.thumbnail || rec?.image || '';
		const model = String(rec?.model || '').toUpperCase();
		const mapped = Object.entries(staticThumbnailBySeries).find(([series]) =>
			model.includes(series)
		)?.[1];

		if (
			typeof rawUrl === 'string' &&
			rawUrl &&
			!rawUrl.includes('10.10.14.110') &&
			!rawUrl.includes('/agent-files/ea/assets/cylinder-thumbnails/')
		) {
			return rawUrl;
		}

		return mapped || rawUrl;
	};

	const getImageAlt = (rec: any) =>
		rec?.imageAlt || `${rec?.brand || ''} ${rec?.model || ''}`.trim() || 'Product preview';

	const openImagePreview = (rec: any) => {
		const url = getThumbnailUrl(rec);
		if (!url) return;
		imagePreview = { url, alt: getImageAlt(rec) };
	};
</script>

<div class="artifact-container min-h-full bg-[#F8FAFC] font-sans text-[#26384f]">
	<!-- Scenario Info Card -->
	<div class="px-5 pt-5 pb-3">
		<div class="bg-white rounded-xl border border-[#dbe8f7] p-4 shadow-sm">
			<div class="mb-2 text-xs font-medium uppercase tracking-wide text-[#5f7190]">
				{scenario.mode || '标准选型 / Standard Selection'}
			</div>
			<h2 class="text-xl font-bold leading-tight text-[#001f5b]">
				{scenario.trigger || scenario.scenario || '选型结果'}
			</h2>
			{#if scenario.scenario && scenario.scenario !== scenario.trigger}
				<p class="text-sm text-[#5f7190] mt-1">{scenario.scenario}</p>
			{/if}
			{#if scenario.badge}
				<div class="mt-2 inline-block text-xs bg-amber-50 text-amber-700 px-2 py-1 rounded-md">
					{scenario.badge}
				</div>
			{/if}
		</div>
	</div>

	<!-- Process Steps -->
	{#if steps.length === 4}
		<div class="px-5 pb-3 pt-5">
			<h2 class="mb-3 text-lg font-bold leading-tight text-[#111827]">
				🧠 AI 理解与推理 / AI Understanding & Reasoning
			</h2>
			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
				{#each steps as step, i}
					{@const card = processCards[i]}
					<div
						class="flex min-h-[150px] flex-col rounded-xl p-3.5 text-left"
						style="background-color: {card.background};"
					>
						<div class="mb-4 text-2xl leading-none">
							{card.icon}
						</div>
						<div class="text-xs font-bold text-[#6b7280]">{card.title}</div>
						<div class="text-xs font-semibold text-[#a1a1aa]">{card.subtitle}</div>
						<div class="mt-3 text-lg font-bold leading-tight text-[#111827]">{step.value}</div>
						<div class="mt-2 text-xs leading-snug text-[#4b5563]">{step.detail}</div>
						{#if step.source}
							<div
								class="mt-auto inline-flex max-w-full items-center self-start rounded px-1.5 py-0.5 text-[10px] font-medium text-white"
								style="background-color: {card.color};"
							>
								<span class="truncate">{step.source}</span>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Calculation Summary Tags -->
	{#if Object.keys(calcSummary).length > 0}
		<div class="px-5 pb-2">
			<div class="flex flex-wrap gap-x-3 gap-y-1.5">
				{#each Object.entries(calcSummary) as [key, val]}
					{@const v = normalizeSummaryValue(val)}
					{@const label = getCalcLabel(key, v)}
					{@const isWarning = isWarningSummary(key)}
					<span
						class="inline-flex items-baseline gap-1 rounded bg-gray-100 px-2 py-1 text-xs text-[#64748b]"
						class:text-amber-700={isWarning}
						title={v.detail || ''}
					>
						<span class="font-medium">{label}</span>
						<strong class="font-semibold text-[#26384f]">{v.value}</strong>
					</span>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Recommendations -->
	{#if primaryRec}
		<div class="px-5 pb-3">
			<h2 class="mb-3 mt-3 text-base font-bold leading-tight text-[#111827]">
				📦 推荐型号 / Recommendations
			</h2>
			<!-- Primary -->
			<div class="rounded-xl bg-[#1976D2] p-4 text-white shadow-sm">
				<div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_45%]">
					<div class="min-w-0">
						<div class="mb-4 flex flex-wrap items-center gap-2">
							<span class="text-xl leading-none">★</span>
							<span class="rounded-md bg-white/20 px-3 py-1.5 text-sm font-bold">首选 Primary</span>
							{#if primaryRec.source?.includes('工程师验证')}
								<span
									class="rounded-md bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-700"
									>✅ 工程师验证 Verified</span
								>
							{/if}
						</div>
						<div class="text-2xl font-bold leading-tight">{primaryRec.model}</div>
						<div class="mt-3 text-sm font-semibold text-white/85">
							{primaryRec.brand} · 料号 {primaryRec.partNo}
						</div>
						<div class="mt-4 flex flex-wrap gap-2">
							{#if primaryRec.bore}
								<span class="rounded-md bg-white/20 px-2.5 py-1 text-xs font-semibold"
									>{primaryRec.bore}</span
								>
							{/if}
							{#if primaryRec.stroke}
								<span class="rounded-md bg-white/20 px-2.5 py-1 text-xs font-semibold"
									>{primaryRec.stroke}</span
								>
							{/if}
							{#if primaryRec.theoreticalForce}
								<span class="rounded-md bg-white/20 px-2.5 py-1 text-xs font-semibold"
									>{primaryRec.theoreticalForce}</span
								>
							{/if}
						</div>
						{#if primaryRec.mounting}
							<div
								class="mt-3 inline-flex max-w-full rounded-md bg-white/20 px-2.5 py-1 text-xs font-semibold"
							>
								<span class="truncate">{primaryRec.mounting}</span>
							</div>
						{/if}
						{#if primaryRec.reason}
							<div
								class="mt-4 border-t border-white/20 pt-3 text-sm font-normal leading-relaxed text-white/70"
							>
								{primaryRec.reason}
							</div>
						{/if}
					</div>
					{#if getThumbnailUrl(primaryRec)}
						<div class="flex min-w-0 flex-col items-center justify-center">
							<button
								type="button"
								class="w-full rounded-xl bg-slate-50 p-2.5 transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-white/70"
								aria-label="放大查看产品图片"
								on:click={() => openImagePreview(primaryRec)}
							>
								<img
									class="max-h-44 w-full rounded-md object-contain"
									src={getThumbnailUrl(primaryRec)}
									alt={getImageAlt(primaryRec)}
									loading="lazy"
								/>
							</button>
							<div class="mt-2 text-center text-xs font-semibold text-white/75">
								产品图片预览 / Product preview
							</div>
						</div>
					{/if}
				</div>
			</div>

			<!-- Alternates -->
			<div class="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
				{#each alternateRecs as alt, i}
					<div class="rounded-xl border border-[#dedede] bg-white p-4 shadow-sm">
						<div class="flex items-start gap-3">
							<div class="min-w-0 flex-1">
								<div class="mb-3 flex items-center gap-2 text-xs font-bold text-[#71717a]">
									<span class="text-[#111827]">✦</span>
									<span>备选 {i + 1} / Alt {i + 1}</span>
								</div>
								<div class="text-lg font-bold leading-tight text-[#111827]">{alt.model}</div>
								<div class="mt-1 text-sm font-medium text-[#71717a]">
									{alt.brand} · {alt.partNo}
								</div>
							</div>
							{#if getThumbnailUrl(alt)}
								<button
									type="button"
									class="h-14 w-20 shrink-0 rounded-lg border border-gray-100 bg-gray-50 p-1 transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-blue-200"
									aria-label="放大查看产品图片"
									on:click={() => openImagePreview(alt)}
								>
									<img
										class="h-full w-full object-contain"
										src={getThumbnailUrl(alt)}
										alt={getImageAlt(alt)}
										loading="lazy"
									/>
								</button>
							{/if}
						</div>
						<div class="mt-3 flex flex-wrap gap-2">
							{#if alt.bore}
								<span
									class="rounded-md bg-gray-100 px-2.5 py-1.5 text-xs font-medium text-[#52525b]"
									>{alt.bore}</span
								>
							{/if}
							{#if alt.stroke}
								<span
									class="rounded-md bg-gray-100 px-2.5 py-1.5 text-xs font-medium text-[#52525b]"
									>{alt.stroke}</span
								>
							{/if}
							{#if alt.theoreticalForce}
								<span
									class="rounded-md bg-gray-100 px-2.5 py-1.5 text-xs font-medium text-[#52525b]"
									>{alt.theoreticalForce}</span
								>
							{/if}
						</div>
						<div
							class="mt-3 border-t border-dashed border-[#d4d4d8] pt-3 text-xs leading-relaxed text-[#71717a]"
						>
							{alt.diff || alt.reason || alt.mounting}
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Selection Basis -->
	{#if selectionBasis.length > 0}
		<div class="px-5 pb-3">
			<div class="bg-white rounded-xl border border-[#dbe8f7] p-4 shadow-sm">
				<h3 class="text-sm font-bold text-[#001f5b] mb-2">选型依据 / Selection Basis</h3>
				<ul class="space-y-1">
					{#each selectionBasis as item}
						<li class="text-sm text-[#5f7190] flex gap-2">
							<span class="text-blue-500 shrink-0">•</span>
							<span>{item}</span>
						</li>
					{/each}
				</ul>
			</div>
		</div>
	{/if}

	<!-- Information Sources -->
	{#if infoSources.length > 0}
		<div class="px-5 pb-3">
			<div class="bg-white rounded-xl border border-[#dbe8f7] p-4 shadow-sm">
				<h3 class="text-sm font-bold text-[#001f5b] mb-2">信息来源 / Information Sources</h3>
				<div class="space-y-1.5">
					{#each infoSources as src}
						<div class="flex items-start gap-2 text-sm">
							<LucideIcon
								name="file-check"
								className="mt-0.5 size-4 shrink-0 text-[#6b88ad]"
								strokeWidth="1.8"
							/>
							<div>
								<span class="font-medium text-[#26384f]">{src.source}</span>
								<span class="text-[#5f7190] ml-1">— {src.category}</span>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	{/if}

	<!-- Manual Review -->
	{#if manualReview.length > 0}
		<div class="px-5 pb-5">
			<div class="bg-amber-50 rounded-xl border border-amber-200 p-4">
				<h3 class="text-sm font-bold text-amber-800 mb-2">
					⚠ 人工复核项目 / Manual Review Required
				</h3>
				<ul class="space-y-1">
					{#each manualReview as item}
						<li class="text-sm text-amber-700 flex gap-2">
							<span class="shrink-0">•</span>
							<span>{item}</span>
						</li>
					{/each}
				</ul>
			</div>
		</div>
	{/if}

	<!-- Footer -->
	<div class="px-5 pb-5">
		<p class="text-xs text-gray-400 text-center">
			AI can make mistakes — verify all selections with your engineering team before use.
		</p>
	</div>

	{#if imagePreview}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6">
			<button
				type="button"
				class="absolute inset-0 h-full w-full cursor-default"
				aria-label="关闭图片预览"
				on:click={() => (imagePreview = null)}
			></button>
			<div
				class="relative z-10 max-h-[88vh] max-w-[92vw] overflow-hidden rounded-xl bg-white p-4 shadow-2xl"
				role="dialog"
				aria-modal="true"
				tabindex="-1"
			>
				<button
					type="button"
					class="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full bg-white text-xl leading-none text-gray-500 shadow hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-300"
					aria-label="关闭图片预览"
					on:click={() => (imagePreview = null)}
				>
					×
				</button>
				<img
					class="max-h-[calc(88vh-2rem)] max-w-[calc(92vw-2rem)] rounded-lg object-contain"
					src={imagePreview.url}
					alt={imagePreview.alt}
				/>
			</div>
		</div>
	{/if}
</div>
