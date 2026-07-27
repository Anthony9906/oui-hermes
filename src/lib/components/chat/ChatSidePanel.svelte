<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount, tick } from 'svelte';
	import { v4 as uuidv4 } from 'uuid';

	import { showArtifacts } from '$lib/stores';
	import { closeExpertAgentDrawer, showExpertAgentDrawer } from '$lib/stores/expertAgents';
	import type { ExpertSkillCard } from '$lib/apis/expert-agents';

	import Drawer from '../common/Drawer.svelte';
	import Artifacts from './Artifacts.svelte';
	import AguiPanel from '$lib/agui/components/AguiPanel.svelte';
	import ExpertAgentDrawer from '$lib/components/expert-agents/ExpertAgentDrawer.svelte';
	import { aguiPanelVisible, aguiStore } from '$lib/agui/stores/agui';
	import {
		isChatSidePanelVisible,
		resolveChatBasePanel,
		type ChatBasePanel
	} from './chatSidePanelState';

	export let history;

	const MIN_WIDTH = 420;
	const MAX_WIDTH = 920;
	const DEFAULT_WIDTH = 800;
	const PANEL_EXIT_DURATION = 260;

	let largeScreen = false;
	let basePanel: ChatBasePanel = null;
	let previousArtifacts = false;
	let previousAgui = false;
	let panelWidth = DEFAULT_WIDTH;
	let isResizing = false;
	let startClientX = 0;
	let startWidth = DEFAULT_WIDTH;
	let activePointerId: number | null = null;
	let panelRendered = false;
	let panelEntered = false;
	let panelLifecycleReady = false;
	let previousPanelVisible = false;
	let panelAnimationFrame: number | null = null;
	let panelCloseTimer: number | null = null;
	let expertRendered = false;
	let expertEntered = false;
	let previousExpertVisible = false;
	let expertAnimationFrame: number | null = null;
	let expertCloseTimer: number | null = null;

	$: aguiVisible = $aguiPanelVisible;
	$: visible = isChatSidePanelVisible(basePanel, $showExpertAgentDrawer);

	const clearPanelAnimationHandles = () => {
		if (panelAnimationFrame !== null) {
			cancelAnimationFrame(panelAnimationFrame);
			panelAnimationFrame = null;
		}

		if (panelCloseTimer !== null) {
			window.clearTimeout(panelCloseTimer);
			panelCloseTimer = null;
		}
	};

	const syncPanelAnimation = async (shouldShow: boolean) => {
		clearPanelAnimationHandles();

		if (shouldShow) {
			if (!panelRendered) {
				panelRendered = true;
				panelEntered = false;
				await tick();
			}

			panelAnimationFrame = requestAnimationFrame(() => {
				panelEntered = true;
				panelAnimationFrame = null;
			});
			return;
		}

		if (!panelRendered) return;

		panelEntered = false;
		panelCloseTimer = window.setTimeout(() => {
			panelRendered = false;
			panelCloseTimer = null;
		}, PANEL_EXIT_DURATION);
	};

	const clearExpertAnimationHandles = () => {
		if (expertAnimationFrame !== null) {
			cancelAnimationFrame(expertAnimationFrame);
			expertAnimationFrame = null;
		}

		if (expertCloseTimer !== null) {
			window.clearTimeout(expertCloseTimer);
			expertCloseTimer = null;
		}
	};

	const syncExpertAnimation = async (shouldShow: boolean) => {
		clearExpertAnimationHandles();

		if (shouldShow) {
			if (!expertRendered) {
				expertRendered = true;
				expertEntered = false;
				await tick();
			}

			expertAnimationFrame = requestAnimationFrame(() => {
				expertEntered = true;
				expertAnimationFrame = null;
			});
			return;
		}

		if (!expertRendered) return;

		expertEntered = false;
		expertCloseTimer = window.setTimeout(() => {
			expertRendered = false;
			expertCloseTimer = null;
		}, PANEL_EXIT_DURATION);
	};

	$: if (panelLifecycleReady && visible !== previousPanelVisible) {
		previousPanelVisible = visible;
		void syncPanelAnimation(visible);
	}

	$: if (panelLifecycleReady && $showExpertAgentDrawer !== previousExpertVisible) {
		previousExpertVisible = $showExpertAgentDrawer;
		void syncExpertAnimation($showExpertAgentDrawer);
	}

	const clampWidth = (width: number) => {
		if (typeof window === 'undefined') return width;
		const maxViewportWidth = Math.max(MIN_WIDTH, window.innerWidth - 520);
		return Math.min(Math.min(MAX_WIDTH, maxViewportWidth), Math.max(MIN_WIDTH, width));
	};

	const applyPanelWidth = (width: number) => {
		panelWidth = clampWidth(width);
		document.documentElement.style.setProperty('--chat-side-panel-width', `${panelWidth}px`);
	};

	const resizeStartHandler = (event: PointerEvent) => {
		if (event.pointerType === 'mouse' && event.button !== 0) return;

		event.preventDefault();
		isResizing = true;
		activePointerId = event.pointerId;
		startClientX = event.clientX;
		startWidth = panelWidth;
		(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
		document.body.style.userSelect = 'none';
	};

	const resizeMoveHandler = (event: PointerEvent) => {
		if (!isResizing || event.pointerId !== activePointerId) return;
		event.preventDefault();
		applyPanelWidth(startWidth + startClientX - event.clientX);
	};

	const resizeEndHandler = (event?: PointerEvent) => {
		if (event && event.pointerId !== activePointerId) return;
		if (!isResizing) return;
		isResizing = false;
		activePointerId = null;
		document.body.style.userSelect = '';
		localStorage.setItem('chatSidePanelWidth', String(panelWidth));
	};

	const resizeViewportHandler = () => {
		applyPanelWidth(panelWidth);
	};

	$: {
		const artifactsVisible = $showArtifacts;
		const nextBasePanel = resolveChatBasePanel(basePanel, {
			artifactsVisible,
			aguiVisible,
			artifactsJustOpened: artifactsVisible && !previousArtifacts,
			aguiJustOpened: aguiVisible && !previousAgui
		});

		if (nextBasePanel !== basePanel) {
			basePanel = nextBasePanel;
		}

		previousArtifacts = artifactsVisible;
		previousAgui = aguiVisible;
	}

	const closeBasePanel = () => {
		if (basePanel === 'artifacts') {
			showArtifacts.set(false);
		} else if (basePanel === 'agui') {
			aguiStore.hidePanel();
		}
	};

	const closeTopPanel = () => {
		if ($showExpertAgentDrawer) {
			closeExpertAgentDrawer();
			return;
		}

		closeBasePanel();
	};

	async function startExpertAgentChat(skill: ExpertSkillCard) {
		const searchParams = new URLSearchParams({
			'expert-agent': skill.skill_name,
			'expert-agent-start': uuidv4()
		});

		await goto(`/?${searchParams.toString()}`);
		await tick();
		closeExpertAgentDrawer();
	}

	onMount(() => {
		panelLifecycleReady = true;
		previousPanelVisible = visible;
		void syncPanelAnimation(visible);
		previousExpertVisible = $showExpertAgentDrawer;
		void syncExpertAnimation($showExpertAgentDrawer);

		const mediaQuery = window.matchMedia('(min-width: 1024px)');
		const handleMediaQuery = (e: MediaQueryListEvent | MediaQueryList) => {
			largeScreen = e.matches;
			applyPanelWidth(Number(localStorage.getItem('chatSidePanelWidth')) || panelWidth);
		};

		applyPanelWidth(Number(localStorage.getItem('chatSidePanelWidth')) || DEFAULT_WIDTH);
		mediaQuery.addEventListener('change', handleMediaQuery);
		window.addEventListener('pointermove', resizeMoveHandler);
		window.addEventListener('pointerup', resizeEndHandler);
		window.addEventListener('pointercancel', resizeEndHandler);
		window.addEventListener('resize', resizeViewportHandler);
		handleMediaQuery(mediaQuery);

		return () => {
			mediaQuery.removeEventListener('change', handleMediaQuery);
			window.removeEventListener('pointermove', resizeMoveHandler);
			window.removeEventListener('pointerup', resizeEndHandler);
			window.removeEventListener('pointercancel', resizeEndHandler);
			window.removeEventListener('resize', resizeViewportHandler);
			clearPanelAnimationHandles();
			clearExpertAnimationHandles();
			document.body.style.userSelect = '';
		};
	});
</script>

{#if panelRendered}
	{#if largeScreen}
		<div class="chat-side-panel-host" class:chat-side-panel-host-entered={panelEntered}>
			<button
				type="button"
				class="chat-side-panel-resizer"
				aria-label="Resize side panel"
				on:pointerdown={resizeStartHandler}
			>
				<span class="chat-side-panel-resizer-grip" aria-hidden="true"></span>
			</button>
			<div
				class="chat-side-panel-shell"
				class:chat-side-panel-shell-artifacts={basePanel === 'artifacts'}
				class:chat-side-panel-shell-expert-only={basePanel === null && expertRendered}
			>
				{#if basePanel === 'artifacts'}
					<Artifacts {history} on:close={closeBasePanel} />
				{:else if basePanel === 'agui'}
					<AguiPanel />
				{/if}

				{#if expertRendered}
					<div
						class="chat-side-panel-expert-layer"
						class:chat-side-panel-expert-layer-entered={expertEntered || basePanel === null}
						class:chat-side-panel-expert-layer-interactive={$showExpertAgentDrawer}
					>
						<ExpertAgentDrawer
							show={true}
							on:start={(event) => {
								void startExpertAgentChat(event.detail);
							}}
							on:close={closeExpertAgentDrawer}
						/>
					</div>
				{/if}
			</div>
		</div>
	{:else}
		<Drawer
			show={visible}
			onClose={closeTopPanel}
			className="min-h-[100dvh] !bg-white dark:!bg-gray-850"
		>
			<div class="relative h-[100dvh] min-h-0 overflow-hidden">
				{#if basePanel === 'artifacts'}
					<Artifacts {history} on:close={closeBasePanel} />
				{:else if basePanel === 'agui'}
					<AguiPanel />
				{/if}

				{#if expertRendered}
					<div
						class="chat-side-panel-expert-layer"
						class:chat-side-panel-expert-layer-entered={expertEntered || basePanel === null}
						class:chat-side-panel-expert-layer-interactive={$showExpertAgentDrawer}
					>
						<ExpertAgentDrawer
							show={true}
							on:start={(event) => {
								void startExpertAgentChat(event.detail);
							}}
							on:close={closeExpertAgentDrawer}
						/>
					</div>
				{/if}
			</div>
		</Drawer>
	{/if}
{/if}

<style>
	.chat-side-panel-host {
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		z-index: 35;
		width: var(--chat-side-panel-width);
		padding: 20px 18px 20px 0;
		pointer-events: none;
		will-change: transform, opacity;
		opacity: 0;
		visibility: hidden;
		transform: translateX(calc(var(--chat-side-panel-width) + 24px));
		transition:
			transform 260ms cubic-bezier(0.4, 0, 1, 1),
			opacity 220ms ease,
			visibility 0s linear 260ms;
	}

	.chat-side-panel-host-entered {
		opacity: 1;
		visibility: visible;
		transform: translateX(0);
		transition:
			transform 320ms cubic-bezier(0.22, 1, 0.36, 1),
			opacity 260ms ease,
			visibility 0s linear 0s;
	}

	.chat-side-panel-resizer {
		position: absolute;
		top: 20px;
		bottom: 20px;
		left: -6px;
		z-index: 2;
		width: 12px;
		cursor: col-resize;
		pointer-events: auto;
		touch-action: none;
		border: 0;
		background: transparent;
	}

	.chat-side-panel-resizer:hover {
		background: linear-gradient(
			90deg,
			transparent 0%,
			rgba(87, 112, 205, 0.28) 48%,
			transparent 100%
		);
	}

	.chat-side-panel-resizer-grip {
		position: absolute;
		top: 50%;
		left: 50%;
		width: 4px;
		height: 56px;
		border: 0;
		border-radius: 999px;
		background: linear-gradient(
			180deg,
			rgba(114, 130, 179, 0.22) 0%,
			rgba(70, 105, 236, 0.5) 50%,
			rgba(114, 130, 179, 0.22) 100%
		);
		box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.55);
		transform: translate(-50%, -50%);
		opacity: 0.72;
		transition:
			opacity 160ms ease,
			box-shadow 160ms ease,
			transform 160ms ease;
	}

	.chat-side-panel-resizer:hover .chat-side-panel-resizer-grip,
	.chat-side-panel-resizer:focus-visible .chat-side-panel-resizer-grip {
		opacity: 1;
		box-shadow:
			0 0 0 1px rgba(255, 255, 255, 0.72),
			0 0 14px rgba(70, 105, 236, 0.2);
	}

	.chat-side-panel-resizer:active .chat-side-panel-resizer-grip {
		transform: translate(-50%, -50%) scale(0.94);
	}

	.chat-side-panel-shell {
		position: relative;
		width: 100%;
		height: 100%;
		min-height: 0;
		overflow: hidden;
		pointer-events: auto;
		border-radius: 1.5rem;
		background: #fff;
		box-shadow: var(--light-card-shadow, -18px 18px 45px rgba(71, 79, 102, 0.16));
	}

	.chat-side-panel-shell-expert-only {
		background: transparent;
		box-shadow: none;
		backdrop-filter: none;
	}

	.chat-side-panel-expert-layer {
		position: absolute;
		inset: 0;
		z-index: 3;
		overflow: hidden;
		border-radius: inherit;
		background: var(--light-surface, rgba(255, 255, 255, 0.96));
		box-shadow: -18px 18px 45px rgba(71, 79, 102, 0.12);
		backdrop-filter: blur(18px);
		pointer-events: none;
		will-change: transform, opacity;
		opacity: 0;
		visibility: hidden;
		transform: translateX(calc(100% + 24px));
		transition:
			transform 260ms cubic-bezier(0.4, 0, 1, 1),
			opacity 220ms ease,
			visibility 0s linear 260ms;
	}

	.chat-side-panel-expert-layer-entered {
		opacity: 1;
		visibility: visible;
		transform: translateX(0);
		transition:
			transform 320ms cubic-bezier(0.22, 1, 0.36, 1),
			opacity 260ms ease,
			visibility 0s linear 0s;
	}

	.chat-side-panel-expert-layer-interactive {
		pointer-events: auto;
	}

	.chat-side-panel-shell-artifacts {
		min-height: min(560px, calc(100dvh - 40px));
		max-height: calc(100dvh - 40px);
		border: 1.5px solid rgb(47 84 157);
		box-shadow:
			0 22px 58px rgba(9, 37, 88, 0.12),
			0 0 0 1px rgba(255, 255, 255, 0.86) inset;
	}

	:global(.dark) .chat-side-panel-shell {
		background: #111827;
		box-shadow: -18px 18px 45px rgba(0, 0, 0, 0.26);
	}

	:global(.dark) .chat-side-panel-shell-expert-only {
		background: transparent;
		box-shadow: none;
	}

	:global(.dark) .chat-side-panel-expert-layer {
		background: rgba(17, 24, 39, 0.98);
		box-shadow: -18px 18px 45px rgba(0, 0, 0, 0.24);
	}

	:global(.dark) .chat-side-panel-resizer-grip {
		background: linear-gradient(
			180deg,
			rgba(148, 163, 184, 0.28) 0%,
			rgba(147, 197, 253, 0.74) 50%,
			rgba(148, 163, 184, 0.28) 100%
		);
		box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.5);
	}
</style>
