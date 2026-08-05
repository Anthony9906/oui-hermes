import { WEBUI_API_BASE_URL } from '$lib/constants';

export type HermesApprovalChoice = 'once' | 'session' | 'deny';

export class HermesRunsApiError extends Error {
	status: number;

	constructor(status: number, message: string) {
		super(message);
		this.name = 'HermesRunsApiError';
		this.status = status;
	}
}

const TERMINAL_APPROVAL_MESSAGE_PREFIXES = [
	'Run has no active approval session:',
	'Run has no pending approval:'
];

export const isHermesApprovalGoneError = (error: unknown) =>
	error instanceof HermesRunsApiError &&
	(error.status === 404 ||
		error.status === 410 ||
		(error.status === 409 &&
			TERMINAL_APPROVAL_MESSAGE_PREFIXES.some((prefix) => error.message.startsWith(prefix))));

const parseError = async (response: Response) => {
	try {
		const body = await response.json();
		return body?.detail ?? body?.error?.message ?? response.statusText;
	} catch {
		return response.statusText;
	}
};

export const getPendingHermesApprovals = async (token: string, chatId: string) => {
	const response = await fetch(
		`${WEBUI_API_BASE_URL}/hermes/approvals?chat_id=${encodeURIComponent(chatId)}`,
		{
			headers: { Authorization: `Bearer ${token}` }
		}
	);

	if (!response.ok) throw new HermesRunsApiError(response.status, await parseError(response));
	return response.json();
};

export const respondToHermesApproval = async (
	token: string,
	runId: string,
	chatId: string,
	approvalRequestId: string,
	choice: HermesApprovalChoice
) => {
	const response = await fetch(
		`${WEBUI_API_BASE_URL}/hermes/runs/${encodeURIComponent(runId)}/approval`,
		{
			method: 'POST',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({
				chat_id: chatId,
				approval_request_id: approvalRequestId,
				choice
			})
		}
	);

	if (!response.ok) throw new HermesRunsApiError(response.status, await parseError(response));
	return response.json();
};
