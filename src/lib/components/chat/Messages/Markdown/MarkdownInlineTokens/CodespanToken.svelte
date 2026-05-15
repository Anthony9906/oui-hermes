<script lang="ts">
	import { copyToClipboard, unescapeHtml } from '$lib/utils';
	import { toast } from 'svelte-sonner';

	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	export let token;
	export let done = true;
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<code
	class="codespan cursor-pointer {!done ? 'fade-in-token' : ''}"
	on:click={() => {
		copyToClipboard(unescapeHtml(token.text));
		toast.success($i18n.t('Copied to clipboard'));
	}}>{unescapeHtml(token.text)}</code
>
