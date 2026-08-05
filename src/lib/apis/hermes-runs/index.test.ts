import { afterEach, describe, expect, it, vi } from 'vitest';

import { HermesRunsApiError, isHermesApprovalGoneError, respondToHermesApproval } from '.';

describe('respondToHermesApproval', () => {
	afterEach(() => vi.unstubAllGlobals());

	it.each([404, 410])('recognizes terminal approval status %i', async (status) => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue(
				new Response(JSON.stringify({ detail: 'Run not found: run_1' }), {
					status,
					headers: { 'Content-Type': 'application/json' }
				})
			)
		);

		const response = respondToHermesApproval('token', 'run_1', 'chat_1', 'approval_1', 'deny');
		const error = await response.catch((reason) => reason);

		expect(error).toEqual(
			expect.objectContaining<HermesRunsApiError>({
				name: 'HermesRunsApiError',
				status,
				message: 'Run not found: run_1'
			})
		);
		expect(isHermesApprovalGoneError(error)).toBe(true);
	});

	it('keeps a non-terminal conflict retryable', () => {
		expect(isHermesApprovalGoneError(new HermesRunsApiError(409, 'Queue conflict'))).toBe(false);
	});

	it.each(['Run has no active approval session: run_1', 'Run has no pending approval: run_1'])(
		'supports a terminal 409 from a backend that has not restarted: %s',
		(message) => {
			expect(isHermesApprovalGoneError(new HermesRunsApiError(409, message))).toBe(true);
		}
	);
});
