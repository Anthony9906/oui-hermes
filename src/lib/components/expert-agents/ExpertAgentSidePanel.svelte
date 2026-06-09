<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount, tick } from 'svelte';
	import { fly } from 'svelte/transition';
	import { v4 as uuidv4 } from 'uuid';

	import Drawer from '$lib/components/common/Drawer.svelte';
	import ExpertAgentDrawer from '$lib/components/expert-agents/ExpertAgentDrawer.svelte';
	import type { ExpertSkillCard } from '$lib/apis/expert-agents';
	import { closeExpertAgentDrawer, showExpertAgentDrawer } from '$lib/stores/expertAgents';

	const MIN_WIDTH = 420;
	const MAX_WIDTH = 920;
	const DEFAULT_WIDTH = 640;

	let largeScreen = false;
	let panelWidth = DEFAULT_WIDTH;
	let isResizing = false;
	let startClientX = 0;
	let startWidth = DEFAULT_WIDTH;
	let activePointerId: number | null = null;

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

{#if $showExpertAgentDrawer}
	{#if largeScreen}
		<div class="expert-agent-side-panel-host">
			<button
				type="button"
				class="expert-agent-side-panel-resizer"
				aria-label="Resize expert agent panel"
				on:pointerdown={resizeStartHandler}
			></button>
			<div
				in:fly={{ x: 56, duration: 320, opacity: 0.72 }}
				out:fly={{ x: 44, duration: 220, opacity: 0.62 }}
				class="expert-agent-side-panel-shell"
			>
				<ExpertAgentDrawer
					show={$showExpertAgentDrawer}
					on:start={(event) => {
						void startExpertAgentChat(event.detail);
					}}
					on:close={closeExpertAgentDrawer}
				/>
			</div>
		</div>
	{:else}
		<Drawer
			show={$showExpertAgentDrawer}
			onClose={closeExpertAgentDrawer}
			className="min-h-[100dvh] !bg-white dark:!bg-gray-850"
		>
			<div class="h-[100dvh] min-h-0">
				<ExpertAgentDrawer
					show={$showExpertAgentDrawer}
					on:start={(event) => {
						void startExpertAgentChat(event.detail);
					}}
					on:close={closeExpertAgentDrawer}
				/>
			</div>
		</Drawer>
	{/if}
{/if}

<style>
	.expert-agent-side-panel-host {
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		z-index: 35;
		width: var(--chat-side-panel-width, clamp(480px, 38vw, 760px));
		padding: 20px 18px 20px 0;
		pointer-events: none;
	}

	.expert-agent-side-panel-resizer {
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

	.expert-agent-side-panel-resizer:hover {
		background: linear-gradient(
			90deg,
			transparent 0%,
			rgba(121, 171, 223, 0.34) 48%,
			transparent 100%
		);
	}

	.expert-agent-side-panel-resizer::after {
		content: '';
		position: absolute;
		top: 50%;
		left: 50%;
		width: 4px;
		height: 56px;
		border-radius: 999px;
		background: linear-gradient(
			180deg,
			rgba(127, 164, 205, 0.24) 0%,
			rgba(69, 126, 188, 0.52) 50%,
			rgba(127, 164, 205, 0.24) 100%
		);
		box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.55);
		transform: translate(-50%, -50%);
		opacity: 0.72;
	}

	.expert-agent-side-panel-shell {
		width: 100%;
		height: 100%;
		min-height: 0;
		overflow: hidden;
		pointer-events: auto;
		border-radius: 1.5rem;
		border: 1px solid rgba(186, 215, 238, 0.72);
		background: linear-gradient(
			180deg,
			rgba(255, 255, 255, 0.96) 0%,
			rgba(243, 249, 255, 0.86) 100%
		);
		box-shadow:
			-18px 18px 45px rgba(71, 79, 102, 0.16),
			inset 1px 1px 0 rgba(255, 255, 255, 0.94);
		backdrop-filter: blur(18px);
	}

	:global(.dark) .expert-agent-side-panel-shell {
		border-color: rgba(55, 65, 81, 0.9);
		background: #111827;
		box-shadow: -18px 18px 45px rgba(0, 0, 0, 0.26);
	}
</style>
