/**
 * AG-UI (Agent-User Interaction) state store.
 *
 * Receives agui:* Socket.IO events from the backend and maintains
 * the UI state for the right-side AG-UI workspace.
 */
import { derived, writable } from 'svelte/store';

// ── Types ────────────────────────────────────────────────────────────────

export type AguiStatus = 'pending' | 'running' | 'completed' | 'error';

export interface AguiStep {
	step_name: string;
	status: AguiStatus;
	timestamp?: number;
}

export interface AguiArtifact {
	artifact_type: string;
	payload: any;
	run_id: string;
	timestamp: number;
}

export type AguiInteractionKind = 'choice' | 'approval';

export interface AguiInteractionOption {
	id: string;
	label: string;
	value: string;
	description?: string;
	metadata?: any;
}

export interface AguiInteractionRequest {
	id: string;
	kind: AguiInteractionKind;
	title: string;
	message: string;
	options: AguiInteractionOption[];
	custom_label: string;
	custom_placeholder: string;
	allow_custom: boolean;
	approval_id?: string;
	tool_call_id?: string;
	run_id: string;
	timestamp: number;
	payload: any;
}

export interface AguiToolCall {
	tool_call_id: string;
	tool_name: string;
	status: Extract<AguiStatus, 'running' | 'completed' | 'error'>;
}

export interface AguiState {
	steps: AguiStep[];
	current_step: string | null;
	artifact: AguiArtifact | null;
	interaction: AguiInteractionRequest | null;
	tool_calls: Record<string, AguiToolCall>;
	is_active: boolean;
	panel_visible: boolean;
	run_id: string | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────

const createInitialState = (): AguiState => ({
	steps: [],
	current_step: null,
	artifact: null,
	interaction: null,
	tool_calls: {},
	is_active: false,
	panel_visible: false,
	run_id: null
});

const normalizeTimestamp = (ts?: number) => {
	if (!ts) return Date.now();
	return ts > 1_000_000_000_000 ? ts : ts * 1000;
};

const hasCurrentContent = (s: AguiState) => s.artifact !== null;

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
	const label = stringifyValue(option.label ?? option.title ?? option.name ?? option.value, id);
	const value = stringifyValue(option.value ?? option.content ?? option.label ?? label, label);
	const description = stringifyValue(option.description ?? option.detail ?? option.hint, '');

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

	const kind = payload.kind === 'approval' || payload.type === 'approval' ? 'approval' : 'choice';
	const options = (Array.isArray(payload.options) ? payload.options : [])
		.map(normalizeInteractionOption)
		.filter(Boolean) as AguiInteractionOption[];

	return {
		id: stringifyValue(
			payload.id ?? payload.interaction_id ?? payload.request_id,
			`interaction_${timestamp}`
		),
		kind,
		title: stringifyValue(
			payload.title ?? (kind === 'approval' ? '需要授权确认' : '请选择下一步'),
			kind === 'approval' ? '需要授权确认' : '请选择下一步'
		),
		message: stringifyValue(payload.message ?? payload.description ?? payload.question, ''),
		options,
		custom_label: stringifyValue(payload.custom_label ?? payload.customLabel, '自定义回答'),
		custom_placeholder: stringifyValue(
			payload.custom_placeholder ?? payload.customPlaceholder,
			'输入自定义内容'
		),
		allow_custom: kind !== 'approval',
		approval_id: stringifyValue(payload.approval_id, ''),
		tool_call_id: stringifyValue(payload.tool_call_id, ''),
		run_id: runId,
		timestamp,
		payload
	};
};

const ensureRun = (s: AguiState, runId?: string | null): AguiState => {
	if (!runId || s.run_id === runId) return s;

	if (!hasCurrentContent(s)) {
		return {
			...s,
			run_id: runId,
			steps: [],
			current_step: null,
			artifact: null,
			interaction: null,
			tool_calls: {}
		};
	}

	return {
		...s,
		run_id: runId,
		steps: [],
		current_step: null,
		artifact: null,
		interaction: null,
		tool_calls: {}
	};
};

// ── Store ─────────────────────────────────────────────────────────────────

