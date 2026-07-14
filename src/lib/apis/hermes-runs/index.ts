import { WEBUI_API_BASE_URL } from '$lib/constants';

export type HermesApprovalChoice = 'once' | 'session' | 'deny';

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

	if (!response.ok) throw new Error(await parseError(response));
	return response.json();
};

export const respondToHermesApproval = async (
	token: string,
	runId: string,
	chatId: string,
	approvalRequestId: string,
	choice: HermesApprovalChoice
) => {
	const response = await fetch(`${WEBUI_API_BASE_URL}/hermes/runs/${encodeURIComponent(runId)}/approval`, {
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
	});

	if (!response.ok) throw new Error(await parseError(response));
	return response.json();
};
