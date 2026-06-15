<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { cubicOut } from 'svelte/easing';
	import { fly, scale } from 'svelte/transition';

	import type { AguiInteractionOption, AguiInteractionRequest } from '../stores/agui';
	import LucideIcon from '$lib/components/expert-agents/LucideIcon.svelte';
	import Pencil from '$lib/components/icons/Pencil.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	const dispatch = createEventDispatcher<{
		submit: {
			interaction: AguiInteractionRequest;
			response: {
				type: 'option' | 'custom';
				id?: string;
				label?: string;
				value: string;
			};
		};
		close: { interaction: AguiInteractionRequest };
	}>();

	export let interaction: AguiInteractionRequest;
	export let disabled = false;

	let customValue = '';
	let currentInteractionId = '';

	$: if (interaction?.id !== currentInteractionId) {
		currentInteractionId = interaction?.id ?? '';
		customValue = '';
	}
	$: canSubmitCustom = customValue.trim().length > 0 && !disabled;

	const getOptionPrefix = (index: number) =>
		index >= 0 && index < 26 ? String.fromCharCode(65 + index) : String(index + 1);

	const selectOption = (option: AguiInteractionOption) => {
		if (disabled) return;

		dispatch('submit', {
			interaction,
			response: {
				type: 'option',
				id: option.id,
				label: option.label,
				value: option.value
			}
		});
	};

	const submitCustom = () => {
		const value = customValue.trim();
		if (!value || disabled) return;

		dispatch('submit', {
			interaction,
			response: {
				type: 'custom',
				label: interaction.custom_label,
				value
			}
		});

		customValue = '';
	};
</script>

<div
	class="mx-auto w-full max-w-2xl px-3 sm:px-4"
	in:fly={{ y: 18, duration: 220, easing: cubicOut }}
	out:scale={{ start: 0.98, duration: 140, easing: cubicOut }}
>
	<section
		class="overflow-hidden rounded-lg border border-blue-200 bg-white text-gray-800 shadow-xl shadow-blue-900/10 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
		aria-live="polite"
	>
		<div
			class="flex items-center justify-between gap-3 border-b border-blue-100 bg-blue-50/80 px-4 py-3 dark:border-gray-800 dark:bg-gray-850"
		>
			<div class="min-w-0 flex-1">
				<div class="flex items-center gap-3 text-base font-semibold sm:text-lg">
					<span
						class="flex size-8 shrink-0 items-center justify-center text-blue-600"
						aria-hidden="true"
					>
						<LucideIcon name="message-circle-question-mark" className="size-7" strokeWidth="1.8" />
					</span>
					<span class="truncate">{interaction.title}</span>
				</div>
			</div>
			<button
				type="button"
				class="rounded-lg p-1.5 text-gray-500 transition hover:bg-white hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500/30 dark:hover:bg-gray-800 dark:hover:text-gray-100"
				aria-label="关闭交互卡片"
				on:click={() => dispatch('close', { interaction })}
			>
				<XMark className="size-4" />
			</button>
		</div>

		<div class="space-y-2 px-4 py-3">
			{#if interaction.message}
				<div class="px-1 pb-1 text-sm leading-5 text-gray-600 dark:text-gray-300">
					{interaction.message}
				</div>
			{/if}

			{#each interaction.options as option, index (option.id)}
				<button
					type="button"
					class="group flex w-full items-center gap-3 rounded-lg bg-gray-50 px-3 py-2.5 text-left transition hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-500/30 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-gray-800 dark:hover:bg-gray-750"
					{disabled}
					on:click={() => selectOption(option)}
				>
					<span
						class="flex size-7 shrink-0 items-center justify-center rounded-full bg-gray-800 text-sm font-semibold text-white transition group-hover:bg-blue-600 dark:bg-gray-700"
						aria-hidden="true"
					>
						{getOptionPrefix(index)}
					</span>
					<span class="flex min-w-0 flex-1 items-baseline justify-between gap-3">
						<span class="min-w-0 truncate text-base font-semibold">{option.label}</span>
						{#if option.description}
							<span
								class="max-w-[58%] shrink-0 truncate text-right text-xs leading-4 text-gray-500 dark:text-gray-400"
								title={option.description}
							>
								{option.description}
							</span>
						{/if}
					</span>
				</button>
			{/each}

			{#if interaction.allow_custom}
				<form
					class="flex items-center gap-2 rounded-lg bg-gray-50 p-2 dark:bg-gray-800"
					on:submit|preventDefault={submitCustom}
				>
					<label
						class="flex size-9 shrink-0 items-center justify-center rounded-md bg-white text-gray-600 dark:bg-gray-900 dark:text-gray-300"
						aria-label={interaction.custom_label}
					>
						<Pencil className="size-4" strokeWidth="1.9" />
					</label>
					<input
						class="h-9 min-w-0 flex-1 rounded-md bg-white px-3 text-sm text-gray-800 outline-none transition placeholder:text-gray-400 focus:ring-2 focus:ring-blue-500/30 dark:bg-gray-900 dark:text-gray-100"
						bind:value={customValue}
						placeholder={interaction.custom_placeholder}
						{disabled}
					/>
					<button
						type="submit"
						class="flex size-9 shrink-0 items-center justify-center rounded-md bg-blue-600 text-white transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500/40 disabled:cursor-not-allowed disabled:bg-gray-300"
						disabled={!canSubmitCustom}
						aria-label="提交自定义回答"
					>
						<LucideIcon name="arrow-right" className="size-4" strokeWidth="2" />
					</button>
				</form>
			{/if}
		</div>
	</section>
</div>
