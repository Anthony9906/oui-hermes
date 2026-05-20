// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
declare global {
	const APP_VERSION: string;
	const APP_BUILD_HASH: string;

	type dict = Record<string, any>;
	type TippyInstance = import('tippy.js').Instance;

	const gapi: any;
	const google: any;

	interface Window {
		pdfjsLib?: any;
	}

	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface Platform {}
	}
}

declare module 'svelte' {
	export function getContext(
		key: 'i18n'
	): import('svelte/store').Writable<import('i18next').i18n>;
	export function getContext<T = any>(key: any): T;
}

export {};
