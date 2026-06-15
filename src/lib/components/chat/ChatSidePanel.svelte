<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount, tick } from 'svelte';
	import { fly } from 'svelte/transition';
	import { v4 as uuidv4 } from 'uuid';

	import { showArtifacts } from '$lib/stores';
	import { closeExpertAgentDrawer, showExpertAgentDrawer } from '$lib/stores/expertAgents';
	import type { ExpertSkillCard } from '$lib/apis/expert-agents';

	import Drawer from '../common/Drawer.svelte';
	import Artifacts from './Artifacts.svelte';
	import AguiPanel from '$lib/agui/components/AguiPanel.svelte';
	import ExpertAgentDrawer from '$lib/components/expert-agents/ExpertAgentDrawer.svelte';
	import { aguiPanelVisible, aguiStore } from '$lib/agui/stores/agui';

	export let history;

	const MIN_WIDTH = 420;
	const MAX_WIDTH = 920;
	const DEFAULT_WIDTH = 800;

	let largeScreen = false;
	let activePanel: 'artifacts' | 'expertAgents' | 'agui' = 'expertAgents';
	let previousArtifacts = false;
	let previousExpertAgent = false;
	let previousAgui = false;
	let panelWidth = DEFAULT_WIDTH;
	let isResizing = false;
	let startClientX = 0;
	let startWidth = DEFAULT_WIDTH;
	let activePointerId: number | null = null;

	$: aguiVisible = $aguiPanelVisible;
	$: visible = $showArtifacts || $showExpertAgentDrawer || aguiVisible;

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
		const expertAgentVisible = $showExpertAgentDrawer;

		if (aguiVisible && !previousAgui) {
			activePanel = 'agui';
		} else if (artifactsVisible && !previousArtifacts) {
			activePanel = 'artifacts';
		} else if (expertAgentVisible && !previousExpertAgent) {
			activePanel = 'expertAgents';
		}

		if (!aguiVisible && activePanel === 'agui') {
			if (artifactsVisible) {
				activePanel = 'artifacts';
			} else if (expertAgentVisible) {
				activePanel = 'expertAgents';
			}
		}

		if (!artifactsVisible && expertAgentVisible && activePanel === 'artifacts') {
			activePanel = 'expertAgents';
		}

		if (!expertAgentVisible && artifactsVisible && activePanel === 'expertAgents') {
			activePanel = 'artifacts';
		}

		previousArtifacts = artifactsVisible;
		previousExpertAgent = expertAgentVisible;
		previousAgui = aguiVisible;
	}

	const closeActivePanel = () => {
		if (activePanel === 'artifacts') {
			showArtifacts.set(false);
		} else if (activePanel === 'agui') {
			aguiStore.hidePanel();
		} else {
			closeExpertAgentDrawer();
		}
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
			document.body.style.userSelect = '';
		};
	});
</script>

{#if visible}
	{#if largeScreen}
		<div class="chat-side-panel-host">
			<button
				type="button"
				class="chat-side-panel-resizer"
				class:chat-side-panel-resizer-artifacts={activePanel === 'artifacts'}
				aria-label="Resize side panel"
				on:pointerdown={resizeStartHandler}
			>
				<span class="chat-side-panel-resizer-grip" aria-hidden="true"></span>
			</button>
			<div
				in:fly={{ x: 56, duration: 320, opacity: 0.72 }}
				out:fly={{ x: 44, duration: 220, opacity: 0.62 }}
				class="chat-side-panel-shell"
				class:chat-side-panel-shell-artifacts={activePanel === 'artifacts'}
			>
				{#if activePanel === 'artifacts'}
					<Artifacts {history} on:close={closeActivePanel} />
				{:else if activePanel === 'agui'}
					<AguiPanel />
				{:else}
					<ExpertAgentDrawer
						show={$showExpertAgentDrawer}
						on:start={(event) => {
							void startExpertAgentChat(event.detail);
						}}
						on:close={closeActivePanel}
					/>
				{/if}
			</div>
		</div>
	{:else}
		<Drawer
			show={visible}
			onClose={closeActivePanel}
			className="min-h-[100dvh] !bg-white dark:!bg-gray-850"
		>
			<div class="h-[100dvh] min-h-0">
				{#if activePanel === 'artifacts'}
					<Artifacts {history} on:close={closeActivePanel} />
				{:else if activePanel === 'agui'}
					<AguiPanel />
				{:else}
					<ExpertAgentDrawer
						show={$showExpertAgentDrawer}
						on:start={(event) => {
							void startExpertAgentChat(event.detail);
						}}
						on:close={closeActivePanel}
					/>
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
	}

	.chat-side-panel-resizer {
		position: absolute;
		top: 50%;
		left: -16px;
		z-index: 2;
		width: 32px;
		height: 88px;
		display: flex;
		align-items: center;
		justify-content: center;
		transform: translateY(-50%);
		cursor: col-resize;
		pointer-events: auto;
		touch-action: none;
		border: 0;
		background: transparent;
	}

	.chat-side-panel-resizer-grip {
		width: 14px;
		height: 58px;
		border: 1px solid rgba(47, 84, 157, 0.28);
		border-radius: 999px;
		background:
			radial-gradient(circle at 50% 17px, rgba(47, 84, 157, 0.78) 0 2px, transparent 2.4px),
			radial-gradient(circle at 50% 29px, rgba(47, 84, 157, 0.78) 0 2px, transparent 2.4px),
			radial-gradient(circle at 50% 41px, rgba(47, 84, 157, 0.78) 0 2px, transparent 2.4px),
			linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(239, 246, 255, 0.92));
		box-shadow:
			0 10px 26px rgba(15, 42, 89, 0.18),
			0 0 0 1px rgba(255, 255, 255, 0.86) inset;
		opacity: 0.72;
		transition:
			opacity 160ms ease,
			border-color 160ms ease,
			box-shadow 160ms ease,
			transform 160ms ease;
	}

	.chat-side-panel-resizer:hover .chat-side-panel-resizer-grip,
	.chat-side-panel-resizer:focus-visible .chat-side-panel-resizer-grip,
	.chat-side-panel-resizer-artifacts .chat-side-panel-resizer-grip {
		border-color: rgba(37, 99, 235, 0.5);
		opacity: 0.96;
		box-shadow:
			0 14px 30px rgba(15, 42, 89, 0.22),
			0 0 0 1px rgba(255, 255, 255, 0.9) inset;
	}

	.chat-side-panel-resizer:active .chat-side-panel-resizer-grip {
		transform: scale(0.96);
	}

	.chat-side-panel-shell {
		width: 100%;
		height: 100%;
		min-height: 0;
		overflow: hidden;
		pointer-events: auto;
		border-radius: 1.5rem;
		background: #fff;
		box-shadow: var(--light-card-shadow, -18px 18px 45px rgba(71, 79, 102, 0.16));
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

	:global(.dark) .chat-side-panel-resizer-grip {
		border-color: rgba(148, 163, 184, 0.42);
		background:
			radial-gradient(circle at 50% 17px, rgba(191, 219, 254, 0.85) 0 2px, transparent 2.4px),
			radial-gradient(circle at 50% 29px, rgba(191, 219, 254, 0.85) 0 2px, transparent 2.4px),
			radial-gradient(circle at 50% 41px, rgba(191, 219, 254, 0.85) 0 2px, transparent 2.4px),
			linear-gradient(180deg, rgba(30, 41, 59, 0.96), rgba(17, 24, 39, 0.94));
		box-shadow:
			0 10px 26px rgba(0, 0, 0, 0.34),
			0 0 0 1px rgba(255, 255, 255, 0.08) inset;
	}
</style>
