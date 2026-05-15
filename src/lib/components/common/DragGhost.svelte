<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	export let x;
	export let y;

	let popupElement = null;

	onMount(() => {
		document.body.appendChild(popupElement);
		document.body.style.overflow = 'hidden';
	});

	onDestroy(() => {
		if (popupElement && popupElement.parentNode) {
			try {
				popupElement.parentNode.removeChild(popupElement);
			} catch (err) {
				console.warn('Failed to remove popupElement:', err);
			}
		}

		document.body.style.overflow = 'unset';
	});
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->

<div
	bind:this={popupElement}
	class="fixed top-0 left-0 w-screen h-[100dvh] z-[99999] touch-none pointer-events-none"
>
	<div class=" absolute text-white z-99999" style="top: {y + 10}px; left: {x + 10}px;">
		<slot></slot>
	</div>
</div>
