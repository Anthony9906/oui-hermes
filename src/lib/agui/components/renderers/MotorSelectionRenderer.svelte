<script lang="ts">
	import { onMount } from 'svelte';
	import LucideIcon from '$lib/components/expert-agents/LucideIcon.svelte';

	export let payload: any;
	let modelViewerFailed = false;

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
			icon: '⚙️',
			title: '扭矩校核',
			subtitle: 'Torque Check',
			color: '#2563EB',
			background: '#E4F3FF'
		},
		{
			icon: '🗂️',
			title: '标库命中',
			subtitle: 'Catalog Match',
			color: '#9C27B0',
			background: '#F3E5F5'
		}
	];

	const calcLabels: Record<string, string> = {
		angularAccel: '角加速度',
		motorSpeed: '电机转速',
		loadInertia: '负载惯量',
		screwInertia: '丝杆惯量',
		totalInertia: '总惯量',
		reflectedInertia: '折算惯量',
		frictionTorque: '摩擦力矩',
		gravityTorque: '重力矩',
		accelTorque: '加速扭矩',
		peakTorque: '峰值扭矩',
		reqTorque: '选型扭矩',
		requiredTorque: '选型扭矩',
		inertiaRatio: '惯量比',
		safetyFactor: '安全系数'
	};

	const motorPreviewModelUrl = '/assets/model/MS1H4-10B30CB-A330R.glb';
	const motorPreviewIosUrl = '/assets/model/MS1H4-10B30CB-A330R-ar-x180.usdz';
	const motorPreviewOrientation = '0deg 180deg 0deg';

	const normalizeSummaryValue = (val: any) =>
		typeof val === 'object' && val !== null
			? val
			: { value: String(val ?? ''), detail: '', label: '' };

	const humanizeKey = (key: string) =>
		key
			.replace(/([a-z0-9])([A-Z])/g, '$1 $2')
			.replace(/[_-]+/g, ' ')
			.trim();

	const getCalcLabel = (key: string, val: any) =>
		val?.label || val?.name || calcLabels[key] || humanizeKey(key);

	const isWarningSummary = (key: string) => {
		const normalized = key.toLowerCase();
		return normalized.includes('safety') || key.includes('复核') || normalized.includes('note');
	};

	const getModelPreviewUrl = (_rec: any) => motorPreviewModelUrl;

	const getSpecChips = (rec: any) =>
		[
			rec?.power,
			rec?.ratedTorque ? `额定 ${rec.ratedTorque}` : '',
			rec?.rotorInertia ? `惯量 ${rec.rotorInertia}` : '',
			rec?.inertiaRatio ? `惯量比 ${rec.inertiaRatio}` : '',
			rec?.baseSize ? `基座 ${rec.baseSize}` : '',
			rec?.brake ? `刹车 ${rec.brake}` : ''
		].filter(Boolean);

	onMount(async () => {
		try {
			await import('@google/model-viewer');
		} catch {
			modelViewerFailed = true;
		}
	});
</script>

