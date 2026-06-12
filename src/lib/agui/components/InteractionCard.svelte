<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { cubicOut } from 'svelte/easing';
	import { fly, scale } from 'svelte/transition';

	import type { AguiInteractionOption, AguiInteractionRequest } from '../stores/agui';
	import LockClosed from '$lib/components/icons/LockClosed.svelte';
	import LucideIcon from '$lib/components/expert-agents/LucideIcon.svelte';
	import Pencil from '$lib/components/icons/Pencil.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	const dispatch = createEventDispatcher<{
		submit: {
			interaction: AguiInteractionRequest;
			response: {
				type: 'option' | 'custom' | 'approval';
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
	$: isApproval = interaction?.kind === 'approval';

	const getOptionPrefix = (index: number) =>
		index >= 0 && index < 26 ? String.fromCharCode(65 + index) : String(index + 1);

	const getOptionDescription = (option: AguiInteractionOption) => {
		if (option.description) return option.description;

		const fallbackDescriptions: Record<string, string> = {
			薄型气缸: '紧凑空间、短行程，适合安装空间受限的场合',
			标准气缸: '通用性强、行程范围广，适合常规自动化设备',
			导杆气缸: '自带导向、抗侧向负载，适合精度要求更高的场合'
		};

		return fallbackDescriptions[option.label] ?? fallbackDescriptions[option.value] ?? '';
	};

	const selectOption = (option: AguiInteractionOption) => {
		if (disabled) return;

		dispatch('submit', {
			interaction,
			response: {
				type: isApproval ? 'approval' : 'option',
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
		class="agui-interaction-card overflow-hidden rounded-lg border-2 text-[#071f4d]"
		aria-live="polite"
	>
		<div class="agui-interaction-card__header flex items-center justify-between gap-3 px-4 py-3">
			<div class="min-w-0 flex-1">
				<div class="flex items-center gap-3 text-base font-semibold text-[#071f4d] sm:text-lg">
					<span
						class="flex size-8 shrink-0 items-center justify-center text-[#3478d9]"
						aria-hidden="true"
					>
						{#if isApproval}
							<LockClosed className="size-7" strokeWidth="1.8" />
						{:else}
							<LucideIcon
								name="message-circle-question-mark"
								className="size-7"
								strokeWidth="1.8"
							/>
						{/if}
					</span>
					<span class="truncate">{interaction.title}</span>
				</div>
			</div>
			<button
				type="button"
				class="rounded-lg p-1.5 text-[#7b8aa6] transition hover:bg-[#e9f6ff] hover:text-[#31506b] focus:outline-none focus:ring-2 focus:ring-[#60a5fa]/35"
				aria-label="关闭交互卡片"
				on:click={() => dispatch('close', { interaction })}
			>
				<XMark className="size-4" />
			</button>
		</div>

		<div class="space-y-2 px-4 py-2.5">
			{#each interaction.options as option, index (option.id)}
				{@const optionDescription = getOptionDescription(option)}
				<button
					type="button"
					class="group flex w-full items-center gap-3 rounded-lg bg-[#f3f5f8] px-3 py-2.5 text-left shadow-[inset_0_1px_0_rgba(255,255,255,0.72)] transition hover:bg-[#edf1f6] focus:outline-none focus:ring-2 focus:ring-[#60a5fa]/35 disabled:cursor-not-allowed disabled:opacity-60"
					{disabled}
					on:click={() => selectOption(option)}
				>
					<span
						class="flex size-7 shrink-0 items-center justify-center rounded-full bg-[#1f3b63] text-sm font-semibold text-white transition group-hover:bg-[#2f5688]"
						aria-hidden="true"
					>
						{getOptionPrefix(index)}
					</span>
					<span class="flex min-w-0 flex-1 items-baseline justify-between gap-3">
						<span class="min-w-0 truncate text-base font-semibold text-[#071f4d]">
							{option.label}
						</span>
						{#if optionDescription}
							<span
								class="max-w-[58%] shrink-0 truncate text-right text-xs leading-4 text-[#6b7280]"
								title={optionDescription}
							>
								{optionDescription}
							</span>
						{/if}
					</span>
				</button>
			{/each}

			{#if interaction.allow_custom}
				<form
					class="flex items-center gap-2 rounded-lg bg-[#f3f5f8] p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.72)]"
					on:submit|preventDefault={submitCustom}
				>
					<label
						class="flex size-9 shrink-0 items-center justify-center rounded-md bg-white/72 text-[#31506b]"
						aria-label={interaction.custom_label}
					>
						<Pencil className="size-4" strokeWidth="1.9" />
					</label>
					<input
						class="h-9 min-w-0 flex-1 rounded-md bg-white/78 px-3 text-sm text-[#071f4d] outline-none transition placeholder:text-[#7b8aa6] focus:bg-white focus:ring-2 focus:ring-[#60a5fa]/25"
						bind:value={customValue}
						placeholder={interaction.custom_placeholder}
						{disabled}
					/>
					<button
						type="submit"
						class="flex size-9 shrink-0 items-center justify-center rounded-md bg-[#3478d9] text-white shadow-[0_3px_8px_rgba(52,120,217,0.22)] transition hover:bg-[#256ecf] focus:outline-none focus:ring-2 focus:ring-[#60a5fa]/40 disabled:cursor-not-allowed disabled:bg-[#cbd7e8] disabled:text-white"
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

<style>
	.agui-interaction-card {
		position: relative;
		isolation: isolate;
		border-color: rgba(70, 156, 245, 0.88);
		background:
			linear-gradient(
				135deg,
				rgba(248, 252, 255, 0.98) 0%,
				rgba(240, 248, 255, 0.96) 54%,
				rgba(232, 244, 255, 0.96) 100%
			),
			radial-gradient(circle at 88% 18%, rgba(127, 203, 255, 0.12), transparent 34%);
		box-shadow:
			0 18px 42px rgba(24, 86, 154, 0.14),
			0 6px 18px rgba(71, 154, 236, 0.08),
			inset 0 1px 0 rgba(255, 255, 255, 0.96);
		backdrop-filter: blur(18px) saturate(1.18);
		-webkit-backdrop-filter: blur(18px) saturate(1.18);
	}

	.agui-interaction-card::before {
		content: '';
		position: absolute;
		inset: 0;
		z-index: -1;
		border-radius: inherit;
		border-top: 1px solid rgba(159, 221, 255, 0.82);
		background:
			linear-gradient(118deg, rgba(255, 255, 255, 0.74) 0%, transparent 38%),
			repeating-linear-gradient(
				135deg,
				rgba(255, 255, 255, 0.14) 0,
				rgba(255, 255, 255, 0.14) 1px,
				rgba(255, 255, 255, 0) 1px,
				rgba(255, 255, 255, 0) 7px
			);
		pointer-events: none;
	}

	.agui-interaction-card__header {
		border-bottom: 1px solid rgba(159, 211, 250, 0.62);
		background: linear-gradient(180deg, rgba(255, 255, 255, 0.6), rgba(233, 246, 255, 0.36));
	}
</style>
