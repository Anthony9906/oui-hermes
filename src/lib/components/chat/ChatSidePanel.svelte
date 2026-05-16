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
	import ExpertAgentDrawer from '$lib/components/expert-agents/ExpertAgentDrawer.svelte';

	export let history;

	const MIN_WIDTH = 420;
	const MAX_WIDTH = 920;
	const DEFAULT_WIDTH = 640;

	let largeScreen = false;
	let activePanel: 'artifacts' | 'expertAgents' = 'expertAgents';
	let previousArtifacts = false;
	let previousExpertAgent = false;
	let panelWidth = DEFAULT_WIDTH;
	let isResizing = false;
	let startClientX = 0;
	let startWidth = DEFAULT_WIDTH;

	$: visible = $showArtifacts || $showExpertAgentDrawer;

	const clampWidth = (width: number) => {
		if (typeof window === 'undefined') return width;
		const maxViewportWidth = Math.max(MIN_WIDTH, window.innerWidth - 520);
		return Math.min(Math.min(MAX_WIDTH, maxViewportWidth), Math.max(MIN_WIDTH, width));
	};

	const applyPanelWidth = (width: number) => {
		panelWidth = clampWidth(width);
		document.documentElement.style.setProperty('--chat-side-panel-width', `${panelWidth}px`);
	};

	const resizeStartHandler = (event: MouseEvent) => {
		isResizing = true;
		startClientX = event.clientX;
		startWidth = panelWidth;
		document.body.style.userSelect = 'none';
	};

	const resizeMoveHandler = (event: MouseEvent) => {
		if (!isResizing) return;
		applyPanelWidth(startWidth + startClientX - event.clientX);
	};

	const resizeEndHandler = () => {
		if (!isResizing) return;
		isResizing = false;
		document.body.style.userSelect = '';
		localStorage.setItem('chatSidePanelWidth', String(panelWidth));
	};

	const resizeViewportHandler = () => {
		applyPanelWidth(panelWidth);
	};

	$: {
		const artifactsVisible = $showArtifacts;
		const expertAgentVisible = $showExpertAgentDrawer;

		if (artifactsVisible && !previousArtifacts) {
			activePanel = 'artifacts';
		}

		if (expertAgentVisible && !previousExpertAgent) {
			activePanel = 'expertAgents';
		}

		if (!artifactsVisible && expertAgentVisible && activePanel === 'artifacts') {
			activePanel = 'expertAgents';
		}

		if (!expertAgentVisible && artifactsVisible && activePanel === 'expertAgents') {
			activePanel = 'artifacts';
		}

		previousArtifacts = artifactsVisible;
		previousExpertAgent = expertAgentVisible;
	}

	const closeActivePanel = () => {
		if (activePanel === 'artifacts') {
			showArtifacts.set(false);
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
		window.addEventListener('mousemove', resizeMoveHandler);
		window.addEventListener('mouseup', resizeEndHandler);
		window.addEventListener('resize', resizeViewportHandler);
		handleMediaQuery(mediaQuery);

		return () => {
			mediaQuery.removeEventListener('change', handleMediaQuery);
			window.removeEventListener('mousemove', resizeMoveHandler);
			window.removeEventListener('mouseup', resizeEndHandler);
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
				aria-label="Resize side panel"
				on:mousedown|preventDefault={resizeStartHandler}
			/>
			<div
				in:fly={{ x: 56, duration: 320, opacity: 0.72 }}
				out:fly={{ x: 44, duration: 220, opacity: 0.62 }}
				class="chat-side-panel-shell"
				class:chat-side-panel-shell-artifacts={activePanel === 'artifacts'}
			>
				{#if activePanel === 'artifacts'}
					<Artifacts {history} adaptiveHeight={true} on:close={closeActivePanel} />
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
		top: 20px;
		bottom: 20px;
		left: -6px;
		z-index: 2;
		width: 12px;
		cursor: col-resize;
		pointer-events: auto;
		border: 0;
		background: transparent;
	}

	.chat-side-panel-resizer:hover {
		background: linear-gradient(
			90deg,
			transparent 0%,
			rgba(148, 163, 184, 0.34) 48%,
			transparent 100%
		);
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
</style>
