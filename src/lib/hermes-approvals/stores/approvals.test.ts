import { get } from 'svelte/store';
import { beforeEach, describe, expect, it } from 'vitest';

import { activeHermesApproval, hermesApprovalStore } from './approvals';

const request = (id: string, chatId: string, sequence = 1) => ({
	approval_request_id: id,
	run_id: 'run_1',
	chat_id: chatId,
	message_id: 'message_1',
	command: 'mkdir /tmp/a',
	description: 'write outside workspace',
	pattern_key: 'write',
	pattern_keys: ['write'],
	choices: ['once', 'session', 'always', 'deny'] as const,
	sequence,
	status: 'pending' as const,
	requested_at: sequence
});

describe('hermesApprovalStore', () => {
	beforeEach(() => hermesApprovalStore.reset());

	it('only exposes approvals for the active chat', () => {
		hermesApprovalStore.onRequest(request('approval_a', 'chat_a'));
		hermesApprovalStore.onRequest(request('approval_b', 'chat_b'));
		hermesApprovalStore.setActiveChat('chat_b');

		expect(get(activeHermesApproval)?.approval_request_id).toBe('approval_b');
	});

	it('keeps FIFO ordering and advances after resolution', () => {
		hermesApprovalStore.setActiveChat('chat_a');
		hermesApprovalStore.onRequest(request('approval_2', 'chat_a', 2));
		hermesApprovalStore.onRequest(request('approval_1', 'chat_a', 1));

		expect(get(activeHermesApproval)?.approval_request_id).toBe('approval_1');
		hermesApprovalStore.markResponding('approval_1', 'once');
		expect(get(activeHermesApproval)?.status).toBe('responding');
		hermesApprovalStore.resolve('approval_1', 'once');
		expect(get(activeHermesApproval)?.approval_request_id).toBe('approval_2');
	});
});
