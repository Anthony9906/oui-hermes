import { derived, writable } from 'svelte/store';

import type { HermesApprovalChoice } from '$lib/apis/hermes-runs';

export interface HermesApprovalRequest {
	approval_request_id: string;
	run_id: string;
	chat_id: string;
	message_id: string;
	command: string;
	description: string;
	pattern_key: string;
	pattern_keys: string[];
	choices: HermesApprovalChoice[];
	sequence: number;
	status: 'pending' | 'responding' | 'approved' | 'denied' | 'expired';
	selected_choice?: HermesApprovalChoice | null;
	requested_at: number;
	responded_at?: number | null;
}

interface HermesApprovalState {
	active_chat_id: string;
	requests: HermesApprovalRequest[];
}

const initialState = (): HermesApprovalState => ({ active_chat_id: '', requests: [] });

function createHermesApprovalStore() {
	const { subscribe, update, set } = writable<HermesApprovalState>(initialState());

	return {
		subscribe,
		setActiveChat(chatId: string) {
			update((state) => ({ ...state, active_chat_id: chatId || '' }));
		},
		replacePendingForChat(chatId: string, requests: HermesApprovalRequest[]) {
			update((state) => ({
				...state,
				requests: [...state.requests.filter((request) => request.chat_id !== chatId), ...requests]
			}));
		},
		onRequest(request: HermesApprovalRequest) {
			update((state) => ({
				...state,
				requests: [
					...state.requests.filter(
						(item) => item.approval_request_id !== request.approval_request_id
					),
					request
				]
			}));
		},
		markResponding(id: string, choice: HermesApprovalChoice) {
			update((state) => ({
				...state,
				requests: state.requests.map((request) =>
					request.approval_request_id === id
						? { ...request, status: 'responding', selected_choice: choice }
						: request
				)
			}));
		},
		markPending(id: string) {
			update((state) => ({
				...state,
				requests: state.requests.map((request) =>
					request.approval_request_id === id
						? { ...request, status: 'pending', selected_choice: null }
						: request
				)
			}));
		},
		expireForRun(runId: string) {
			update((state) => ({
				...state,
				requests: state.requests.map((request) =>
					request.run_id === runId &&
					(request.status === 'pending' || request.status === 'responding')
						? {
								...request,
								status: 'expired',
								responded_at: Date.now() / 1000
							}
						: request
				)
			}));
		},
		resolve(id: string, choice?: HermesApprovalChoice) {
			update((state) => ({
				...state,
				requests: state.requests.map((request) =>
					request.approval_request_id === id
						? {
								...request,
								status: (choice ?? request.selected_choice) === 'deny' ? 'denied' : 'approved',
								selected_choice: choice ?? request.selected_choice,
								responded_at: Date.now() / 1000
							}
						: request
				)
			}));
		},
		resolveFirstForRun(runId: string, choice?: HermesApprovalChoice) {
			update((state) => {
				const request = state.requests
					.filter(
						(item) =>
							item.run_id === runId && (item.status === 'pending' || item.status === 'responding')
					)
					.sort((a, b) => a.sequence - b.sequence)
					.at(0);
				if (!request) return state;
				return {
					...state,
					requests: state.requests.map((item) =>
						item.approval_request_id === request.approval_request_id
							? {
									...item,
									status: (choice ?? item.selected_choice) === 'deny' ? 'denied' : 'approved',
									selected_choice: choice ?? item.selected_choice,
									responded_at: Date.now() / 1000
								}
							: item
					)
				};
			});
		},
		reset() {
			set(initialState());
		}
	};
}

export const hermesApprovalStore = createHermesApprovalStore();
export const activeHermesApproval = derived(
	hermesApprovalStore,
	($state) =>
		$state.requests
			.filter(
				(request) =>
					request.chat_id === $state.active_chat_id &&
					(request.status === 'pending' || request.status === 'responding')
			)
			.sort((a, b) => a.requested_at - b.requested_at || a.sequence - b.sequence)
			.at(0) ?? null
);
