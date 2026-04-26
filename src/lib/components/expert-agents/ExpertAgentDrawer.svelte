<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { fade, fly } from 'svelte/transition';

	import { getExpertAgents, type ExpertSkillCard } from '$lib/apis/expert-agents';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import ExpertSkillCardComponent from './ExpertSkillCard.svelte';

	export let show = false;

	const dispatch = createEventDispatcher<{
		start: ExpertSkillCard;
		close: void;
	}>();

	let items: ExpertSkillCard[] = [];
	let loading = false;
	let loaded = false;
	let error: string | null = null;

	const close = () => {
		show = false;
		dispatch('close');
	};

	const loadExpertAgents = async () => {
		loading = true;
		error = null;

		try {
			items = await getExpertAgents(localStorage.token);
			loaded = true;
		} catch (err) {
			console.error(err);
			error = '无法加载专家技能';
		} finally {
			loading = false;
		}
	};

	$: if (show && !loaded && !loading) {
		void loadExpertAgents();
	}
</script>

{#if show}
	<div class="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true">
		<button
			type="button"
			class="absolute inset-0 bg-black/30 backdrop-blur-[1px]"
			aria-label="关闭专家面板"
			on:click={close}
			in:fade={{ duration: 120 }}
		/>

		<aside
			class="absolute bottom-0 right-0 top-0 flex w-full flex-col bg-gray-50 shadow-2xl outline-none dark:bg-gray-950 sm:w-[400px]"
			in:fly={{ x: 420, duration: 180 }}
			out:fly={{ x: 420, duration: 140 }}
		>
			<div
				class="flex items-start justify-between border-b border-gray-200 px-5 py-4 dark:border-gray-800"
			>
				<div>
					<div class="text-lg font-semibold text-gray-900 dark:text-gray-100">Expert Agent</div>
					<div class="mt-1 text-sm text-gray-500 dark:text-gray-400">选择一个专家技能开始会话</div>
				</div>

				<button
					type="button"
					class="rounded-xl p-2 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-900 dark:hover:text-gray-100"
					aria-label="关闭专家面板"
					on:click={close}
				>
					<XMark className="size-5" />
				</button>
			</div>

			<div class="flex-1 overflow-y-auto p-5">
				{#if loading}
					<div
						class="flex h-full flex-col items-center justify-center gap-3 text-sm text-gray-500 dark:text-gray-400"
					>
						<Spinner className="size-5" />
						<div>正在加载专家技能...</div>
					</div>
				{:else if error}
					<div class="flex h-full flex-col items-center justify-center text-center">
						<div class="text-base font-medium text-gray-900 dark:text-gray-100">
							无法加载专家技能
						</div>
						<button
							type="button"
							class="mt-4 rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-900"
							on:click={() => {
								loaded = false;
								void loadExpertAgents();
							}}
						>
							重试
						</button>
					</div>
				{:else if items.length === 0}
					<div class="flex h-full flex-col items-center justify-center text-center">
						<div class="text-base font-medium text-gray-900 dark:text-gray-100">
							还没有可用的专家技能
						</div>
						<div class="mt-2 max-w-64 text-sm text-gray-500 dark:text-gray-400">
							创建 Hermes Skill 后，它会显示在这里。
						</div>
					</div>
				{:else}
					<div class="space-y-4">
						{#each items as item (item.skill_name)}
							<ExpertSkillCardComponent
								skill={item}
								onStart={(skill) => {
									dispatch('start', skill);
								}}
							/>
						{/each}
					</div>
				{/if}
			</div>
		</aside>
	</div>
{/if}
