<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { cubicOut } from 'svelte/easing';
	import { fly, scale } from 'svelte/transition';

	import type { HermesApprovalChoice } from '$lib/apis/hermes-runs';
	import LucideIcon from '$lib/components/expert-agents/LucideIcon.svelte';
	import type { HermesApprovalRequest } from '../stores/approvals';
	import { getAgentApprovalExplanation } from '../utils';

	const dispatch = createEventDispatcher<{
		submit: { approval: HermesApprovalRequest; choice: HermesApprovalChoice };
	}>();

	export let approval: HermesApprovalRequest;
	export let disabled = false;

	let allowForSession = false;
	let activeApprovalId = '';

	$: choices = new Set<HermesApprovalChoice>(
		approval?.choices?.length ? approval.choices : ['once', 'session', 'deny']
	);
	$: canAllowOnce = choices.has('once');
	$: canAllowSession = choices.has('session');
	$: canDeny = choices.has('deny');
	$: explanation = getAgentApprovalExplanation(approval);
	$: if (approval?.approval_request_id !== activeApprovalId) {
		activeApprovalId = approval?.approval_request_id ?? '';
		allowForSession = !canAllowOnce && canAllowSession;
	}

	const submitAllow = () => {
		const choice: HermesApprovalChoice = allowForSession && canAllowSession ? 'session' : 'once';
		dispatch('submit', { approval, choice });
	};
</script>

<div
	class="mx-auto w-full max-w-3xl px-3 sm:px-4"
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
			<span
				class="flex size-8 shrink-0 items-center justify-center text-amber-700 dark:text-amber-400"
			>
				<LucideIcon name="shield-alert" className="size-7" strokeWidth="1.8" />
			</span>
			<div class="min-w-0">
				<div class="text-base font-semibold sm:text-lg">Agent 需要你的授权</div>
				<div class="text-xs text-amber-800/80 dark:text-amber-300/80">
					该操作尚未执行。请核对风险说明和命令后再选择。
				</div>
			</div>
		</header>

		<div class="space-y-3 px-4 py-3">
			<div>
				<div class="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">风险说明</div>
				<p
					class="rounded-md border border-amber-200 bg-amber-50/60 px-3 py-2 text-sm leading-5 text-gray-700 dark:border-amber-900/70 dark:bg-amber-950/20 dark:text-gray-200"
				>
					{explanation}
				</p>
			</div>

			{#if approval.command}
				<div>
					<div class="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
						Agent 准备执行
					</div>
					<pre
						class="max-h-40 overflow-auto whitespace-pre-wrap break-all rounded-md bg-gray-950 px-3 py-2 text-xs leading-5 text-gray-100">{approval.command}</pre>
				</div>
			{/if}

			<div class="grid items-stretch gap-2 sm:grid-cols-2">
				{#if canAllowOnce || canAllowSession}
					<div
						class="rounded-lg border border-gray-200 bg-gray-50 transition hover:border-emerald-400 hover:bg-emerald-50 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-emerald-700 dark:hover:bg-emerald-950/20"
					>
						<button
							type="button"
							class="flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left focus:outline-none focus:ring-2 focus:ring-emerald-500/40 disabled:cursor-not-allowed disabled:opacity-60"
							{disabled}
							on:click={submitAllow}
						>
							<span class="mt-0.5 text-emerald-600 dark:text-emerald-400">
								<LucideIcon name="check" className="size-5" strokeWidth="2.2" />
							</span>
							<span class="min-w-0">
								<span class="block text-sm font-semibold">
									{allowForSession ? '本对话期间允许' : '仅本次允许'}
								</span>
								<span class="block text-xs leading-4 text-gray-500 dark:text-gray-400">
									{allowForSession ? '允许本对话中的同类操作' : '只允许当前这一次操作'}
								</span>
							</span>
						</button>

						{#if canAllowSession}
							<label
								class="mx-3 mb-3 flex cursor-pointer items-start gap-2 border-t border-gray-200 pt-2 text-xs dark:border-gray-700"
							>
								<input
									type="checkbox"
									class="mt-0.5 size-4 rounded border-gray-300 accent-emerald-600"
									bind:checked={allowForSession}
									{disabled}
								/>
								<span>
									<span class="block font-medium text-gray-700 dark:text-gray-200"
										>本对话期间允许同类操作</span
									>
									<span class="mt-0.5 block leading-4 text-gray-500 dark:text-gray-400">
										勾选后，本对话内遇到相同安全规则时不再询问。
									</span>
								</span>
							</label>
						{/if}
					</div>
				{/if}

				{#if canDeny}
					<button
						type="button"
						class="flex items-start gap-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 text-left transition hover:border-red-400 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500/40 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-gray-800 dark:hover:bg-red-950/30"
						{disabled}
						on:click={() => dispatch('submit', { approval, choice: 'deny' })}
					>
						<span class="mt-0.5 text-red-600 dark:text-red-400">
							<LucideIcon name="ban" className="size-5" strokeWidth="1.9" />
						</span>
						<span class="min-w-0">
							<span class="block text-sm font-semibold">拒绝</span>
							<span class="block text-xs leading-4 text-gray-500 dark:text-gray-400">
								不执行该操作，Agent 将收到明确的拒绝结果
							</span>
						</span>
					</button>
				{/if}
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
