import { describe, expect, it } from 'vitest';

import {
	isAguiPanelTopmost,
	isChatSidePanelVisible,
	resolveChatBasePanel
} from './chatSidePanelState';

describe('chatSidePanelState', () => {
	it('keeps the AG-UI artifact as the base panel while the expert overlay opens and closes', () => {
		const basePanel = resolveChatBasePanel(null, {
			artifactsVisible: false,
			aguiVisible: true,
			aguiJustOpened: true
		});

		expect(basePanel).toBe('agui');
		expect(isChatSidePanelVisible(basePanel, true)).toBe(true);
		expect(isChatSidePanelVisible(basePanel, false)).toBe(true);
	});

	it('falls back to the other visible artifact panel when the active base panel closes', () => {
		expect(
			resolveChatBasePanel('artifacts', {
				artifactsVisible: false,
				aguiVisible: true
			})
		).toBe('agui');

		expect(
			resolveChatBasePanel('agui', {
				artifactsVisible: true,
				aguiVisible: false
			})
		).toBe('artifacts');
	});

	it('uses the most recently opened artifact panel and releases the layout when all panels close', () => {
		expect(
			resolveChatBasePanel('agui', {
				artifactsVisible: true,
				aguiVisible: true,
				artifactsJustOpened: true
			})
		).toBe('artifacts');

		expect(
			resolveChatBasePanel('artifacts', {
				artifactsVisible: false,
				aguiVisible: false
			})
		).toBeNull();
		expect(isChatSidePanelVisible(null, false)).toBe(false);
	});

	it('only treats the artifact as topmost when the expert overlay is closed', () => {
		expect(isAguiPanelTopmost(true, false)).toBe(true);
		expect(isAguiPanelTopmost(true, true)).toBe(false);
		expect(isAguiPanelTopmost(false, false)).toBe(false);
	});
});
