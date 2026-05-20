<script context="module" lang="ts">
	let savedTab: 'files' | 'overview' | 'expertAgents' = 'overview';
</script>

<script lang="ts">
	import { goto } from '$app/navigation';
	import { SvelteFlowProvider } from '@xyflow/svelte';
	import { fly } from 'svelte/transition';
	import { Pane, PaneResizer } from 'paneforge';
	import { v4 as uuidv4 } from 'uuid';

	import { onDestroy, onMount, tick, getContext } from 'svelte';
	import {
		config,
		terminalServers,
		mobile,
		showControls,
		showCallOverlay,
		showArtifacts,
		showEmbeds,
		settings,
		showFileNavPath,
		selectedTerminalId,
		user
	} from '$lib/stores';

	import { uploadFile } from '$lib/apis/files';
	import type { ExpertSkillCard } from '$lib/apis/expert-agents';
	import { toast } from 'svelte-sonner';

	import CallOverlay from './MessageInput/CallOverlay.svelte';
	import Drawer from '../common/Drawer.svelte';
	import Artifacts from './Artifacts.svelte';
	import Embeds from './ChatControls/Embeds.svelte';
	import FileNav from './FileNav.svelte';
	import Overview from './Overview.svelte';
	import ExpertAgentDrawer from '$lib/components/expert-agents/ExpertAgentDrawer.svelte';
	import { closeExpertAgentDrawer, showExpertAgentDrawer } from '$lib/stores/expertAgents';

	const i18n = getContext('i18n');

	export let history;

	export let chatId = null;

	export let chatFiles = [];
	$: void chatFiles;

	export let eventTarget: EventTarget;
	export let submitPrompt: Function;
	export let stopResponse: Function;
	export let showMessage: Function;
	export let files;
	export let modelId;

	export let codeInterpreterEnabled = false;

	export let pane: Pane | null = null;

	let largeScreen = false;
	let dragged = false;
	let minSize = 0;
	let paneReady = false;
	const defaultPaneWidth = 420;
	const expertAgentPaneWidth = 580;

	// Tab state for the Hermes context panel
	let activeTab = savedTab;
	// svelte-ignore reactive_declaration_module_script_dependency
	$: {
		savedTab = activeTab;
	}

	$: hasMessages = history?.messages && Object.keys(history.messages).length > 0;

	$: showFilesTab =
		($selectedTerminalId &&
			(($terminalServers ?? []).some((t) => t.id && t.id === $selectedTerminalId) ||
				$user?.role === 'admin' ||
				($user?.permissions?.features?.direct_tool_servers ?? true))) ||
		(codeInterpreterEnabled && $config?.code?.interpreter_engine !== 'jupyter');
	$: showOverviewTab = hasMessages;
	$: showExpertAgentTab = !largeScreen && $showExpertAgentDrawer;

	const firstVisibleTab = () => {
		if (showFilesTab) activeTab = 'files';
		else if (showOverviewTab) activeTab = 'overview';
		else if (showExpertAgentTab) activeTab = 'expertAgents';
	};

	// Tab fallback: if active tab becomes hidden, switch to a visible Hermes context tab.
	$: if (
		(activeTab === 'overview' && !showOverviewTab) ||
		(activeTab === 'files' && !showFilesTab) ||
		(activeTab === 'expertAgents' && !showExpertAgentTab)
	) {
		firstVisibleTab();
	}

	// Auto-close if there are no visible context tabs and no full-screen panel is active.
	$: if (
		!$showCallOverlay &&
		!$showArtifacts &&
		!$showEmbeds &&
		!showFilesTab &&
		!showOverviewTab &&
		!showExpertAgentTab
	) {
		closePanel();
	}

	$: if (!largeScreen && $showExpertAgentDrawer) {
		activeTab = 'expertAgents';
		showControls.set(true);
	}

	$: if (paneReady && $showControls && pane && largeScreen) {
		const container = document.getElementById('chat-container');
		if (container) {
			minSize = getMinPaneSize(container);
			if (activeTab === 'expertAgents' && pane.isExpanded() && pane.getSize() < minSize) {
				pane.resize(minSize);
			}
		}
	}

	// Auto-switch to Files tab when display_file is triggered
	$: if ($showFileNavPath) {
		activeTab = 'files';
		showControls.set(true);
	}

	// Auto-open Files tab when a terminal is selected (suppress panel open when full-screen)
	$: if ($selectedTerminalId && showFilesTab) {
		activeTab = 'files';
		if (largeScreen) {
			showControls.set(true);
		}
	}

	// Clear selected direct terminal if user lost permission
	$: if (
		$selectedTerminalId &&
		!($terminalServers ?? []).some((t) => t.id && t.id === $selectedTerminalId) &&
		!($user?.role === 'admin' || ($user?.permissions?.features?.direct_tool_servers ?? true))
	) {
		selectedTerminalId.set(null);
	}

	// Attach a terminal file to the chat input
	const handleTerminalAttach = async (blob: Blob, name: string, contentType: string) => {
		const tempItemId = uuidv4();
		const fileItem = {
			type: 'file',
			file: '',
			id: null,
			url: '',
			name,
			collection_name: '',
			status: 'uploading',
			error: '',
			itemId: tempItemId,
			size: blob.size
		};

		files = [...files, fileItem];

		try {
			const file = new File([blob], name, { type: contentType || 'application/octet-stream' });
			const uploaded = await uploadFile(localStorage.token, file);
			if (!uploaded) throw new Error('Upload failed');

			const idx = files.findIndex((f) => f.itemId === tempItemId);
			if (idx !== -1) {
				files[idx] = {
					...fileItem,
					status: 'uploaded',
					file: uploaded,
					id: uploaded.id,
					url: `${uploaded.id}`,
					collection_name: uploaded?.meta?.collection_name
				};
				files = files;
			}
			toast.success($i18n.t('File attached to chat'));
		} catch (e) {
			files = files.filter((f) => f.itemId !== tempItemId);
			toast.error($i18n.t('Failed to attach file'));
		}
	};

	export const openPane = () => {
		const container = document.getElementById('chat-container');
		if (!pane || !container) return;

		const savedWidth = parseInt(localStorage?.chatControlsSize);
		if (savedWidth) {
			const targetWidth = Math.max(savedWidth, getPaneTargetWidth());
			let size = Math.floor((targetWidth / container.clientWidth) * 100);
			pane.resize(size);
		} else {
			pane.resize(minSize);
		}
	};

	const getPaneTargetWidth = () =>
		activeTab === 'expertAgents' ? expertAgentPaneWidth : defaultPaneWidth;

	const getMinPaneSize = (container: HTMLElement) => {
		const size = Math.floor((getPaneTargetWidth() / container.clientWidth) * 100);
		return Math.min(size, 62);
	};

	const handleMediaQuery = async (e) => {
		if (e.matches) {
			largeScreen = true;
			if ($showCallOverlay) {
				showCallOverlay.set(false);
				await tick();
				showCallOverlay.set(true);
			}
		} else {
			largeScreen = false;
			if ($showCallOverlay) {
				showCallOverlay.set(false);
				await tick();
				showCallOverlay.set(true);
			}
			pane = null;
		}
	};

	const onMouseDown = () => {
		dragged = true;
	};
	const onMouseUp = () => {
		dragged = false;
	};

	function closePanel() {
		showControls.set(false);
		if (!largeScreen) {
			closeExpertAgentDrawer();
			showArtifacts.set(false);
			showEmbeds.set(false);
			if ($showCallOverlay) showCallOverlay.set(false);
		}
	}

	async function startExpertAgentChat(skill: ExpertSkillCard) {
		const searchParams = new URLSearchParams({
			'expert-agent': skill.skill_name,
			'expert-agent-start': uuidv4()
		});

		await goto(`/?${searchParams.toString()}`);
		await tick();
		closePanel();
	}

	onMount(() => {
		const mediaQuery = window.matchMedia('(min-width: 1024px)');
		mediaQuery.addEventListener('change', handleMediaQuery);
		handleMediaQuery(mediaQuery);

		let resizeObserver: ResizeObserver | null = null;
		let isDestroyed = false;

		// Wait for Svelte to render the Pane after largeScreen changed
		const init = async () => {
			await tick();

			if (isDestroyed) return;

			// If controls were persisted as open, set the pane to the saved size
			if ($showControls && pane) {
				openPane();
			}

			setTimeout(() => {
				paneReady = true;
			}, 0);

			const container = document.getElementById('chat-container') as HTMLElement;
			if (!container) return;

			minSize = getMinPaneSize(container);
			resizeObserver = new ResizeObserver((entries) => {
				for (let entry of entries) {
					const width = entry.contentRect.width;
					minSize = Math.min(Math.floor((getPaneTargetWidth() / width) * 100), 62);
					if ($showControls) {
						if (pane && pane.isExpanded() && pane.getSize() < minSize) {
							pane.resize(minSize);
						} else {
							let size = Math.floor(
								(parseInt(localStorage?.chatControlsSize) / container.clientWidth) * 100
							);
							if (size < minSize && pane) pane.resize(minSize);
						}
					}
				}
			});
			resizeObserver.observe(container);
		};
		init();

		document.addEventListener('mousedown', onMouseDown);
		document.addEventListener('mouseup', onMouseUp);

		return () => {
			isDestroyed = true;
			paneReady = false;
			resizeObserver?.disconnect();
			if (!largeScreen) {
				closePanel();
			}
			mediaQuery.removeEventListener('change', handleMediaQuery);
			document.removeEventListener('mousedown', onMouseDown);
			document.removeEventListener('mouseup', onMouseUp);
		};
	});

	const closeHandler = () => {
		if (!largeScreen) {
			closePanel();
		}
		showEmbeds.set(false);
		if (!largeScreen) {
			showArtifacts.set(false);
			closeExpertAgentDrawer();
		}
		if ($showCallOverlay) showCallOverlay.set(false);
	};

	$: if (paneReady && !chatId) closeHandler();

	// Helper: is a "special" full-screen panel active?
	$: specialPanel = $showCallOverlay || $showEmbeds;