function createAguiStore() {
	const { subscribe, update, set } = writable<AguiState>(createInitialState());

	return {
		subscribe,

		/** Prepare a local run. Tool activity stays internal; only artifacts open the panel. */
		activate(run_id: string) {
			update(() => ({
				...createInitialState(),
				run_id,
				is_active: true
			}));
		},

		/** Restore a previously emitted artifact without forcing the panel open. */
		restoreArtifact(artifact: AguiArtifact, panelVisible = false) {
			update((s) => ({
				...s,
				is_active: true,
				panel_visible: panelVisible,
				run_id: artifact.run_id || s.run_id,
				steps: [],
				current_step: null,
				artifact,
				interaction: null,
				tool_calls: {}
			}));
		},

		/** Handle a step_started event. */
		onStepStarted(step_name: string, ts: number, run_id?: string | null) {
			update((state) => {
				const s = ensureRun(state, run_id);
				const timestamp = normalizeTimestamp(ts);
				const steps = [...s.steps];
				const existingIdx = steps.findIndex((st) => st.step_name === step_name);

				if (existingIdx >= 0) {
					steps[existingIdx] = { ...steps[existingIdx], status: 'running', timestamp };
				} else {
					if (s.current_step) {
						const idx = steps.findIndex((st) => st.step_name === s.current_step);
						if (idx >= 0) {
							steps[idx] = { ...steps[idx], status: 'completed' };
						}
					}
					steps.push({ step_name, status: 'running', timestamp });
				}

				return {
					...s,
					is_active: true,
					steps,
					current_step: step_name
				};
			});
		},

		/** Handle a step_finished event. */
		onStepFinished(step_name: string, run_id?: string | null) {
			update((state) => {
				const s = ensureRun(state, run_id);
				const steps = s.steps.map((st) =>
					st.step_name === step_name ? { ...st, status: 'completed' as const } : st
				);
				return { ...s, steps, current_step: s.current_step === step_name ? null : s.current_step };
			});
		},

		/** Handle a tool_call_start event. */
		onToolCallStart(
			tool_call_id: string,
			tool_name: string,
			run_id?: string | null,
			ts?: number,
			args?: any
		) {
			update((state) => {
				const s = ensureRun(state, run_id);
				void ts;
				void args;

				return {
					...s,
					is_active: true,
					tool_calls: {
						...s.tool_calls,
						[tool_call_id]: { tool_call_id, tool_name, status: 'running' }
					}
				};
			});
		},

		/** Handle a tool_call_end event. */
		onToolCallEnd(tool_call_id: string, run_id?: string | null, ts?: number) {
			update((state) => {
				const s = ensureRun(state, run_id);
				const tc = s.tool_calls[tool_call_id];
				void ts;

				return {
					...s,
					tool_calls: tc
						? {
								...s.tool_calls,
								[tool_call_id]: { ...tc, status: 'completed' }
							}
						: s.tool_calls
				};
			});
		},

		/** Handle a state_snapshot event (artifact delivery). */
		onStateSnapshot(artifact: AguiArtifact) {
			update((state) => {
				const s = ensureRun(state, artifact.run_id);
				return {
					...s,
					is_active: true,
					artifact,
					interaction: null,
					panel_visible: true,
					steps: s.steps
				};
			});
		},

		onInteractionRequest(interaction: AguiInteractionRequest) {
			update((state) => {
				const s = ensureRun(state, interaction.run_id);
				return {
					...s,
					is_active: true,
					interaction,
					panel_visible: false
				};
			});
		},

		clearInteraction(id?: string) {
			update((s) => {
				if (id && s.interaction?.id !== id) return s;
				return { ...s, interaction: null };
			});
		},

		showPanel() {
			update((s) => ({ ...s, is_active: true, panel_visible: true }));
		},

		hidePanel() {
			update((s) => ({ ...s, panel_visible: false }));
		},

		togglePanel() {
			update((s) => ({ ...s, is_active: true, panel_visible: !s.panel_visible }));
		},

		/** Reset for a new chat. */
		reset() {
			set(createInitialState());
		}
	};
}

export const aguiStore = createAguiStore();

// ── Derived ───────────────────────────────────────────────────────────────

export const hasArtifact = derived(aguiStore, ($s) => $s.artifact !== null);
export const activeInteraction = derived(aguiStore, ($s) => $s.interaction);
export const aguiPanelVisible = derived(
	aguiStore,
	($s) => $s.panel_visible && $s.artifact !== null
);
export const activeSteps = derived(aguiStore, ($s) =>
	$s.steps.filter((st) => st.status === 'running' || st.status === 'pending')
);
export const completedSteps = derived(aguiStore, ($s) =>
	$s.steps.filter((st) => st.status === 'completed')
);
