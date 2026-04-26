<script lang="ts">
	import type { ExpertSkillCard } from '$lib/apis/expert-agents';

	export let skill: ExpertSkillCard;
	export let onStart: (skill: ExpertSkillCard) => void = () => {};
</script>

<div
	class="flex min-h-44 flex-col rounded-2xl border border-gray-200 bg-white p-4 shadow-xs dark:border-gray-800 dark:bg-gray-900"
>
	<div class="text-sm font-semibold text-gray-900 dark:text-gray-100">{skill.skill_name}</div>

	<div class="mt-3 flex-1 whitespace-pre-wrap text-sm leading-6 text-gray-600 dark:text-gray-400">
		{skill.description || '暂无描述'}
	</div>

	<div class="mt-4 flex justify-end">
		<button
			type="button"
			class="rounded-xl bg-gray-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-gray-700 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300"
			on:click={() => onStart(skill)}
		>
			开始会话
		</button>
	</div>
</div>
