import type { HermesApprovalRequest } from './stores/approvals';

type ApprovalRiskInput = Pick<
	HermesApprovalRequest,
	'command' | 'description' | 'pattern_key' | 'pattern_keys'
>;

const hasChinese = (value: string) => /[\u3400-\u9fff]/.test(value);

export const getAgentApprovalExplanation = (approval: ApprovalRiskInput): string => {
	const command = approval.command?.trim() ?? '';
	const description = approval.description?.trim() ?? '';
	const ruleText = [description, approval.pattern_key, ...(approval.pattern_keys ?? [])]
		.filter(Boolean)
		.join(' ')
		.toLowerCase();
	const evidence = `${ruleText} ${command.toLowerCase()}`;

	if (/\b(rm|rmdir|unlink)\b|\b(delete|remove)\b/.test(evidence)) {
		return 'Agent 准备删除指定的文件或目录。删除操作通常无法撤销，请重点核对下方命令中的目标路径是否正确。';
	}
	if (/\b(sudo|doas)\b|administrator|root privilege|elevated privilege/.test(evidence)) {
		return 'Agent 准备以较高的系统权限执行操作，可能影响系统文件或其他用户的数据。请确认命令及影响范围符合预期。';
	}
	if (
		/script execution|\b(?:bash|sh|zsh|python\d*|node|perl|ruby)\s+(?:-[a-z]*[ce]\b|-c\b)/.test(
			evidence
		)
	) {
		return 'Agent 准备通过命令解释器直接执行一段脚本。脚本可能包含多步操作，请确认代码内容、目标路径和工作目录可信。';
	}
	if (
		/\b(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b|internal (?:url|network)|private (?:url|network)/.test(
			evidence
		)
	) {
		return 'Agent 准备访问本机或内网服务。请确认目标地址、端口和请求内容可信，且不会泄露敏感信息。';
	}
	if (/\b(write|overwrite|modify|replace|truncate)\b|\b(?:tee|sed)\b/.test(evidence)) {
		return 'Agent 准备写入或修改文件。请核对下方命令中的目标路径和修改内容，避免覆盖重要数据。';
	}
	if (/\b(install|upgrade|update)\b|\b(?:npm|pnpm|yarn|pip|uv|brew|apt|dnf)\b/.test(evidence)) {
		return 'Agent 准备安装或更新软件包，这可能改变当前环境或引入新的依赖。请确认软件包名称和来源可信。';
	}
	if (description && hasChinese(description)) {
		return description;
	}

	return '该操作受到安全策略保护。请核对下方命令、目标路径和可能影响，确认符合你的预期后再允许。';
};
