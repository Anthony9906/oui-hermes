<script lang="ts">
	import { getContext } from 'svelte';

	import {
		WEBUI_NAME,
		banners,
		chatId,
		config,
		mobile,
		mobileModeOverride,
		settings,
		showControls,
		showSidebar,
		temporaryChatEnabled,
		user
	} from '$lib/stores';

	import { slide } from 'svelte/transition';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	import ShareChatModal from '../chat/ShareChatModal.svelte';
	import ModelSelector from '../chat/ModelSelector.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Menu from '$lib/components/layout/Navbar/Menu.svelte';
	import AdjustmentsHorizontal from '../icons/AdjustmentsHorizontal.svelte';

	import PencilSquare from '../icons/PencilSquare.svelte';
	import Banner from '../common/Banner.svelte';
	import Sidebar from '../icons/Sidebar.svelte';

	import ChatBubbleDotted from '../icons/ChatBubbleDotted.svelte';
	import ChatBubbleDottedChecked from '../icons/ChatBubbleDottedChecked.svelte';

	import EllipsisHorizontal from '../icons/EllipsisHorizontal.svelte';
	import LucideIcon from '$lib/components/expert-agents/LucideIcon.svelte';
	import ChatPlus from '../icons/ChatPlus.svelte';
	import ChatCheck from '../icons/ChatCheck.svelte';
	import { aguiPanelVisible, aguiStore, hasArtifact } from '$lib/agui/stores/agui';
	import { closeExpertAgentDrawer, showExpertAgentDrawer } from '$lib/stores/expertAgents';
	import { isAguiPanelTopmost } from './chatSidePanelState';

	const i18n = getContext('i18n');

	export let initNewChat: Function;
	export let shareEnabled: boolean = false;
	export let scrollTop = 0;
	$: void scrollTop;

	export let chat;
	export let history;
	export let selectedModels;
	export let showModelSelector = true;

	export let onSaveTempChat: () => {};
	$: void onSaveTempChat;
	export let archiveChatHandler: (id: string) => void;
	export let moveChatHandler: (id: string, folderId: string) => void;

	let closedBannerIds = [];

	let showShareChatModal = false;
	let showDownloadChatModal = false;
	$: aguiPanelTopmost = isAguiPanelTopmost($aguiPanelVisible, $showExpertAgentDrawer);

	const toggleAguiPanel = () => {
		if ($showExpertAgentDrawer) {
			aguiStore.showPanel();
			closeExpertAgentDrawer();
			return;
		}

		aguiStore.togglePanel();
	};

	const toggleResponsiveMode = () => {
		const nextMobile = !$mobile;

		mobileModeOverride.set(nextMobile);
		localStorage.mobileModeOverride = nextMobile ? 'mobile' : 'desktop';
		mobile.set(nextMobile);
		showSidebar.set(false);

		if (nextMobile) {
			showControls.set(false);
		}
	};
</script>

<ShareChatModal bind:show={showShareChatModal} chatId={$chatId} />

<button
	id="new-chat-button"
	class="hidden"
	on:click={() => {
		initNewChat();
	}}
	aria-label="New Chat"
></button>

<nav
	class="sticky top-0 z-30 w-full {chat?.id
		? 'pt-0.5 pb-1'
		: 'pt-1 pb-1'} -mb-12 flex flex-col items-center drag-region"