<div class="artifact-container min-h-full bg-[#F8FAFC] font-sans text-[#26384f]">
	<div class="px-5 pt-5 pb-3">
		<div class="rounded-xl border border-[#dbe8f7] bg-white p-4 shadow-sm">
			<div class="mb-2 text-xs font-medium uppercase tracking-wide text-[#5f7190]">
				{scenario.mode || '标准选型 / Standard Selection'}
			</div>
			<h2 class="text-xl font-bold leading-tight text-[#001f5b]">
				{scenario.trigger || scenario.scenario || '电机选型结果'}
			</h2>
			{#if scenario.scenario && scenario.scenario !== scenario.trigger}
				<p class="mt-1 text-sm text-[#5f7190]">{scenario.scenario}</p>
			{/if}
			{#if scenario.badge}
				<div class="mt-2 inline-block rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-700">
					{scenario.badge}
				</div>
			{/if}
		</div>
	</div>

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
						<div class="mb-4 text-2xl leading-none">{card.icon}</div>
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

	{#if primaryRec}
		<div class="px-5 pb-3">
			<h2 class="mb-3 mt-3 text-base font-bold leading-tight text-[#111827]">
				📦 推荐型号 / Recommendations
			</h2>
			<div class="rounded-xl bg-[#155E75] p-4 text-white shadow-sm">
				<div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_42%]">
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
							{#each getSpecChips(primaryRec) as chip}
								<span class="rounded-md bg-white/20 px-2.5 py-1 text-xs font-semibold">{chip}</span>
							{/each}
						</div>
						{#if primaryRec.reason}
							<div
								class="mt-4 border-t border-white/20 pt-3 text-sm font-normal leading-relaxed text-white/75"
							>
								{primaryRec.reason}
							</div>
						{/if}
					</div>
					<div class="flex min-w-0 flex-col justify-center">
						<div class="rounded-xl border border-white/20 bg-white/10 p-4">
							<div class="mb-2 flex items-center gap-2 text-sm font-bold text-white">
								<LucideIcon name="box" className="size-4" strokeWidth="1.8" />
								<span>3D/外观预览 / Model Preview</span>
							</div>
							{#if getModelPreviewUrl(primaryRec)}
								<div class="overflow-hidden rounded-lg bg-white/90">
									{#if modelViewerFailed}
										<a
											class="block break-all px-3 py-3 text-xs font-semibold text-[#155E75] transition hover:bg-white"
											href={getModelPreviewUrl(primaryRec)}
											target="_blank"
											rel="noreferrer"
										>
											{getModelPreviewUrl(primaryRec)}
										</a>
									{:else}
										<model-viewer
											class="h-48 w-full bg-[#f8fafc]"
											src={getModelPreviewUrl(primaryRec)}
											ios-src={motorPreviewIosUrl}
											orientation={motorPreviewOrientation}
											camera-controls
											ar
											ar-modes="webxr scene-viewer quick-look"
											ar-placement="floor"
											ar-scale="auto"
											auto-rotate
											rotation-per-second="24deg"
											shadow-intensity="0.65"
											exposure="0.9"
											loading="eager"
											reveal="auto"
										></model-viewer>
									{/if}
								</div>
								<div class="mt-2 text-xs text-white/70">
									参数化外观预览，非制造级 CAD/STEP 源文件。
								</div>
							{:else}
								<div class="rounded-lg bg-white/15 px-3 py-6 text-center text-sm text-white/75">
									当前推荐卡未提供 3D 模型 URL
								</div>
							{/if}
						</div>
					</div>
				</div>
			</div>

			<div class="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
				{#each alternateRecs as alt, i}
					<div class="rounded-xl border border-[#dedede] bg-white p-4 shadow-sm">
						<div class="mb-3 flex items-center gap-2 text-xs font-bold text-[#71717a]">
							<span class="text-[#111827]">✦</span>
							<span>备选 {i + 1} / Alt {i + 1}</span>
						</div>
						<div class="text-lg font-bold leading-tight text-[#111827]">{alt.model}</div>
						<div class="mt-1 text-sm font-medium text-[#71717a]">{alt.brand} · {alt.partNo}</div>
						<div class="mt-3 flex flex-wrap gap-2">
							{#each getSpecChips(alt) as chip}
								<span
									class="rounded-md bg-gray-100 px-2.5 py-1.5 text-xs font-medium text-[#52525b]"
									>{chip}</span
								>
							{/each}
						</div>
						<div
							class="mt-3 border-t border-dashed border-[#d4d4d8] pt-3 text-xs leading-relaxed text-[#71717a]"
						>
							{alt.diff || alt.reason}
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	{#if selectionBasis.length > 0}
		<div class="px-5 pb-3">
			<div class="rounded-xl border border-[#dbe8f7] bg-white p-4 shadow-sm">
				<h3 class="mb-2 text-sm font-bold text-[#001f5b]">选型依据 / Selection Basis</h3>
				<ul class="space-y-1">
					{#each selectionBasis as item}
						<li class="flex gap-2 text-sm text-[#5f7190]">
							<span class="shrink-0 text-blue-500">•</span><span>{item}</span>
						</li>
					{/each}
				</ul>
			</div>
		</div>
	{/if}

	{#if infoSources.length > 0}
		<div class="px-5 pb-3">
			<div class="rounded-xl border border-[#dbe8f7] bg-white p-4 shadow-sm">
				<h3 class="mb-2 text-sm font-bold text-[#001f5b]">信息来源 / Information Sources</h3>
				<div class="space-y-1.5">
					{#each infoSources as src}
						<div class="flex items-start gap-2 text-sm">
							<LucideIcon
								name="file-check"
								className="mt-0.5 size-4 shrink-0 text-[#6b88ad]"
								strokeWidth="1.8"
							/>
							<div>
								<span class="font-medium text-[#26384f]">{src.source}</span><span
									class="ml-1 text-[#5f7190]">— {src.category}</span
								>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	{/if}

	{#if manualReview.length > 0}
		<div class="px-5 pb-5">
			<div class="rounded-xl border border-amber-200 bg-amber-50 p-4">
				<h3 class="mb-2 text-sm font-bold text-amber-800">
					⚠ 人工复核项目 / Manual Review Required
				</h3>
				<ul class="space-y-1">
					{#each manualReview as item}
						<li class="flex gap-2 text-sm text-amber-700">
							<span class="shrink-0">•</span><span>{item}</span>
						</li>
					{/each}
				</ul>
			</div>
		</div>
	{/if}

	<div class="px-5 pb-5">
		<p class="text-center text-xs text-gray-400">
			AI can make mistakes — verify all selections with your engineering team before use.
		</p>
	</div>
</div>
