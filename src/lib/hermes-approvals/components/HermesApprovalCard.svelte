<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { cubicOut } from 'svelte/easing';
	import { fly, scale } from 'svelte/transition';

	import LucideIcon from '$lib/components/expert-agents/LucideIcon.svelte';
	import type { HermesApprovalChoice } from '$lib/apis/hermes-runs';
	import type { HermesApprovalRequest } from '../stores/approvals';

	const dispatch = createEventDispatcher<{
		submit: { approval: HermesApprovalRequest; choice: HermesApprovalChoice };
	}>();

	export let approval: HermesApprovalRequest;
	export let disabled = false;

	const optionInfo: Record<
		HermesApprovalChoice,
		{ label: string; description: string; icon: string; tone: string }
	> = {
		once: {
			label: '仅本次允许',
			description: '只允许当前这一次操作',
			icon: 'check',
			tone: 'hover:border-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/30'
		},
		session: {
			label: '本对话期间允许',
			description: '本次 Hermes 会话中不再询问同类操作',
			icon: 'messages-square',
			tone: 'hover:border-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/30'
		},
		always: {
			label: '永久允许该规则',
			description: '写入 Hermes 永久允许列表，请谨慎选择',
			icon: 'shield-check',
			tone: 'hover:border-orange-500 hover:bg-orange-50 dark:hover:bg-orange-950/30'
		},
		deny: {
			label: '拒绝',
			description: '不执行该操作，Hermes 将收到明确拒绝',
			icon: 'ban',
			tone: 'hover:border-red-400 hover:bg-red-50 dark:hover:bg-red-950/30'
		}
	};

	$: choices = (approval?.choices?.length
		? approval.choices
		: ['once', 'session', 'always', 'deny']) as HermesApprovalChoice[];
</script>

<div
	class="mx-auto w-full max-w-2xl px-3 sm:px-4"
	in:fly={{ y: 18, duration: 220, easing: cubicOut }}
	out:scale={{ start: 0.98, duration: 140, easing: cubicOut }}
>
	<section
		class="overflow-hidden rounded-lg border border-amber-300 bg-white text-gray-800 shadow-xl shadow-amber-900/10 dark:border-amber-800 dark:bg-gray-900 dark:text-gray-100"
		aria-live="assertive"
	>
		<header
			class="flex items-center gap-3 border-b border-amber-200 bg-amber-50/90 px-4 py-3 dark:border-amber-900 dark:bg-amber-950/30"
		>
			<span class="flex size-8 shrink-0 items-center justify-center text-amber-700 dark:text-amber-400">
				<LucideIcon name="shield-alert" className="size-7" strokeWidth="1.8" />
			</span>
			<div class="min-w-0">
				<div class="text-base font-semibold sm:text-lg">Hermes 需要你的授权</div>
				<div class="text-xs text-amber-800/80 dark:text-amber-300/80">
					该操作尚未执行，选择后原任务会继续
				</div>
			</div>
		</header>

		<div class="space-y-3 px-4 py-3">
			{#if approval.description}
				<p class="text-sm leading-5 text-gray-600 dark:text-gray-300">{approval.description}</p>
			{/if}

			{#if approval.command}
				<div>
					<div class="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">待执行操作</div>
					<pre
						class="max-h-40 overflow-auto whitespace-pre-wrap break-all rounded-md bg-gray-950 px-3 py-2 text-xs leading-5 text-gray-100"
					>{approval.command}</pre>
				</div>
			{/if}

			<div class="grid gap-2 sm:grid-cols-2">
				{#each choices as choice}
					{@const info = optionInfo[choice]}
					{#if info}
						<button
							type="button"
							class="flex items-start gap-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 text-left transition focus:outline-none focus:ring-2 focus:ring-amber-500/40 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-gray-800 {info.tone}"
							{disabled}
							on:click={() => dispatch('submit', { approval, choice })}
						>
							<span class="mt-0.5 text-amber-700 dark:text-amber-400">
								<LucideIcon name={info.icon} className="size-5" strokeWidth="1.9" />
							</span>
							<span class="min-w-0">
								<span class="block text-sm font-semibold">{info.label}</span>
								<span class="block text-xs leading-4 text-gray-500 dark:text-gray-400">
									{info.description}
								</span>
							</span>
						</button>
					{/if}
				{/each}
			</div>

			{#if disabled}
				<div class="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400">
					<LucideIcon name="loader-circle" className="size-4 animate-spin" strokeWidth="2" />
					正在提交审批结果……
				</div>
			{/if}
		</div>
	</section>
</div>
