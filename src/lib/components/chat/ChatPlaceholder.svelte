<script lang="ts">
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';

	import { config, user, models as _models, temporaryChatEnabled } from '$lib/stores';
	import { onMount, getContext } from 'svelte';

	import { blur, fade } from 'svelte/transition';

	import Suggestions from './Suggestions.svelte';
	import { sanitizeResponseContent } from '$lib/utils';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EyeSlash from '$lib/components/icons/EyeSlash.svelte';

	const i18n = getContext('i18n');

	export let modelIds = [];
	export let models = [];
	export let atSelectedModel;

	export let onSelect = (e) => {};

	let mounted = false;
	let selectedModelIdx = 0;

	$: if (modelIds.length > 0) {
		selectedModelIdx = models.length - 1;
	}

	$: models = modelIds.map((id) => $_models.find((m) => m.id === id));

	onMount(() => {
		mounted = true;
	});
</script>

{#key mounted}
	<div class="mx-auto mt-[clamp(3rem,9vh,5.5rem)] mb-auto w-full max-w-6xl px-2.5">
		{#if $temporaryChatEnabled}
			<Tooltip
				content={$i18n.t("This chat won't appear in history and your messages will not be saved.")}
				className="w-full flex justify-start mb-0.5"
				placement="top"
			>
				<div class="flex items-center gap-2 text-gray-500 text-lg mt-2 w-fit">
					<EyeSlash strokeWidth="2.5" className="size-5" />{$i18n.t('Temporary Chat')}
				</div>
			</Tooltip>
		{/if}

		<div class="mb-8 text-left flex items-center gap-4 font-primary">
			<div class="w-full min-w-0">
				<div
					class="expert-agent-title line-clamp-1 text-[3.75rem] lg:text-[4.25rem] font-bold leading-none tracking-normal"
					data-text={models[selectedModelIdx]?.name ??
						$i18n.t('Hello, {{name}}', { name: $user?.name })}
					in:fade={{ duration: 200 }}
				>
					{#if models[selectedModelIdx]?.name}
						{models[selectedModelIdx]?.name}
					{:else}
						{$i18n.t('Hello, {{name}}', { name: $user?.name })}
					{/if}
				</div>

				<div in:fade={{ duration: 200, delay: 200 }}>
					{#if models[selectedModelIdx]?.info?.meta?.description ?? null}
						<div
							class="expert-agent-subtitle mt-3 w-full max-w-[42rem] break-words text-[1.75rem] lg:text-[1.875rem] xl:max-w-[64rem] xl:text-[2rem] leading-tight text-[#52617e] dark:text-gray-300 line-clamp-2 markdown"
						>
							{@html DOMPurify.sanitize(
								marked.parse(
									sanitizeResponseContent(
										models[selectedModelIdx]?.info?.meta?.description
									).replaceAll('\n', '<br>')
								)
							)}
						</div>
						{#if models[selectedModelIdx]?.info?.meta?.user}
							<div class="mt-0.5 text-sm font-normal text-gray-400 dark:text-gray-500">
								By
								{#if models[selectedModelIdx]?.info?.meta?.user.community}
									<a
										href="https://openwebui.com/m/{models[selectedModelIdx]?.info?.meta?.user
											.username}"
										>{models[selectedModelIdx]?.info?.meta?.user.name
											? models[selectedModelIdx]?.info?.meta?.user.name
											: `@${models[selectedModelIdx]?.info?.meta?.user.username}`}</a
									>
								{:else}
									{models[selectedModelIdx]?.info?.meta?.user.name}
								{/if}
							</div>
						{/if}
					{:else}
						<div
							class="expert-agent-subtitle w-full max-w-[42rem] break-words text-[1.75rem] lg:text-[1.875rem] xl:max-w-[64rem] xl:text-[2rem] text-[#52617e] dark:text-gray-300 line-clamp-2"
						>
							{$i18n.t('How can I help you today?')}
						</div>
					{/if}
				</div>
			</div>
		</div>

		<div
			class="mt-[clamp(4rem,10vh,6.25rem)] w-full font-primary"
			in:fade={{ duration: 200, delay: 300 }}
		>
			<Suggestions
				suggestionPrompts={atSelectedModel?.info?.meta?.suggestion_prompts ??
					models[selectedModelIdx]?.info?.meta?.suggestion_prompts ??
					$config?.default_prompt_suggestions ??
					[]}
				{onSelect}
			/>
		</div>
	</div>
{/key}

<style>
	.expert-agent-title {
		position: relative;
		display: inline-block;
		background: linear-gradient(
			90deg,
			#7bdcff 0%,
			#b7f0ff 6%,
			#9ee7ff 12%,
			#58c9ff 18%,
			#1684e8 24%,
			#0b4ca3 32%,
			#071f4d 40%,
			#2d6fc4 45%,
			#58c9ff 49%,
			#7bdcff 50%,
			#b7f0ff 56%,
			#9ee7ff 62%,
			#58c9ff 68%,
			#1684e8 74%,
			#0b4ca3 82%,
			#071f4d 90%,
			#2d6fc4 95%,
			#58c9ff 99%,
			#7bdcff 100%
		);
		background-size: 200% 100%;
		background-position: 0% 50%;
		background-repeat: repeat-x;
		-webkit-background-clip: text;
		background-clip: text;
		-webkit-text-fill-color: transparent;
		color: transparent;
		text-shadow: none;
		filter: none;
		text-transform: none;
		animation: expert-agent-gradient-flow 24s linear infinite;
	}

	.expert-agent-subtitle {
		font-family:
			-apple-system, BlinkMacSystemFont, 'Inter', 'Vazirmatn', ui-sans-serif, system-ui, 'Segoe UI',
			Roboto, Ubuntu, Cantarell, 'Noto Sans', sans-serif, 'Helvetica Neue', Arial,
			'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji';
		font-weight: 100;
		color: #a8a8a8;
		font-size: 2.5rem;
	}

	@keyframes expert-agent-gradient-flow {
		0% {
			background-position: 0% 50%;
		}
		100% {
			background-position: 100% 50%;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.expert-agent-title {
			animation: none;
			background-position: 50% 50%;
		}
	}
</style>
