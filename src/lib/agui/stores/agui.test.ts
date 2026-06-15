import { get } from 'svelte/store';
import { describe, expect, it } from 'vitest';

import {
	activeInteraction,
	aguiPanelVisible,
	aguiStore,
	normalizeInteractionRequest
} from './agui';

describe('aguiStore', () => {
	it('normalizes choice interactions', () => {
		const interaction = normalizeInteractionRequest(
			{
				title: 'Pick one',
				question: 'Which path?',
				choices: ['A', { id: 'b', label: 'B', value: 'bee', description: 'Second' }]
			},
			'run_1',
			1000
		);

		expect(interaction?.kind).toBe('choice');
		expect(interaction?.message).toBe('Which path?');
		expect(interaction?.options).toEqual([
			{ id: 'option_1', label: 'A', value: 'A' },
			{ id: 'b', label: 'B', value: 'bee', description: 'Second', metadata: undefined }
		]);
	});

	it('shows artifact panel and keeps interaction separate', () => {
		aguiStore.reset();
		aguiStore.onInteractionRequest(
			normalizeInteractionRequest({ title: 'Pick', options: ['A'] }, 'run_1')!
		);
		expect(get(activeInteraction)?.title).toBe('Pick');

		aguiStore.onStateSnapshot({
			artifact_type: 'generic-preview',
			payload: { title: 'Preview' },
			run_id: 'run_1',
			timestamp: Date.now()
		});

		expect(get(activeInteraction)).toBeNull();
		expect(get(aguiPanelVisible)).toBe(true);
	});
});
