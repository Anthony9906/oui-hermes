export type ChatBasePanel = 'artifacts' | 'agui' | null;

type ResolveChatBasePanelOptions = {
	artifactsVisible: boolean;
	aguiVisible: boolean;
	artifactsJustOpened?: boolean;
	aguiJustOpened?: boolean;
};

export const resolveChatBasePanel = (
	currentPanel: ChatBasePanel,
	{
		artifactsVisible,
		aguiVisible,
		artifactsJustOpened = false,
		aguiJustOpened = false
	}: ResolveChatBasePanelOptions
): ChatBasePanel => {
	if (aguiJustOpened) return 'agui';
	if (artifactsJustOpened) return 'artifacts';

	if (currentPanel === 'agui' && aguiVisible) return 'agui';
	if (currentPanel === 'artifacts' && artifactsVisible) return 'artifacts';

	if (aguiVisible) return 'agui';
	if (artifactsVisible) return 'artifacts';

	return null;
};

export const isChatSidePanelVisible = (basePanel: ChatBasePanel, expertAgentVisible: boolean) =>
	basePanel !== null || expertAgentVisible;

export const isAguiPanelTopmost = (aguiVisible: boolean, expertAgentVisible: boolean) =>
	aguiVisible && !expertAgentVisible;