</script>

{#if !largeScreen}
	{#if $showControls}
		<Drawer
			show={$showControls}
			onClose={closePanel}
			className="min-h-[100dvh] !bg-white dark:!bg-gray-850"
		>
			<div class="h-[100dvh] flex flex-col">
				{#if $showCallOverlay}
					<div
						class="h-full max-h-[100dvh] bg-white text-gray-700 dark:bg-black dark:text-gray-300 flex justify-center"
					>
						<CallOverlay
							bind:files
							{submitPrompt}
							{stopResponse}
							{modelId}
							{chatId}
							{eventTarget}
							on:close={closePanel}
						/>
					</div>
				{:else if $showEmbeds}
					<Embeds />
				{:else if $showArtifacts}
					<Artifacts {history} />
				{:else}
					<!-- Hermes context tabs -->
					<div class="flex flex-col h-full min-h-0">
						<!-- Tab bar -->
						<div class="flex items-center justify-between px-2 pt-2 pb-2 shrink-0">
							<div class="flex gap-1 min-w-0 overflow-x-auto scrollbar-hidden">
								{#if showFilesTab}
									<button
										class="px-2.5 py-1 text-sm rounded-lg transition whitespace-nowrap {activeTab ===
										'files'
											? 'bg-gray-100 dark:bg-gray-800 font-medium text-gray-900 dark:text-white'
											: 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
										on:click={() => (activeTab = 'files')}
									>
										{$i18n.t('Files')}
									</button>
								{/if}
								{#if showOverviewTab}
									<button
										class="px-2.5 py-1 text-sm rounded-lg transition whitespace-nowrap {activeTab ===
										'overview'
											? 'bg-gray-100 dark:bg-gray-800 font-medium text-gray-900 dark:text-white'
											: 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
										on:click={() => (activeTab = 'overview')}
									>
										{$i18n.t('Overview')}
									</button>
								{/if}
								{#if showExpertAgentTab}
									<button
										class="px-2.5 py-1 text-sm rounded-lg transition whitespace-nowrap {activeTab ===
										'expertAgents'
											? 'bg-gray-100 dark:bg-gray-800 font-medium text-gray-900 dark:text-white'
											: 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
										on:click={() => (activeTab = 'expertAgents')}
									>
										Expert Agent
									</button>
								{/if}
							</div>
							<button
								class="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition text-gray-500 dark:text-gray-400"
								on:click={closePanel}
								aria-label={$i18n.t('Close')}
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="1.5"
									class="size-4"
								>
									<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
								</svg>
							</button>
						</div>

						<div
							class="flex-1 min-h-0 {activeTab === 'overview'
								? 'h-full'
								: activeTab === 'expertAgents'
									? 'h-full'
									: ''}"
						>
							{#if activeTab === 'overview'}
								<Overview
									{history}
									onNodeClick={(e) => {
										const node = e.node;
										showMessage(node.data.message, true);
									}}
									onClose={() => showControls.set(false)}
								/>
							{:else if activeTab === 'expertAgents'}
								<ExpertAgentDrawer
									show={$showExpertAgentDrawer}
									on:start={(event) => {
										void startExpertAgentChat(event.detail);
									}}
									on:close={closePanel}
								/>
							{:else if activeTab === 'files' && $selectedTerminalId}
								<FileNav onAttach={handleTerminalAttach} {chatId} />
							{/if}
						</div>
					</div>
				{/if}
			</div>
		</Drawer>
	{/if}
{:else}
	{#if $showControls}
		<PaneResizer
			class="relative z-20 flex items-center justify-center border-l border-transparent transition hover:border-gray-200/80 dark:hover:border-gray-800"
			id="controls-resizer"
		>
			<div
				class="absolute -left-1.5 -right-1.5 -top-0 -bottom-0 z-20 cursor-col-resize bg-transparent"
			></div>
		</PaneResizer>
	{/if}

	<Pane
		bind:pane
		defaultSize={0}
		onResize={(size) => {
			if ($showControls && pane.isExpanded()) {
				if (size < minSize) pane.resize(minSize);
				if (size < minSize) {
					localStorage.chatControlsSize = 0;
				} else {
					const container = document.getElementById('chat-container');
					localStorage.chatControlsSize = Math.floor((size / 100) * container.clientWidth);
				}
			}
		}}
		onCollapse={() => {
			if (paneReady) closePanel();
		}}
		collapsible={true}
		id="context-panel-pane"
		class="z-10 bg-transparent {dragged
			? ''
			: 'transition-[flex-basis,width] duration-300 ease-out'}"
	>
		{#if $showControls}
			<div class="flex h-full max-h-full min-h-0">
				<div
					in:fly={{ x: 56, duration: 320, opacity: 0.72 }}
					out:fly={{ x: 44, duration: 220, opacity: 0.62 }}
					class="context-panel-shell flex h-full min-h-0 w-full flex-col {specialPanel &&
					!$showCallOverlay
						? ' '
						: ''} z-40 pointer-events-auto overflow-hidden"
					id="controls-container"
				>
					{#if $showCallOverlay}
						<div class="w-full h-full flex justify-center">
							<CallOverlay
								bind:files
								{submitPrompt}
								{stopResponse}
								{modelId}
								{chatId}
								{eventTarget}
								on:close={closePanel}
							/>
						</div>
					{:else if $showEmbeds}
						<Embeds overlay={dragged} />
					{:else}
						<!-- Hermes context tabs -->
						<div class="flex flex-col h-full min-h-0">
							<!-- Tab bar -->
							<div class="context-panel-header flex items-center justify-between shrink-0">
								<div class="min-w-0 pr-2">
									<div class="text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-400">
										Context Panel
									</div>
								</div>
								<div class="flex gap-1 min-w-0 overflow-x-auto scrollbar-hidden">
									{#if showFilesTab}
										<button
											class="context-panel-tab {activeTab === 'files'
												? 'context-panel-tab-active'
												: 'context-panel-tab-idle'}"
											on:click={() => (activeTab = 'files')}
										>
											{$i18n.t('Files')}
										</button>
									{/if}
									{#if showOverviewTab}
										<button
											class="context-panel-tab {activeTab === 'overview'
												? 'context-panel-tab-active'
												: 'context-panel-tab-idle'}"
											on:click={() => (activeTab = 'overview')}
										>
											{$i18n.t('Overview')}
										</button>
									{/if}
									{#if showExpertAgentTab}
										<button
											class="context-panel-tab {activeTab === 'expertAgents'
												? 'context-panel-tab-active'
												: 'context-panel-tab-idle'}"
											on:click={() => (activeTab = 'expertAgents')}
										>
											Expert Agent
										</button>
									{/if}
								</div>
								<button
									class="context-panel-close"
									on:click={closePanel}
									aria-label={$i18n.t('Close')}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										stroke-width="1.5"
										class="size-4"
									>
										<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
									</svg>
								</button>
							</div>

							<div
								class="flex-1 min-h-0 overflow-hidden {activeTab === 'overview'
									? 'h-full'
									: activeTab === 'expertAgents'
										? 'h-full'
										: ''}"
							>
								{#if activeTab === 'overview'}
									<Overview
										{history}
										onNodeClick={(e) => {
											const node = e.node;
											if (node?.data?.message?.favorite) {
												history.messages[node.data.message.id].favorite = true;
											} else {
												history.messages[node.data.message.id].favorite = null;
											}
											showMessage(node.data.message, true);
										}}
										onClose={() => showControls.set(false)}
									/>
								{:else if activeTab === 'expertAgents'}
									<ExpertAgentDrawer
										show={$showExpertAgentDrawer}
										on:start={(event) => {
											void startExpertAgentChat(event.detail);
										}}
										on:close={closePanel}
									/>
								{:else if activeTab === 'files' && $selectedTerminalId}
									<FileNav onAttach={handleTerminalAttach} overlay={dragged} {chatId} />
								{/if}
							</div>
						</div>
					{/if}
				</div>
			</div>
		{/if}
	</Pane>
{/if}

<style>
	.context-panel-shell {
		height: 100%;
		min-height: 0;
		background: linear-gradient(
			180deg,
			rgba(245, 248, 252, 0.98) 0%,
			rgba(238, 237, 242, 0.98) 100%
		);
		border-left: 1px solid rgba(213, 219, 231, 0.92);
		box-shadow:
			-24px 0 46px rgba(71, 79, 102, 0.1),
			-1px 0 0 rgba(255, 255, 255, 0.86) inset;
		overflow: hidden;
	}

	:global(#context-panel-pane) {
		overflow: visible !important;
		transition:
			flex-basis 300ms cubic-bezier(0.22, 1, 0.36, 1),
			width 300ms cubic-bezier(0.22, 1, 0.36, 1) !important;
	}

	.context-panel-header {
		gap: 0.75rem;
		padding: 0.75rem 0.875rem 0.625rem 1rem;
		border-bottom: 1px solid rgba(226, 231, 240, 0.92);
		background: rgba(255, 255, 255, 0.72);
		backdrop-filter: blur(18px);
	}

	.context-panel-tab {
		white-space: nowrap;
		border-radius: 0.625rem;
		padding: 0.375rem 0.625rem;
		font-size: 0.8125rem;
		font-weight: 500;
		line-height: 1.125rem;
		transition:
			background-color 160ms ease,
			color 160ms ease,
			box-shadow 160ms ease;
	}

	.context-panel-tab-active {
		background: #edf1f7;
		color: #293246;
		box-shadow: 0 1px 2px rgba(80, 90, 112, 0.08);
	}

	.context-panel-tab-idle {
		color: #7a8498;
	}

	.context-panel-tab-idle:hover {
		background: rgba(237, 241, 247, 0.72);
		color: #445066;
	}

	.context-panel-close {
		flex-shrink: 0;
		border-radius: 0.625rem;
		padding: 0.375rem;
		color: #7a8498;
		transition:
			background-color 160ms ease,
			color 160ms ease;
	}

	.context-panel-close:hover {
		background: rgba(237, 241, 247, 0.82);
		color: #293246;
	}

	:global(.dark) .context-panel-shell {
		background: linear-gradient(180deg, rgba(22, 27, 39, 0.98) 0%, rgba(17, 22, 33, 0.98) 100%);
		border-left-color: rgba(55, 65, 84, 0.9);
		box-shadow:
			-24px 0 46px rgba(0, 0, 0, 0.24),
			-1px 0 0 rgba(255, 255, 255, 0.04) inset;
	}

	:global(.dark) .context-panel-header {
		border-bottom-color: rgba(55, 65, 84, 0.84);
		background: rgba(22, 27, 39, 0.78);
	}

	:global(.dark) .context-panel-tab-active {
		background: rgba(55, 65, 84, 0.88);
		color: #f4f6fb;
	}

	:global(.dark) .context-panel-tab-idle {
		color: #9aa4b6;
	}

	:global(.dark) .context-panel-tab-idle:hover,
	:global(.dark) .context-panel-close:hover {
		background: rgba(55, 65, 84, 0.72);
		color: #f4f6fb;
	}

	@media (min-width: 768px) {
		:global(#chat-container:has(#context-panel-pane #controls-container)) {
			margin-right: 0 !important;
			max-width: calc(100vw - 20px) !important;
			border-top-right-radius: 0 !important;
			border-bottom-right-radius: 0 !important;
		}

		:global(
			.app:has(#sidebar[data-state='true'])
				#chat-container:has(#context-panel-pane #controls-container)
		) {
			max-width: calc(100vw - var(--sidebar-width) - 40px) !important;
		}
	}
</style>
