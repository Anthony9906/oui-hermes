import { describe, expect, it } from 'vitest';

import { getAgentApprovalExplanation } from './utils';

const approval = (overrides: Record<string, unknown> = {}) => ({
	command: '',
	description: '',
	pattern_key: '',
	pattern_keys: [],
	...overrides
});

describe('getAgentApprovalExplanation', () => {
	it('turns an internal deletion rule into an explicit user-facing warning', () => {
		const result = getAgentApprovalExplanation(
			approval({ command: 'rm -rf -- /tmp/report', description: 'delete in root path' })
		);

		expect(result).toContain('删除指定的文件或目录');
		expect(result).toContain('目标路径');
		expect(result).not.toContain('delete in root path');
	});

	it('explains direct script execution', () => {
		expect(
			getAgentApprovalExplanation(
				approval({ command: "bash -c 'deploy.sh'", description: 'script execution' })
			)
		).toContain('命令解释器');
	});

	it('keeps an already clear Chinese description', () => {
		expect(
			getAgentApprovalExplanation(approval({ description: '将文件上传到项目存储空间。' }))
		).toBe('将文件上传到项目存储空间。');
	});

	it('uses a safe generic explanation for unknown internal rules', () => {
		expect(getAgentApprovalExplanation(approval({ description: 'opaque_policy_17' }))).toContain(
			'安全策略保护'
		);
	});
});
