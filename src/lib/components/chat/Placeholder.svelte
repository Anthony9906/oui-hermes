<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';

	import { onMount, getContext, tick, createEventDispatcher } from 'svelte';
	import { blur, fade } from 'svelte/transition';

	const dispatch = createEventDispatcher();

	import { getChatList } from '$lib/apis/chats';
	import { updateFolderById } from '$lib/apis/folders';

	import {
		config,
		user,
		models as _models,
		temporaryChatEnabled,
		selectedFolder,
		chats,
		currentChatPage
	} from '$lib/stores';
	import { sanitizeResponseContent, extractCurlyBraceWords } from '$lib/utils';

	import Suggestions from './Suggestions.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EyeSlash from '$lib/components/icons/EyeSlash.svelte';
	import MessageInput from './MessageInput.svelte';
	import FolderPlaceholder from './Placeholder/FolderPlaceholder.svelte';
	import FolderTitle from './Placeholder/FolderTitle.svelte';

	const i18n = getContext('i18n');

	export let createMessagePair: Function;
	export let stopResponse: Function;

	export let autoScroll = false;

	export let atSelectedModel: Model | undefined;
	export let selectedModels: [''];

	export let history;

	export let prompt = '';
	export let files = [];
	export let messageInput = null;

	export let selectedToolIds = [];
	export let selectedFilterIds = [];
	export let pendingOAuthTools = [];

	export let showCommands = false;

	export let imageGenerationEnabled = false;
	export let codeInterpreterEnabled = false;
	export let webSearchEnabled = false;

	export let onUpload: Function = (e) => {};
	export let onSelect = (e) => {};
	export let onChange = (e) => {};

	export let toolServers = [];

	export let dragged = false;

	let models = [];
	let selectedModelIdx = 0;

	$: if (selectedModels.length > 0) {
		selectedModelIdx = models.length - 1;
	}

	$: models = selectedModels.map((id) => $_models.find((m) => m.id === id));
</script>

<div class="flex h-full w-full flex-col items-center px-5 pb-7 pt-10 text-center @2xl:px-20">
	{#if $temporaryChatEnabled}
		<Tooltip
			content={$i18n.t("This chat won't appear in history and your messages will not be saved.")}
			className="w-full flex justify-center mb-0.5"
			placement="top"
		>
			<div class="flex items-center gap-2 text-gray-500 text-base my-2 w-fit">
				<EyeSlash strokeWidth="2.5" className="size-4" />{$i18n.t('Temporary Chat')}
			</div>
		</Tooltip>
	{/if}

	<div
		class="flex w-full flex-1 items-start justify-center pt-[clamp(3.5rem,10vh,6rem)] text-center text-3xl text-[#071f4d] dark:text-gray-100 font-primary"
	>
		<div class="w-full flex flex-col justify-center items-center">
			{#if $selectedFolder}
				<FolderTitle
					folder={$selectedFolder}
					onUpdate={async (folder) => {
						await chats.set(await getChatList(localStorage.token, $currentChatPage));
						currentChatPage.set(1);
					}}
					onDelete={async () => {
						await chats.set(await getChatList(localStorage.token, $currentChatPage));
						currentChatPage.set(1);

						selectedFolder.set(null);
					}}
				/>
			{:else}
				<div class="flex flex-col justify-center items-center gap-4 w-full px-5 max-w-5xl">
					<div
						class="expert-agent-title flex items-center text-[2.75rem] @sm:text-[4.3rem] font-bold tracking-normal leading-none line-clamp-1"
						data-text={models[selectedModelIdx]?.name ??
							$i18n.t('Hello, {{name}}', { name: $user?.name })}
						in:fade={{ duration: 100 }}
					>
						{#if models[selectedModelIdx]?.name}
							<Tooltip
								content={models[selectedModelIdx]?.name}
								placement="top"
								className=" flex items-center "
							>
								<span class="line-clamp-1">
									{models[selectedModelIdx]?.name}
								</span>
							</Tooltip>
						{:else}
							{$i18n.t('Hello, {{name}}', { name: $user?.name })}
						{/if}
					</div>
				</div>

				<div class="flex mt-1 mb-2">
					<div in:fade={{ duration: 100, delay: 50 }}>
						{#if models[selectedModelIdx]?.info?.meta?.description ?? null}
							<Tooltip
								className=" w-fit"
								content={DOMPurify.sanitize(
									marked.parse(
										sanitizeResponseContent(
											models[selectedModelIdx]?.info?.meta?.description ?? ''
										).replaceAll('\n', '<br>')
									)
								)}
								placement="top"
							>
								<div
									class="expert-agent-subtitle mt-1 w-full max-w-[42rem] break-words px-2 text-[1.75rem] @sm:text-[1.875rem] @4xl:max-w-[64rem] @4xl:text-[2rem] leading-tight text-[#52617e] dark:text-gray-300 line-clamp-2 markdown"
								>
									{@html DOMPurify.sanitize(
										marked.parse(
											sanitizeResponseContent(
												models[selectedModelIdx]?.info?.meta?.description ?? ''
											).replaceAll('\n', '<br>')
										)
									)}
								</div>
							</Tooltip>

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
						{/if}
					</div>
				</div>
			{/if}

			{#if $selectedFolder}
				<div
					class="mx-auto px-4 md:max-w-3xl md:px-6 font-primary min-h-62"
					in:fade={{ duration: 200, delay: 200 }}
				>
					<FolderPlaceholder folder={$selectedFolder} />
				</div>
			{:else}
				<div
					class="mx-auto mt-[clamp(4rem,10vh,6.25rem)] w-full max-w-5xl font-primary"
					in:fade={{ duration: 200, delay: 200 }}
				>
					<div class="mx-5">
						<Suggestions
							suggestionPrompts={atSelectedModel?.info?.meta?.suggestion_prompts ??
								models[selectedModelIdx]?.info?.meta?.suggestion_prompts ??
								$config?.default_prompt_suggestions ??
								[]}
							inputValue={prompt}
							{onSelect}
						/>
					</div>
				</div>
			{/if}
		</div>
	</div>

	<div class="w-full max-w-5xl shrink-0 text-base font-normal {atSelectedModel ? 'mt-2' : ''}">
		<MessageInput
			bind:this={messageInput}
			{history}
			{selectedModels}
			bind:files
			bind:prompt
			bind:autoScroll
			bind:selectedToolIds
			bind:selectedFilterIds
			bind:imageGenerationEnabled
			bind:codeInterpreterEnabled
			bind:webSearchEnabled
			bind:atSelectedModel
			bind:showCommands
			bind:dragged
			{pendingOAuthTools}
			{toolServers}
			{stopResponse}
			{createMessagePair}
			placeholder={$i18n.t('How can I help you today?')}
			{onChange}
			{onUpload}
			on:submit={(e) => {
				dispatch('submit', e.detail);
			}}
		/>
	</div>
</div>

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
		font-weight: 400;
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
