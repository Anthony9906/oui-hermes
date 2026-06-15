import { derived, writable } from 'svelte/store';

export interface AguiArtifact {
	artifact_type: string;
	payload: any;
	run_id: string;
	timestamp: number;
}

export interface AguiInteractionOption {
	id: string;
	label: string;
	value: string;
	description?: string;
	metadata?: any;
}

export interface AguiInteractionRequest {
	id: string;
	kind: 'choice';
	title: string;
	message: string;
	options: AguiInteractionOption[];
	custom_label: string;
	custom_placeholder: string;
	allow_custom: boolean;
	run_id: string;
	timestamp: number;
	payload: any;
}

export interface AguiState {
	artifact: AguiArtifact | null;
	interaction: AguiInteractionRequest | null;
	is_active: boolean;
	panel_visible: boolean;
	run_id: string | null;
}

const createInitialState = (): AguiState => ({
	artifact: null,
	interaction: null,
	is_active: false,
	panel_visible: false,
	run_id: null
});

const normalizeTimestamp = (timestamp?: number) => {
	if (!timestamp) return Date.now();
	return timestamp > 1_000_000_000_000 ? timestamp : timestamp * 1000;
};

const stringifyValue = (value: any, fallback = '') => {
	if (typeof value === 'string') return value;
	if (value === null || value === undefined) return fallback;
	if (typeof value === 'number' || typeof value === 'boolean') return String(value);

	try {
		return JSON.stringify(value);
	} catch {
		return fallback;
	}
};

const firstDefined = (...values: any[]) =>
	values.find((value) => value !== null && value !== undefined);

const normalizeInteractionOption = (option: any, index: number): AguiInteractionOption | null => {
	if (typeof option === 'string') {
		return {
			id: `option_${index + 1}`,
			label: option,
			value: option
		};
	}

	if (!option || typeof option !== 'object') return null;

	const id = stringifyValue(option.id ?? option.key ?? option.value, `option_${index + 1}`);
	const label = stringifyValue(
		firstDefined(
			option.label,
			option.title,
			option.name,
			option.text,
			option.content,
			option.option,
			option.choice,
			option.value
		),
		id
	);
	const value = stringifyValue(
		firstDefined(
			option.value,
			option.content,
			option.text,
			option.option,
			option.choice,
			option.label
		),
		label
	);
	const description = stringifyValue(
		firstDefined(option.description, option.detail, option.hint, option.subtitle),
		''
	);

	return {
		id,
		label,
		value,
		...(description ? { description } : {}),
		metadata: option.metadata ?? option.meta
	};
};

export const normalizeInteractionRequest = (
	payload: any,
	runId = '',
	timestamp = Date.now()
): AguiInteractionRequest | null => {
	if (!payload || typeof payload !== 'object') return null;

	const rawOptions = firstDefined(payload.options, payload.choices, payload.items);
	const options = (Array.isArray(rawOptions) ? rawOptions : [])
		.map(normalizeInteractionOption)
		.filter(Boolean) as AguiInteractionOption[];

	if (!options.length) return null;

	const allowCustom = firstDefined(payload.allow_custom, payload.allowCustom);

	return {
		id: stringifyValue(
			payload.id ?? payload.interaction_id ?? payload.request_id,
			`interaction_${timestamp}`
		),
		kind: 'choice',
		title: stringifyValue(
			firstDefined(payload.title, payload.heading, payload.name),
			'请选择下一步'
		),
		message: stringifyValue(
			firstDefined(
				payload.message,
				payload.description,
				payload.question,
				payload.prompt,
				payload.body
			),
			''
		),
		options,
		custom_label: stringifyValue(payload.custom_label ?? payload.customLabel, '自定义回答'),
		custom_placeholder: stringifyValue(
			payload.custom_placeholder ?? payload.customPlaceholder,
			'输入自定义内容'
		),
		allow_custom: typeof allowCustom === 'boolean' ? allowCustom : true,
		run_id: runId,
		timestamp: normalizeTimestamp(timestamp),
		payload
	};
};

function createAguiStore() {
	const { subscribe, update, set } = writable<AguiState>(createInitialState());

	return {
		subscribe,
		activate(run_id: string) {
			update((state) => ({
				...state,
				is_active: true,
				run_id,
				interaction: null
			}));
		},
		restoreArtifact(artifact: AguiArtifact, panelVisible = false) {
			update((state) => ({
				...state,
				artifact,
				interaction: null,
				is_active: true,
				panel_visible: panelVisible,
				run_id: artifact.run_id || state.run_id
			}));
		},
		onStateSnapshot(artifact: AguiArtifact) {
			update((state) => ({
				...state,
				artifact,
				interaction: null,
				is_active: true,
				panel_visible: true,
				run_id: artifact.run_id || state.run_id
			}));
		},
		onInteractionRequest(interaction: AguiInteractionRequest) {
			update((state) => ({
				...state,
				interaction,
				is_active: true,
				run_id: interaction.run_id || state.run_id
			}));
		},
		clearInteraction(id?: string) {
			update((state) => {
				if (id && state.interaction?.id !== id) return state;
				return { ...state, interaction: null };
			});
		},
		showPanel() {
			update((state) => ({ ...state, is_active: true, panel_visible: true }));
		},
		hidePanel() {
			update((state) => ({ ...state, panel_visible: false }));
		},
		togglePanel() {
			update((state) => ({ ...state, is_active: true, panel_visible: !state.panel_visible }));
		},
		reset() {
			set(createInitialState());
		}
	};
}

export const aguiStore = createAguiStore();
export const hasArtifact = derived(aguiStore, ($state) => $state.artifact !== null);
export const aguiPanelVisible = derived(
	aguiStore,
	($state) => $state.panel_visible && $state.artifact !== null
);
export const activeInteraction = derived(aguiStore, ($state) => $state.interaction);