>
	<div class="flex items-center w-full pl-1.5 pr-1">
		<div
			id="navbar-bg-gradient-to-b"
			class="{chat?.id
				? 'visible'
				: 'invisible'} bg-transparent pointer-events-none absolute inset-0 -bottom-10 z-[-1]"
		></div>

		<div class=" flex max-w-full w-full mx-auto px-1.5 md:px-2 pt-0.5 bg-transparent">
			<div class="flex items-center w-full max-w-full">
				{#if $mobile && !$showSidebar}
					<div
						class="-translate-x-0.5 mr-1 mt-1 self-start flex flex-none items-center text-gray-600 dark:text-gray-400"
					>
						<Tooltip content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}>
							<button
								class=" cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
								on:click={() => {
									showSidebar.set(!$showSidebar);
								}}
							>
								<div class=" self-center p-1.5">
									<Sidebar />
								</div>
							</button>
						</Tooltip>
					</div>
				{/if}

				<div
					class="flex-1 overflow-hidden max-w-full mt-0.5 py-0.5
			{$showSidebar ? 'ml-1' : ''}
			"
				>
					{#if showModelSelector}
						<div class="flex items-start">
							<ModelSelector bind:selectedModels showSetDefault={false} />
						</div>
					{/if}
				</div>

				<div class="self-start flex flex-none items-center text-gray-600 dark:text-gray-400">
					<button
						type="button"
						class="no-drag-region mr-2 flex shrink-0 translate-y-[10px] rounded-md transition hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-blue-500/40 sm:mr-10"
						on:click={toggleResponsiveMode}
						aria-label={$mobile ? 'Switch to desktop mode' : 'Switch to mobile mode'}
					>
						<img
							src="/assets/images/cowain-logo-blue.png"
							alt="Cowain"
							class="h-[1.4rem] w-auto select-none object-contain"
							draggable="false"
						/>
					</button>

					<!-- <div class="md:hidden flex self-center w-[1px] h-5 mx-2 bg-gray-300 dark:bg-stone-700" /> -->

					{#if $mobile && !$temporaryChatEnabled && chat && chat.id}
						<Tooltip content={$i18n.t('New Chat')}>
							<button
								type="button"
								class=" flex {$showSidebar
									? 'md:hidden'
									: ''} mr-2 h-10 w-10 translate-y-[10px] cursor-pointer items-center justify-center rounded-xl border border-transparent text-gray-600 transition hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-850"
								on:click={() => {
									initNewChat();
								}}
								aria-label="New Chat"
							>
								<ChatPlus className="size-5" strokeWidth="1.5" />
							</button>
						</Tooltip>
					{/if}

					{#if shareEnabled && chat && (chat.id || $temporaryChatEnabled)}
						<Menu
							{chat}
							{shareEnabled}
							shareHandler={() => {
								showShareChatModal = !showShareChatModal;
							}}
							archiveChatHandler={() => {
								archiveChatHandler(chat.id);
							}}
							{moveChatHandler}
						>
							<button
								type="button"
								class="flex h-10 w-10 translate-y-[10px] cursor-pointer items-center justify-center rounded-xl border border-transparent transition hover:bg-gray-50 dark:hover:bg-gray-850"
								id="chat-context-menu-button"
								aria-label="打开对话菜单"
							>
								<EllipsisHorizontal className="size-5" strokeWidth="1.5" />
							</button>
						</Menu>
					{/if}

					{#if $hasArtifact}
						<Tooltip content={aguiPanelTopmost ? '隐藏制品预览' : '显示制品预览'}>
							<button
								type="button"
								class="ml-2 flex h-10 w-10 translate-y-[10px] cursor-pointer items-center justify-center rounded-xl border transition {aguiPanelTopmost
									? 'border-blue-200 bg-blue-50 text-blue-600 dark:border-blue-700/60 dark:bg-blue-900/30 dark:text-blue-200'
									: 'border-transparent hover:bg-gray-50 dark:hover:bg-gray-850'}"
								aria-label={aguiPanelTopmost ? '隐藏制品预览' : '显示制品预览'}
								aria-pressed={aguiPanelTopmost}
								on:click={toggleAguiPanel}
							>
								<LucideIcon name="sparkles" className="size-6" strokeWidth="1.45" />
							</button>
						</Tooltip>
					{/if}
				</div>
			</div>
		</div>
	</div>

	<div class="absolute top-[100%] left-0 right-0 h-fit">
		{#if !history.currentId && !$chatId && ($banners.length > 0 || ($config?.license_metadata?.type ?? null) === 'trial' || (($config?.license_metadata?.seats ?? null) !== null && $config?.user_count > $config?.license_metadata?.seats))}
			<div class=" w-full z-30">
				<div class=" flex flex-col gap-1 w-full">
					{#if ($config?.license_metadata?.type ?? null) === 'trial'}
						<Banner
							banner={{
								type: 'info',
								title: 'Trial License',
								content: $i18n.t(
									'You are currently using a trial license. Please contact support to upgrade your license.'
								)
							}}
						/>
					{/if}

					{#if ($config?.license_metadata?.seats ?? null) !== null && $config?.user_count > $config?.license_metadata?.seats}
						<Banner
							banner={{
								type: 'error',
								title: 'License Error',
								content: $i18n.t(
									'Exceeded the number of seats in your license. Please contact support to increase the number of seats.'
								)
							}}
						/>
					{/if}

					{#each $banners.filter((b) => ![...JSON.parse(localStorage.getItem('dismissedBannerIds') ?? '[]'), ...closedBannerIds].includes(b.id)) as banner (banner.id)}
						<Banner
							{banner}
							on:dismiss={(e) => {
								const bannerId = e.detail;

								if (banner.dismissible) {
									localStorage.setItem(
										'dismissedBannerIds',
										JSON.stringify(
											[
												bannerId,
												...JSON.parse(localStorage.getItem('dismissedBannerIds') ?? '[]')
											].filter((id) => $banners.find((b) => b.id === id))
										)
									);
								} else {
									closedBannerIds = [...closedBannerIds, bannerId];
								}
							}}
						/>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</nav>
