<script lang="ts">
	import { v4 as uuidv4 } from 'uuid';
	import { toast } from 'svelte-sonner';
	import { PaneGroup, Pane } from 'paneforge';

	import { getContext, onMount, tick } from 'svelte';
	import { fade } from 'svelte/transition';
	const i18n: Writable<i18nType> = getContext('i18n');

	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { get, type Unsubscriber, type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { WEBUI_BASE_URL } from '$lib/constants';
	import equal from 'fast-deep-equal';

	import {
		chatId,
		chats,
		config,
		type Model,
		models,
		tags as allTags,
		settings,
		showSidebar,
		WEBUI_NAME,
		banners,
		user,
		socket,
		audioQueue,
		chatTitleUpdateSignal,
		showControls,
		showCallOverlay,
		currentChatPage,
		temporaryChatEnabled,
		mobile,
		chatTitle,
		showArtifacts,
		artifactContents,
		tools,
		toolServers,
		terminalServers,
		functions,
		folderRefreshSignal,
		newChatFolder,
		selectedFolder,
		pinnedChats,
		showEmbeds,
		selectedTerminalId,
		showFileNavPath,
		showFileNavDir,
		chatRequestQueues,
		desktopEvent
	} from '$lib/stores';

	import { WEBUI_API_BASE_URL } from '$lib/constants';

	import {
		convertMessagesToHistory,
		copyToClipboard,
		getMessageContentParts,
		createMessagesList,
		getPromptVariables,
		processDetails,
		removeAllDetails,
		getCodeBlockContents,
		isYoutubeUrl,
		displayFileHandler
	} from '$lib/utils';
	import { AudioQueue } from '$lib/utils/audio';

	import {
		archiveChatById,
		createNewChat,
		getAllTags,
		getChatById,
		getChatList,
		getPinnedChatList,
		getTagsById,
		updateChatById,
		updateChatFolderIdById
	} from '$lib/apis/chats';
	import { generateOpenAIChatCompletion } from '$lib/apis/openai';
	import { processWeb, processWebSearch, processYoutubeVideo } from '$lib/apis/retrieval';
	import { getAndUpdateUserLocation, getUserSettings } from '$lib/apis/users';
	import {
		generateQueries,
		chatAction,
		generateMoACompletion,
		stopTask,
		stopTasksByChatId,
		getTaskIdsByChatId
	} from '$lib/apis';
	import { getTools } from '$lib/apis/tools';
	import { uploadFile } from '$lib/apis/files';
	import { createOpenAITextStream } from '$lib/apis/streaming';
	import { getFunctions } from '$lib/apis/functions';
	import { updateFolderById } from '$lib/apis/folders';
	import {
		buildExpertSkillPrompt,
		clearExpertAgentStartRequest,
		expertAgentStartRequest,
		showExpertAgentDrawer,
		type ExpertAgentStartRequest
	} from '$lib/stores/expertAgents';

	import Banner from '../common/Banner.svelte';
	import MessageInput from '$lib/components/chat/MessageInput.svelte';
	import Messages from '$lib/components/chat/Messages.svelte';
	import Navbar from '$lib/components/chat/Navbar.svelte';
	import ChatSidePanel from './ChatSidePanel.svelte';
	import EventConfirmDialog from '../common/ConfirmDialog.svelte';
	import Placeholder from './Placeholder.svelte';
	import FilesOverlay from './MessageInput/FilesOverlay.svelte';
	import NotificationToast from '../NotificationToast.svelte';
	import Spinner from '../common/Spinner.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Sidebar from '../icons/Sidebar.svelte';
	import Image from '../common/Image.svelte';
	import { getBanners } from '$lib/apis/configs';

	export let chatIdProp = '';

	let loading = true;

	const eventTarget = new EventTarget();
	let messageInput: MessageInput | undefined;

	let autoScroll = true;
	let processing = '';
	let messagesContainerElement: HTMLDivElement;
	let activeExpertSkillName = '';

	const focusChatInput = ({ defer = false } = {}) => {
		if ($mobile || $showCallOverlay) {
			return;
		}

		const focus = () => document.getElementById('chat-input')?.focus();

		if (defer) {
			setTimeout(focus, 0);
			return;
		}

		focus();
	};

	const buildChatMeta = (meta = chat?.chat?.meta ?? {}) => {
		const nextMeta = { ...(meta ?? {}) };

		if (activeExpertSkillName) {
			nextMeta.expert_skill_name = activeExpertSkillName;
		} else {
			delete nextMeta.expert_skill_name;
		}

		return nextMeta;
	};

	const getNewChatFolder = () => ($newChatFolder === undefined ? $selectedFolder : $newChatFolder);
	const getNewChatFolderId = () => getNewChatFolder()?.id ?? null;
	const refreshFolderChatList = (folderId = currentChatFolderId) => {
		if (folderId) {
			folderRefreshSignal.set({ id: Date.now(), folderId });
		}
	};

	const refreshSidebarChatTitle = async (targetChatId: string, folderId = currentChatFolderId) => {
		const updatedChat = await getChatById(localStorage.token, targetChatId).catch(() => null);
		const updatedTitle = updatedChat?.chat?.title ?? updatedChat?.title ?? '';
		const newChatTitle = $i18n.t('New Chat');

		if (!updatedTitle || updatedTitle === 'New Chat' || updatedTitle === newChatTitle) {
			return false;
		}

		if ($chatId === targetChatId) {
			chatTitle.set(updatedTitle);
		}
		chatTitleUpdateSignal.set({ id: Date.now(), chatId: targetChatId, title: updatedTitle });

		currentChatPage.set(1);
		await chats.set(await getChatList(localStorage.token, $currentChatPage));
		refreshFolderChatList(folderId ?? updatedChat?.folder_id ?? null);

		return true;
	};

	const watchGeneratedChatTitle = async (targetChatId: string, folderId = currentChatFolderId) => {
		if (!targetChatId || titleRefreshWatchers.has(targetChatId)) {
			return;
		}

		titleRefreshWatchers.add(targetChatId);

		try {
			for (let i = 0; i < 90; i++) {
				await new Promise((resolve) => setTimeout(resolve, 1000));

				if (await refreshSidebarChatTitle(targetChatId, folderId)) {
					return;
				}
			}
		} finally {
			titleRefreshWatchers.delete(targetChatId);
		}
	};

	const getExpertSkillNameFromChatContent = (chatContent) => {
		const messages = [
			...Object.values(chatContent?.history?.messages ?? {}),
			...(Array.isArray(chatContent?.messages) ? chatContent.messages : [])
		];

		for (const message of messages) {
			const content = typeof message?.content === 'string' ? message.content : '';

			const templateMatch = content.match(
				/当前对话启用专家技能：\s+(?:\*\*)?(.+?)(?:\*\*)?(?:\n|$)/
			);
			if (templateMatch?.[1]) {
				return templateMatch[1];
			}

			const legacyMatch = content.match(/现在开始使用专家技能\s+(.+?)\s+来完成/);
			if (legacyMatch?.[1]) {
				return legacyMatch[1];
			}
		}

		return '';
	};

	const getSuggestionExpertSkillName = (suggestion) => {
		const title = suggestion?.title;
		const primaryTitle = Array.isArray(title) ? title[0] : title;
		const name = typeof primaryTitle === 'string' ? primaryTitle.trim() : '';

		if (name) {
			return name;
		}

		const content = typeof suggestion?.content === 'string' ? suggestion.content.trim() : '';
		return content ? content.slice(0, 50) : $i18n.t('Expert Agent');
	};

	let navbarElement;

	let showEventConfirmation = false;
	let eventConfirmationTitle = '';
	let eventConfirmationMessage = '';
	let eventConfirmationInput = false;
	let eventConfirmationInputPlaceholder = '';
	let eventConfirmationInputValue = '';
	let eventConfirmationInputType = '';
	let eventCallback = null;

	let selectedModels = [''];
	let atSelectedModel: Model | undefined;
	let selectedModelIds = [];
	$: if (atSelectedModel !== undefined) {
		selectedModelIds = [atSelectedModel.id];
	} else {
		selectedModelIds = selectedModels;
	}

	let selectedToolIds = [];
	let selectedFilterIds = [];
	let pendingOAuthTools = [];

	let imageGenerationEnabled = false;
	let webSearchEnabled = false;
	let codeInterpreterEnabled = false;

	let showCommands = false;
	let processingExpertAgentStart = false;
	let activeEventsSocket: any = null;

	let generating = false;
	let dragged = false;
	let generationController = null;

	let chat = null;
	let currentChatFolderId = null;
	const titleRefreshWatchers = new Set<string>();
	let tags = [];

	let chatTasks = [];

	let history = {
		messages: {},
		currentId: null
	};

	const bindChatEventSocket = (nextSocket) => {
		if (activeEventsSocket === nextSocket) {
			return;
		}

		activeEventsSocket?.off('events', chatEventHandler);
		activeEventsSocket = nextSocket;
		activeEventsSocket?.on('events', chatEventHandler);
	};

	const adoptChatIdFromEvent = async (eventChatId) => {
		if (!eventChatId || $chatId || $temporaryChatEnabled || eventChatId.startsWith('local:')) {
			return;
		}

		await chatId.set(eventChatId);

		if (window.location.pathname === '/') {
			window.history.replaceState(history.state, '', `/c/${eventChatId}`);
		}

		currentChatPage.set(1);
		await chats.set(await getChatList(localStorage.token, $currentChatPage));
		refreshFolderChatList();
	};

	let taskIds = null;

	// Chat Input
	let prompt = '';
	let chatFiles = [];
	let files = [];

	$: if (chatIdProp) {
		navigateHandler();
	}

	const navigateHandler = async () => {
		// Mark the outgoing chat as read before loading the new one.
		// $chatId still holds the previous chat here — loadChat() updates it.
		if ($chatId && $chatId !== chatIdProp && !$temporaryChatEnabled) {
			updateLastReadAt($chatId);
		}

		loading = true;

		prompt = '';
		messageInput?.setText('');

		files = [];
		selectedToolIds = [];
		selectedFilterIds = [];
		webSearchEnabled = false;
		imageGenerationEnabled = false;

		const storageChatInput = sessionStorage.getItem(
			`chat-input${chatIdProp ? `-${chatIdProp}` : ''}`
		);

		if (chatIdProp && (await loadChat())) {
			await tick();
			loading = false;
			window.setTimeout(() => scrollToBottom(), 0);

			await tick();

			// Mark chat read when initially loading it
			if (chatIdProp && !$temporaryChatEnabled) {
				updateLastReadAt(chatIdProp);
			}

			// Process any queued requests if the chat is idle
			const lastMessage = history.currentId ? history.messages[history.currentId] : null;
			const isIdle = !lastMessage || lastMessage.role !== 'assistant' || lastMessage.done;
			if (isIdle) {
				await processNextInQueue(chatIdProp);
			}

			if (storageChatInput) {
				try {
					const input = JSON.parse(storageChatInput);

					if (!$temporaryChatEnabled) {
						messageInput?.setText(input.prompt);
						files = input.files;
						selectedToolIds = input.selectedToolIds;
						selectedFilterIds = input.selectedFilterIds;
						webSearchEnabled = input.webSearchEnabled;
						imageGenerationEnabled = input.imageGenerationEnabled;
						codeInterpreterEnabled = input.codeInterpreterEnabled;
					}
				} catch (e) {}
			} else {
				await setDefaults();
			}

			focusChatInput();
		} else {
			await goto('/');
		}
	};

	const onSelect = async (e) => {
		const { type, data, prompt: suggestion } = e;

		if (type === 'prompt') {
			if (suggestion) {
				await startExpertAgentChat({
					skill_name: getSuggestionExpertSkillName(suggestion),
					prompt: data,
					nonce: uuidv4()
				});
				return;
			}

			messageInput?.setText(data, async () => {
				if (!($settings?.insertSuggestionPrompt ?? false)) {
					await tick();
					submitHandler(prompt);
				}
			});
		}
	};

	$: if (selectedModels && chatIdProp !== '') {
		saveSessionSelectedModels();
	}

	const saveSessionSelectedModels = () => {
		const selectedModelsString = JSON.stringify(selectedModels);
		if (
			selectedModels.length === 0 ||
			(selectedModels.length === 1 && selectedModels[0] === '') ||
			sessionStorage.selectedModels === selectedModelsString
		) {
			return;
		}
		sessionStorage.selectedModels = selectedModelsString;
		console.log('saveSessionSelectedModels', selectedModels, sessionStorage.selectedModels);
	};

	let oldSelectedModelIds = [''];
	$: if (!equal(selectedModelIds, oldSelectedModelIds)) {
		onSelectedModelIdsChange();
	}

	const onSelectedModelIdsChange = () => {
		resetInput();
		oldSelectedModelIds = structuredClone(selectedModelIds);
	};

	const resetInput = () => {
		selectedToolIds = [];
		selectedFilterIds = [];
		pendingOAuthTools = [];
		webSearchEnabled = false;
		imageGenerationEnabled = false;
		codeInterpreterEnabled = false;

		if (selectedModelIds.filter((id) => id).length > 0) {
			setDefaults();
		}
	};

	const setDefaults = async () => {
		if (!$tools) {
			tools.set(await getTools(localStorage.token));
		}
		if (!$functions) {
			functions.set(await getFunctions(localStorage.token));
		}
		if (selectedModels.length !== 1 && !atSelectedModel) {
			return;
		}

		const model = atSelectedModel ?? $models.find((m) => m.id === selectedModels[0]);
		if (model) {
			// Set Default Tools
			if (model?.info?.meta?.toolIds) {
				const defaultIds = [
					...new Set(
						[...(model?.info?.meta?.toolIds ?? [])].filter((id) => $tools.find((t) => t.id === id))
					)
				];

				// Separate unauthenticated OAuth tools
				const unauthed = [];
				const authed = [];
				for (const id of defaultIds) {
					const tool = $tools.find((t) => t.id === id);
					if (tool && tool.authenticated === false) {
						const parts = id.split(':');
						const serverId = parts.at(-1) ?? id;
						const authType =
							parts.length > 1 ? (parts[0] === 'server' ? parts[1] : parts[0]) : null;
						unauthed.push({ id, name: tool.name ?? id, serverId, authType });
					} else {
						authed.push(id);
					}
				}
				selectedToolIds = authed;
				pendingOAuthTools = unauthed;
			} else if ($settings?.tools) {
				selectedToolIds = $settings.tools;
			} else {
				selectedToolIds = selectedToolIds.filter((id) => !id.startsWith('direct_server:'));
			}

			// Set Default Filters (Toggleable only)
			if (model?.info?.meta?.defaultFilterIds) {
				selectedFilterIds = model.info.meta.defaultFilterIds.filter((id) =>
					model?.filters?.find((f) => f.id === id)
				);
			}

			// Set Default Features
			if (model?.info?.meta?.defaultFeatureIds) {
				if (
					model.info?.meta?.capabilities?.['image_generation'] &&
					$config?.features?.enable_image_generation &&
					($user?.role === 'admin' || $user?.permissions?.features?.image_generation)
				) {
					imageGenerationEnabled = model.info.meta.defaultFeatureIds.includes('image_generation');
				}

				if (
					model.info?.meta?.capabilities?.['web_search'] &&
					$config?.features?.enable_web_search &&
					($user?.role === 'admin' || $user?.permissions?.features?.web_search)
				) {
					webSearchEnabled = model.info.meta.defaultFeatureIds.includes('web_search');
				}

				if (
					model.info?.meta?.capabilities?.['code_interpreter'] &&
					$config?.features?.enable_code_interpreter &&
					($user?.role === 'admin' || $user?.permissions?.features?.code_interpreter)
				) {
					codeInterpreterEnabled = model.info.meta.defaultFeatureIds.includes('code_interpreter');
				}
			}

			// Set Default Terminal
			if (model?.info?.meta?.terminalId) {
				selectedTerminalId.set(model.info.meta.terminalId);
			}
		}
	};

	const showMessage = async (message, scroll = true) => {
		const _chatId = JSON.parse(JSON.stringify($chatId));
		let _messageId = JSON.parse(JSON.stringify(message.id));

		let messageChildrenIds = [];
		if (_messageId === null) {
			messageChildrenIds = Object.keys(history.messages).filter(
				(id) => history.messages[id].parentId === null
			);
		} else {
			messageChildrenIds = history.messages[_messageId].childrenIds;
		}

		while (messageChildrenIds.length !== 0) {
			_messageId = messageChildrenIds.at(-1);
			messageChildrenIds = history.messages[_messageId].childrenIds;
		}

		history.currentId = _messageId;

		await tick();

		if (($settings?.scrollOnBranchChange ?? true) && scroll) {
			const messageElement = document.getElementById(`message-${message.id}`);
			if (messageElement) {
				messageElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
			}
		}

		await tick();
		await tick();
		await tick();

		saveChatHandler(_chatId, history);
	};

	const updateLastReadAt = (id) => {
		$socket?.emit('events:chat', {
			chat_id: id,
			data: { type: 'last_read_at' }
		});
	};

	const terminalEventHandler = (type: string, data: any) => {
		if (type === 'terminal:display_file') {
			if (!data?.path) return;
			displayFileHandler(data.path, { showControls, showFileNavPath });
		} else if (type === 'terminal:write_file' || type === 'terminal:replace_file_content') {
			if (!data?.path) return;
			showFileNavDir.set(data.path);
		} else if (type === 'terminal:run_command') {
			showFileNavDir.set('/');
		}
	};

	const chatEventHandler = async (event, cb) => {
		console.log(event);

		const eventMessage = event?.message_id ? history.messages[event.message_id] : null;
		const isCurrentChatEvent = event.chat_id === $chatId;
		const isKnownLocalMessageEvent = eventMessage && event.chat_id;

		if (isCurrentChatEvent || isKnownLocalMessageEvent) {
			if (!isCurrentChatEvent) {
				await adoptChatIdFromEvent(event.chat_id);
			}

			await tick();
			let message = eventMessage ?? history.messages[event.message_id];
			const type = event?.data?.type ?? null;
			const data = event?.data?.data ?? null;

			if (type === 'chat:title') {
				chatTitle.set(data);
				chatTitleUpdateSignal.set({ id: Date.now(), chatId: event.chat_id, title: data });
				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, $currentChatPage));
				refreshFolderChatList();
				return;
			}

			if (message) {
				if (type === 'status') {
					if (message?.statusHistory) {
						message.statusHistory.push(data);
					} else {
						message.statusHistory = [data];
					}
				} else if (type === 'chat:completion') {
					chatCompletionEventHandler(data, message, event.chat_id);
				} else if (type === 'chat:tasks:cancel') {
					if (event.message_id === history.currentId) {
						taskIds = null;
						// Set all response messages to done
						for (const messageId of history.messages[message.parentId].childrenIds) {
							history.messages[messageId].done = true;
						}
						await processNextInQueue($chatId);
					} else {
						message.done = true;
					}
				} else if (type === 'chat:message:delta' || type === 'message') {
					message.content += data.content;
				} else if (type === 'chat:message' || type === 'replace') {
					message.content = data.content;
				} else if (type === 'chat:message:files' || type === 'files') {
					message.files = data.files;
				} else if (type === 'chat:message:tasks') {
					chatTasks = data.tasks;
				} else if (type === 'chat:message:embeds' || type === 'embeds') {
					message.embeds = data.embeds;

					// Auto-scroll to the embed once it's rendered in the DOM
					await tick();
					setTimeout(() => {
						const embedEl = document.getElementById(`${event.message_id}-embeds-container`);
						if (embedEl) {
							embedEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
						}
					}, 100);
				} else if (type === 'chat:message:error') {
					message.error = data.error;
				} else if (type === 'chat:message:follow_ups') {
					message.followUps = data.follow_ups;

					if (autoScroll) {
						scrollToBottom('smooth');
					}
				} else if (type === 'chat:outlet') {
					// Outlet filter ran on backend — sync in-memory state
					const outletMessages = data.messages ?? [];
					for (const msg of outletMessages) {
						if (msg?.id && history.messages[msg.id]) {
							const existing = history.messages[msg.id];
							if (existing.content !== msg.content) {
								history.messages[msg.id] = {
									...existing,
									originalContent: existing.content,
									...msg
								};
							}
						}
					}
					history = history;
					return; // Patches history.messages directly; skip the trailing write-back.
				} else if (type === 'chat:message:favorite') {
					// Update message favorite status
					message.favorite = data.favorite;
				} else if (type === 'chat:tags') {
					chat = await getChatById(localStorage.token, $chatId);
					allTags.set(await getAllTags(localStorage.token));
				} else if (type === 'source' || type === 'citation') {
					if (data?.type === 'code_execution') {
						// Code execution; update existing code execution by ID, or add new one.
						if (!message?.code_executions) {
							message.code_executions = [];
						}

						const existingCodeExecutionIndex = message.code_executions.findIndex(
							(execution) => execution.id === data.id
						);

						if (existingCodeExecutionIndex !== -1) {
							message.code_executions[existingCodeExecutionIndex] = data;
						} else {
							message.code_executions.push(data);
						}

						message.code_executions = message.code_executions;
					} else {
						// Regular source.
						if (message?.sources) {
							message.sources.push(data);
						} else {
							message.sources = [data];
						}
					}
				} else if (type === 'notification') {
					const toastType = data?.type ?? 'info';
					const toastContent = data?.content ?? '';

					if (toastType === 'success') {
						toast.success(toastContent);
					} else if (toastType === 'error') {
						toast.error(toastContent);
					} else if (toastType === 'warning') {
						toast.warning(toastContent);
					} else {
						toast.info(toastContent);
					}
				} else if (type === 'confirmation') {
					eventCallback = cb;

					eventConfirmationInput = false;
					showEventConfirmation = true;

					eventConfirmationTitle = data.title;
					eventConfirmationMessage = data.message;
				} else if (type === 'execute') {
					eventCallback = cb;

					try {
						// Use Function constructor to evaluate code in a safer way
						const asyncFunction = new Function(`return (async () => { ${data.code} })()`);
						const result = await asyncFunction(); // Await the result of the async function

						if (cb) {
							cb(result);
						}
					} catch (error) {
						console.error('Error executing code:', error);
					}
				} else if (type === 'input') {
					eventCallback = cb;

					eventConfirmationInput = true;
					showEventConfirmation = true;

					eventConfirmationTitle = data.title;
					eventConfirmationMessage = data.message;
					eventConfirmationInputPlaceholder = data.placeholder;
					eventConfirmationInputValue = data?.value ?? '';
					eventConfirmationInputType = data?.type ?? '';
				} else if (type.startsWith('terminal:')) {
					terminalEventHandler(type, data);
				} else {
					console.log('Unknown message type', data);
				}

				history.messages[event.message_id] = message;
			}
		} else {
			// Non-active chat completion: queue stays in the global store.
			// navigateHandler will process it when the user returns to that chat.
		}
	};

	const onMessageHandler = async (event: {
		origin: string;
		data: { type: string; text: string };
	}) => {
		const isSameOrigin = event.origin === window.origin;
		const type = event.data?.type;

		// Prompt-related message types only submit text to the chat input —
		// functionally equivalent to the user typing.  When same-origin is
		// enabled they go through immediately.  When it is disabled (opaque
		// origin) we show a confirmation dialog so the user stays in control.
		const iframePromptTypes = ['input:prompt', 'input:prompt:submit', 'action:submit'];

		if (!isSameOrigin && !iframePromptTypes.includes(type)) {
			return;
		}

		if (type === 'action:submit') {
			console.debug(event.data.text);

			if (prompt !== '') {
				await tick();
				submitHandler(prompt);
			}
		}

		if (type === 'input:prompt') {
			console.debug(event.data.text);

			if (document.getElementById('chat-input')) {
				messageInput?.setText(event.data.text);
				focusChatInput();
			}
		}

		if (type === 'input:prompt:submit') {
			console.debug(event.data.text);

			if (event.data.text !== '') {
				if (isSameOrigin) {
					await tick();
					submitHandler(event.data.text);
				} else {
					// Cross-origin: ask user to confirm before submitting
					eventConfirmationInput = false;
					eventConfirmationTitle = $i18n.t('Confirm Prompt from Embed');
					eventConfirmationMessage = event.data.text;
					eventCallback = async (confirmed: boolean) => {
						if (confirmed) {
							await tick();
							submitHandler(event.data.text);
						}
					};
					showEventConfirmation = true;
				}
			}
		}
	};

	const savedModelIds = async () => {
		if (
			$selectedFolder &&
			selectedModels.filter((modelId) => modelId !== '').length > 0 &&
			!equal($selectedFolder?.data?.model_ids, selectedModels)
		) {
			const res = await updateFolderById(localStorage.token, $selectedFolder.id, {
				data: {
					model_ids: selectedModels
				}
			});
		}
	};

	$: if (selectedModels !== null) {
		savedModelIds();
	}

	const stopAudio = () => {
		try {
			$audioQueue?.stop();
		} catch {}
	};

	const waitForExpertAgentChatReady = async () => {
		for (let i = 0; i < 50; i++) {
			await tick();

			const availableModels = $models
				.filter((m) => !(m?.info?.meta?.hidden ?? false))
				.map((m) => m.id);

			const selectedAvailableModels = selectedModels.filter((modelId) =>
				availableModels.includes(modelId)
			);

			if (selectedAvailableModels.length > 0 && !equal(selectedModels, selectedAvailableModels)) {
				selectedModels = selectedAvailableModels;
			}

			if (
				availableModels.length > 0 &&
				(selectedModels.length === 0 || selectedModels.every((modelId) => !modelId))
			) {
				selectedModels = [
					availableModels.includes('expertagent') ? 'expertagent' : availableModels[0]
				];
			}

			if (!loading && selectedModels.some((modelId) => modelId)) {
				return true;
			}

			await new Promise((resolve) => setTimeout(resolve, 50));
		}

		return false;
	};

	const startExpertAgentChat = async (request: ExpertAgentStartRequest) => {
		if (processingExpertAgentStart) {
			return;
		}

		processingExpertAgentStart = true;

		try {
			const ready = await waitForExpertAgentChatReady();
			if (!ready) {
				toast.error($i18n.t('Model not selected'));
				return;
			}

			clearExpertAgentStartRequest();
			activeExpertSkillName = request.skill_name;
			await submitHandler(request.prompt);
		} finally {
			processingExpertAgentStart = false;
		}
	};

	onMount(() => {
		loading = true;
		console.log('mounted');
		window.addEventListener('message', onMessageHandler);
		const socketSubscribe = socket.subscribe(bindChatEventSocket);

		$audioQueue?.destroy();

		const audioQueueInstance = new AudioQueue(document.getElementById('audioElement'));
		audioQueue.set(audioQueueInstance);

		// Restore direct terminal enabled states based on persisted selectedTerminalId
		if ($settings?.terminalServers?.length) {
			settings.set({
				...$settings,
				terminalServers: ($settings.terminalServers ?? []).map((s) => ({
					...s,
					enabled: $selectedTerminalId !== null && s.url === $selectedTerminalId
				}))
			});
		}

		const pageSubscribe = page.subscribe(async (p) => {
			if (p.url.pathname === '/') {
				await tick();
				await initNewChat();

				// Re-fetch banners on navigation to homepage so newly configured banners appear
				try {
					banners.set(await getBanners(localStorage.token).catch(() => []));
				} catch (e) {
					console.error('Failed to refresh banners:', e);
				}
			}

			stopAudio();
		});

		const selectedFolderSubscribe = selectedFolder.subscribe(async (folder) => {
			await tick();
			if (folder?.data?.model_ids && !equal(selectedModels, folder.data.model_ids)) {
				selectedModels = folder.data.model_ids;

				console.log('Set selectedModels from folder data:', selectedModels);
			}
		});

		const expertAgentStartSubscribe = expertAgentStartRequest.subscribe((request) => {
			if (request) {
				void startExpertAgentChat(request);
			}
		});

		const storageChatInput = sessionStorage.getItem(
			`chat-input${chatIdProp ? `-${chatIdProp}` : ''}`
		);

		const init = async () => {
			if (!chatIdProp) {
				loading = false;
				await tick();
			}

			if (storageChatInput) {
				prompt = '';
				messageInput?.setText('');

				files = [];
				selectedToolIds = [];
				selectedFilterIds = [];
				webSearchEnabled = false;
				imageGenerationEnabled = false;
				codeInterpreterEnabled = false;

				try {
					const input = JSON.parse(storageChatInput);

					if (!$temporaryChatEnabled) {
						messageInput?.setText(input.prompt);
						files = input.files;
						selectedToolIds = input.selectedToolIds;
						selectedFilterIds = input.selectedFilterIds;
						webSearchEnabled = input.webSearchEnabled;
						imageGenerationEnabled = input.imageGenerationEnabled;
						codeInterpreterEnabled = input.codeInterpreterEnabled;
					}
				} catch (e) {}
			}

			focusChatInput();
		};
		init();

		return () => {
			try {
				if (chatIdProp && !$temporaryChatEnabled) {
					updateLastReadAt(chatIdProp);
				}
				pageSubscribe();
				selectedFolderSubscribe();
				expertAgentStartSubscribe();
				window.removeEventListener('message', onMessageHandler);
				socketSubscribe();
				activeEventsSocket?.off('events', chatEventHandler);
				activeEventsSocket = null;
				audioQueueInstance?.destroy();
				audioQueue.set(null);
			} catch (e) {
				console.error(e);
			}
		};
	});

	// File upload functions

	const ensureChatId = async () => {
		if ($chatId) {
			return $chatId;
		}

		const id = uuidv4();
		await chatId.set(id);
		return id;
	};

	const uploadGoogleDriveFile = async (fileData) => {
		console.log('Starting uploadGoogleDriveFile with:', {
			id: fileData.id,
			name: fileData.name,
			url: fileData.url,
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		// Validate input
		if (!fileData?.id || !fileData?.name || !fileData?.url || !fileData?.headers?.Authorization) {
			throw new Error('Invalid file data provided');
		}

		const tempItemId = uuidv4();
		const fileItem = {
			type: 'file',
			file: '',
			id: null,
			url: fileData.url,
			name: fileData.name,
			collection_name: '',
			status: 'uploading',
			error: '',
			itemId: tempItemId,
			size: 0
		};

		try {
			files = [...files, fileItem];
			console.log('Processing web file with URL:', fileData.url);

			// Configure fetch options with proper headers
			const fetchOptions = {
				headers: {
					Authorization: fileData.headers.Authorization,
					Accept: '*/*'
				},
				method: 'GET'
			};

			// Attempt to fetch the file
			console.log('Fetching file content from Google Drive...');
			const fileResponse = await fetch(fileData.url, fetchOptions);

			if (!fileResponse.ok) {
				const errorText = await fileResponse.text();
				throw new Error(`Failed to fetch file (${fileResponse.status}): ${errorText}`);
			}

			// Get content type from response
			const contentType = fileResponse.headers.get('content-type') || 'application/octet-stream';
			console.log('Response received with content-type:', contentType);

			// Convert response to blob
			console.log('Converting response to blob...');
			const fileBlob = await fileResponse.blob();

			if (fileBlob.size === 0) {
				throw new Error('Retrieved file is empty');
			}

			console.log('Blob created:', {
				size: fileBlob.size,
				type: fileBlob.type || contentType
			});

			// Create File object with proper MIME type
			const file = new File([fileBlob], fileData.name, {
				type: fileBlob.type || contentType
			});

			console.log('File object created:', {
				name: file.name,
				size: file.size,
				type: file.type
			});

			if (file.size === 0) {
				throw new Error('Created file is empty');
			}

			const uploadChatId = await ensureChatId();

			// If the file is an audio file, provide the language for STT.
			let metadata = uploadChatId ? { chat_id: uploadChatId } : null;
			if (
				(file.type.startsWith('audio/') || file.type.startsWith('video/')) &&
				$settings?.audio?.stt?.language
			) {
				metadata = {
					...(metadata ?? {}),
					language: $settings?.audio?.stt?.language
				};
			}

			// Upload file to server
			console.log('Uploading file to server...');
			const uploadedFile = await uploadFile(localStorage.token, file, metadata);

			if (!uploadedFile) {
				throw new Error('Server returned null response for file upload');
			}

			console.log('File uploaded successfully:', uploadedFile);

			// Update file item with upload results
			fileItem.status = 'uploaded';
			fileItem.file = uploadedFile;
			fileItem.id = uploadedFile.id;
			fileItem.size = file.size;
			fileItem.collection_name = uploadedFile?.meta?.collection_name;
			fileItem.url = `${uploadedFile.id}`;

			files = files;
			toast.success($i18n.t('File uploaded successfully'));
		} catch (e) {
			console.error('Error uploading file:', e);
			files = files.filter((f) => f.itemId !== tempItemId);
			toast.error(
				$i18n.t('Error uploading file: {{error}}', {
					error: e.message || 'Unknown error'
				})
			);
		}
	};

	const uploadWeb = async (urls) => {
		if ($user?.role !== 'admin' && !($user?.permissions?.chat?.web_upload ?? true)) {
			toast.error($i18n.t('You do not have permission to upload web content.'));
			return;
		}

		if (!Array.isArray(urls)) {
			urls = [urls];
		}

		// Create file items first
		const fileItems = urls.map((url) => ({
			type: 'text',
			name: url,
			collection_name: '',
			status: 'uploading',
			context: 'full',
			url,
			error: ''
		}));

		// Display all items at once
		files = [...files, ...fileItems];

		for (const fileItem of fileItems) {
			try {
				const res = isYoutubeUrl(fileItem.url)
					? await processYoutubeVideo(localStorage.token, fileItem.url)
					: await processWeb(localStorage.token, '', fileItem.url);

				if (res) {
					fileItem.status = 'uploaded';
					fileItem.collection_name = res.collection_name;
					fileItem.file = {
						...res.file,
						...fileItem.file
					};
				}

				files = [...files];
			} catch (e) {
				files = files.filter((f) => f.name !== url);
				toast.error(`${e}`);
			}
		}
	};

	const onUpload = async (event) => {
		const { type, data } = event;

		if (type === 'google-drive') {
			await uploadGoogleDriveFile(data);
		} else if (type === 'web') {
			await uploadWeb(data);
		}
	};

	const onHistoryChange = (history) => {
		if (history) {
			clearTimeout(contentsRAF);
			contentsRAF = setTimeout(() => {
				getContents();
				contentsRAF = null;
			}, 0);
		} else {
			artifactContents.set([]);
		}
	};

	$: onHistoryChange(history);

	const getContents = () => {
		const messages = history ? createMessagesList(history, history.currentId) : [];
		let contents = [];
		const decodeEntityText = (value = '') =>
			value
				.replace(/&quot;/g, '"')
				.replace(/&#39;/g, "'")
				.replace(/&apos;/g, "'")
				.replace(/&amp;/g, '&')
				.replace(/&lt;/g, '<')
				.replace(/&gt;/g, '>');
		const getHtmlAttribute = (tag = '', name = '') => {
			const match = tag.match(new RegExp(`${name}\\s*=\\s*("([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i'));
			return decodeEntityText(match?.[2] ?? match?.[3] ?? match?.[4] ?? '').trim();
		};
		const getOnlyIframeTag = (value = '') => {
			const trimmed = value.trim();
			const match = trimmed.match(/^<iframe\b[\s\S]*?<\/iframe>\s*$/i);
			return match?.[0]?.match(/<iframe\b[^>]*>/i)?.[0] ?? '';
		};

		messages.forEach((message) => {
			if (message?.role !== 'user' && message?.content) {
				const { codeBlocks: codeBlocks, htmlGroups: htmlGroups } = getCodeBlockContents(
					message.content
				);

				if (htmlGroups && htmlGroups.length > 0) {
					htmlGroups.forEach((group) => {
						const iframeTag =
							!group.css.trim() && !group.js.trim() ? getOnlyIframeTag(group.html) : '';
						const iframeSrc = iframeTag ? getHtmlAttribute(iframeTag, 'src') : '';
						if (iframeSrc) {
							contents = [
								...contents,
								{
									type: 'external-iframe',
									content: iframeSrc,
									source: group.html,
									title:
										getHtmlAttribute(iframeTag, 'title') ||
										getHtmlAttribute(iframeTag, 'aria-label') ||
										'Content'
								}
							];
							return;
						}

						const renderedContent = `
                        <!DOCTYPE html>
                        <html lang="en">
                        <head>
                            <meta charset="UTF-8">
                            <meta name="viewport" content="width=device-width, initial-scale=1.0">
							<${''}style>
								html,
								body {
									background-color: white; /* Ensure the iframe has a white background */
									margin: 0;
								}

								body > iframe {
									display: block;
									width: 100% !important;
									border: 0 !important;
									background: #fff;
								}

								${group.css}
							</${''}style>
                        </head>
                        <body>
                            ${group.html}

							<${''}script>
                            	${group.js}
							</${''}script>
                        </body>
                        </html>
                    `;
						contents = [...contents, { type: 'iframe', content: renderedContent }];
					});
				} else {
					// Check for SVG content
					for (const block of codeBlocks) {
						if (block.lang === 'svg' || (block.lang === 'xml' && block.code.includes('<svg'))) {
							contents = [...contents, { type: 'svg', content: block.code }];
						}
					}
				}
			}
		});

		artifactContents.set(contents);
	};

	//////////////////////////
	// Web functions
	//////////////////////////

	const initNewChat = async () => {
		console.log('initNewChat');
		activeExpertSkillName = '';
		await temporaryChatEnabled.set(false);

		const availableModels = $models
			.filter((m) => !(m?.info?.meta?.hidden ?? false))
			.map((m) => m.id);

		const defaultModels = $config?.default_models ? $config?.default_models.split(',') : [];

		if ($page.url.searchParams.get('models') || $page.url.searchParams.get('model')) {
			const urlModels = (
				$page.url.searchParams.get('models') ||
				$page.url.searchParams.get('model') ||
				''
			)?.split(',');

			if (urlModels.length === 1) {
				if (!$models.find((m) => m.id === urlModels[0])) {
					// Model not found; open model selector and prefill
					const modelSelectorButton = document.getElementById('model-selector-0-button');
					if (modelSelectorButton) {
						modelSelectorButton.click();
						await tick();

						const modelSelectorInput = document.getElementById('model-search-input');
						if (modelSelectorInput) {
							modelSelectorInput.focus();
							modelSelectorInput.value = urlModels[0];
							modelSelectorInput.dispatchEvent(new Event('input'));
						}
					}
				} else {
					// Model found; set it as selected
					selectedModels = urlModels;
				}
			} else {
				// Multiple models; set as selected
				selectedModels = urlModels;
			}

			// Unavailable models filtering
			selectedModels = selectedModels.filter((modelId) =>
				$models.map((m) => m.id).includes(modelId)
			);
		} else {
			if ($selectedFolder?.data?.model_ids) {
				// Set from folder model IDs
				selectedModels = $selectedFolder?.data?.model_ids;
			} else {
				if (sessionStorage.selectedModels) {
					// Set from session storage (temporary selection)
					selectedModels = JSON.parse(sessionStorage.selectedModels);
					sessionStorage.removeItem('selectedModels');
				} else {
					if ($settings?.models) {
						// Set from user settings
						selectedModels = $settings?.models;
					} else if (defaultModels && defaultModels.length > 0) {
						// Set from default models
						selectedModels = defaultModels;
					}
				}
			}

			// Unavailable & hidden models filtering
			selectedModels = selectedModels.filter((modelId) => availableModels.includes(modelId));
		}

		// Ensure at least one model is selected
		if (selectedModels.length === 0 || (selectedModels.length === 1 && selectedModels[0] === '')) {
			if (availableModels.length > 0) {
				if (defaultModels && defaultModels.length > 0) {
					selectedModels = defaultModels.filter((modelId) => availableModels.includes(modelId));
				}

				if (
					selectedModels.length === 0 ||
					(selectedModels.length === 1 && selectedModels[0] === '')
				) {
					// Only fall back to first available model if default models didn't resolve
					selectedModels = [availableModels?.at(0) ?? ''];
				}
			} else {
				selectedModels = [''];
			}
		}

		if ($mobile) {
			await showControls.set(false);
		}
		await showCallOverlay.set(false);
		await showArtifacts.set(false);

		if ($page.url.pathname.includes('/c/')) {
			window.history.replaceState(history.state, '', `/`);
		}

		autoScroll = true;

		resetInput();
		await chatId.set('');
		await chatTitle.set('');

		history = {
			messages: {},
			currentId: null
		};

		chatFiles = [];
		taskIds = null;
		chatTasks = [];

		if ($page.url.searchParams.get('youtube')) {
			await uploadWeb(`https://www.youtube.com/watch?v=${$page.url.searchParams.get('youtube')}`);
		}

		if ($page.url.searchParams.get('load-url')) {
			await uploadWeb($page.url.searchParams.get('load-url'));
		}

		if ($page.url.searchParams.get('web-search') === 'true') {
			webSearchEnabled = true;
		}

		if ($page.url.searchParams.get('image-generation') === 'true') {
			imageGenerationEnabled = true;
		}

		if ($page.url.searchParams.get('code-interpreter') === 'true') {
			codeInterpreterEnabled = true;
		}

		if ($page.url.searchParams.get('tools')) {
			selectedToolIds = $page.url.searchParams
				.get('tools')
				?.split(',')
				.map((id) => id.trim())
				.filter((id) => id);
		} else if ($page.url.searchParams.get('tool-ids')) {
			selectedToolIds = $page.url.searchParams
				.get('tool-ids')
				?.split(',')
				.map((id) => id.trim())
				.filter((id) => id);
		}

		// Restore tool selection after OAuth redirect
		const pendingToolId = sessionStorage.getItem('pendingOAuthToolId');
		if (pendingToolId) {
			sessionStorage.removeItem('pendingOAuthToolId');
			if (!selectedToolIds.includes(pendingToolId)) {
				selectedToolIds = [...selectedToolIds, pendingToolId];
			}
		}

		if ($page.url.searchParams.get('call') === 'true') {
			showCallOverlay.set(true);
		}

		// Consume one-shot desktop event (e.g. Spotlight query, call shortcut)
		if ($desktopEvent) {
			const event = $desktopEvent;
			desktopEvent.set(null);

			if (event.type === 'call') {
				setTimeout(() => {
					showCallOverlay.set(true);
				}, 0);
			} else if (event.type === 'query') {
				const query = event.data?.query;
				const eventFiles = event.data?.files;

				// Attach screenshot images from desktop (e.g. Spotlight region capture)
				if (eventFiles?.length) {
					for (const ef of eventFiles) {
						files = [
							...files,
							{
								type: 'image',
								url: ef.dataUrl,
								name: ef.name
							}
						];
					}
				}

				if (query || eventFiles?.length) {
					if (query) {
						messageInput?.setText(query);
					}
					await tick();
					submitHandler(query || '');
				}
			}
		} else if ($page.url.searchParams.get('expert-agent')) {
			const skillName = $page.url.searchParams.get('expert-agent') ?? '';
			if (skillName) {
				await startExpertAgentChat({
					skill_name: skillName,
					prompt: buildExpertSkillPrompt(skillName),
					nonce: $page.url.searchParams.get('expert-agent-start') ?? uuidv4()
				});
			}
		} else if ($page.url.searchParams.get('q')) {
			const q = $page.url.searchParams.get('q') ?? '';
			messageInput?.setText(q);

			if (q) {
				if (($page.url.searchParams.get('submit') ?? 'true') === 'true') {
					await tick();
					submitHandler(q);
				}
			}
		}

		selectedModels = selectedModels.map((modelId) =>
			$models.map((m) => m.id).includes(modelId) ? modelId : ''
		);

		focusChatInput({ defer: true });
	};

	const loadChat = async () => {
		chatId.set(chatIdProp);

		if ($temporaryChatEnabled) {
			temporaryChatEnabled.set(false);
		}

		chat = await getChatById(localStorage.token, $chatId).catch(async (error) => {
			await goto('/');
			return null;
		});

		if (chat) {
			currentChatFolderId = chat?.folder_id ?? null;

			tags = await getTagsById(localStorage.token, $chatId).catch(async (error) => {
				return [];
			});

			const chatContent = chat.chat;

			if (chatContent) {
				console.log(chatContent);

				selectedModels =
					(chatContent?.models ?? undefined) !== undefined
						? chatContent.models
						: [chatContent.models ?? ''];

				if (!($user?.role === 'admin' || ($user?.permissions?.chat?.multiple_models ?? true))) {
					selectedModels = selectedModels.length > 0 ? [selectedModels[0]] : [''];
				}

				activeExpertSkillName =
					chatContent?.meta?.expert_skill_name ??
					chat?.meta?.expert_skill_name ??
					getExpertSkillNameFromChatContent(chatContent);

				oldSelectedModelIds = structuredClone(selectedModels);

				history =
					(chatContent?.history ?? undefined) !== undefined
						? chatContent.history
						: convertMessagesToHistory(chatContent.messages);

				chatTitle.set(chatContent.title);

				chatFiles = chatContent?.files ?? [];

				// Load tasks from chat-level DB field
				chatTasks = chat?.tasks ?? [];

				autoScroll = true;
				await tick();

				if (history.currentId) {
					for (const message of Object.values(history.messages)) {
						if (
							message &&
							message.role === 'assistant' &&
							message.id !== history.currentId &&
							message.done !== false
						) {
							message.done = true;
						}
					}
				}

				const taskRes = await getTaskIdsByChatId(localStorage.token, $chatId).catch((error) => {
					return null;
				});

				if (taskRes) {
					taskIds = taskRes.task_ids;
				}

				// If no active tasks and current message is incomplete, generation was interrupted
				const currentMessage = history.currentId ? history.messages[history.currentId] : null;
				if (
					currentMessage &&
					currentMessage.role === 'assistant' &&
					!currentMessage.done &&
					(!taskIds || taskIds.length === 0)
				) {
					currentMessage.done = true;
				}

				await tick();

				return true;
			} else {
				return null;
			}
		}
	};

	const scrollToBottom = async (behavior = 'auto') => {
		await tick();
		if (messagesContainerElement) {
			messagesContainerElement.scrollTo({
				top: messagesContainerElement.scrollHeight,
				behavior
			});
		}
	};

	let scrollRAF = null;
	let contentsRAF = null;
	const scheduleScrollToBottom = () => {
		if (!scrollRAF) {
			scrollRAF = requestAnimationFrame(async () => {
				scrollRAF = null;
				await scrollToBottom();
			});
		}
	};

	let processingQueueChats = new Set<string>();

	const processNextInQueue = async (targetChatId: string) => {
		if (processingQueueChats.has(targetChatId)) return;

		const queue = $chatRequestQueues[targetChatId];
		if (!queue || queue.length === 0) return;

		processingQueueChats.add(targetChatId);
		try {
			const combinedPrompt = queue.map((m) => m.prompt).join('\n\n');
			const combinedFiles = queue.flatMap((m) => m.files);

			chatRequestQueues.update((q) => {
				const { [targetChatId]: _, ...rest } = q;
				return rest;
			});

			await submitPrompt(combinedPrompt, combinedFiles);
		} finally {
			processingQueueChats.delete(targetChatId);
		}
	};

	const chatCompletedHandler = async (_chatId, modelId, responseMessageId, messages) => {
		// Backend handles outlet filters and persistence inline.
		// Just refresh the sidebar chat list.
		if ($chatId == _chatId && !$temporaryChatEnabled) {
			currentChatPage.set(1);
			await chats.set(await getChatList(localStorage.token, $currentChatPage));
		}
		taskIds = null;
	};

	const chatActionHandler = async (_chatId, actionId, modelId, responseMessageId, event = null) => {
		const messages = createMessagesList(history, responseMessageId);

		const res = await chatAction(localStorage.token, actionId, {
			model: modelId,
			messages: messages.map((m) => ({
				id: m.id,
				role: m.role,
				content: m.content,
				info: m.info ? m.info : undefined,
				timestamp: m.timestamp,
				...(m.sources ? { sources: m.sources } : {})
			})),
			...(event ? { event: event } : {}),
			model_item: $models.find((m) => m.id === modelId),
			chat_id: _chatId,
			session_id: $socket?.id,
			id: responseMessageId
		}).catch((error) => {
			toast.error(`${error}`);
			messages.at(-1).error = { content: error };
			return null;
		});

		if (res !== null && res.messages) {
			// Update chat history with the new messages
			for (const message of res.messages) {
				history.messages[message.id] = {
					...history.messages[message.id],
					...(history.messages[message.id].content !== message.content
						? { originalContent: history.messages[message.id].content }
						: {}),
					...message
				};
			}
		}

		if ($chatId == _chatId) {
			if (!$temporaryChatEnabled) {
				chat = await updateChatById(localStorage.token, _chatId, {
					models: selectedModels,
					messages: messages,
					history: history,
					files: chatFiles,
					meta: buildChatMeta()
				});

				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, $currentChatPage));
			}
		}
	};

	const getChatEventEmitter = async (modelId: string, chatId: string = '') => {
		return setInterval(() => {
			$socket?.emit('usage', {
				action: 'chat',
				model: modelId,
				chat_id: chatId
			});
		}, 1000);
	};

	const createMessagePair = async (userPrompt) => {
		messageInput?.setText('');
		if (selectedModels.length === 0) {
			toast.error($i18n.t('Model not selected'));
		} else {
			const modelId = selectedModels[0];
			const model = $models.filter((m) => m.id === modelId).at(0);

			if (!model) {
				toast.error($i18n.t('Model not found'));
				return;
			}

			const messages = createMessagesList(history, history.currentId);
			const parentMessage = messages.length !== 0 ? messages.at(-1) : null;

			const userMessageId = uuidv4();
			const responseMessageId = uuidv4();

			const userMessage = {
				id: userMessageId,
				parentId: parentMessage ? parentMessage.id : null,
				childrenIds: [responseMessageId],
				role: 'user',
				content: userPrompt ? userPrompt : `[PROMPT] ${userMessageId}`,
				timestamp: Math.floor(Date.now() / 1000)
			};

			const responseMessage = {
				id: responseMessageId,
				parentId: userMessageId,
				childrenIds: [],
				role: 'assistant',
				content: `[RESPONSE] ${responseMessageId}`,
				done: true,

				model: modelId,
				modelName: model.name ?? model.id,
				modelIdx: 0,
				timestamp: Math.floor(Date.now() / 1000)
			};

			if (parentMessage) {
				parentMessage.childrenIds.push(userMessageId);
				history.messages[parentMessage.id] = parentMessage;
			}
			history.messages[userMessageId] = userMessage;
			history.messages[responseMessageId] = responseMessage;

			history.currentId = responseMessageId;

			await tick();

			if (autoScroll) {
				scrollToBottom();
			}

			if (messages.length === 0) {
				await initChatHandler(history);
			} else {
				await saveChatHandler($chatId, history);
			}
		}
	};

	const addMessages = async ({ modelId, parentId, messages }) => {
		const model = $models.filter((m) => m.id === modelId).at(0);

		let parentMessage = history.messages[parentId];
		let currentParentId = parentMessage ? parentMessage.id : null;
		for (const message of messages) {
			let messageId = uuidv4();

			if (message.role === 'user') {
				const userMessage = {
					id: messageId,
					parentId: currentParentId,
					childrenIds: [],
					timestamp: Math.floor(Date.now() / 1000),
					...message
				};

				if (parentMessage) {
					parentMessage.childrenIds.push(messageId);
					history.messages[parentMessage.id] = parentMessage;
				}

				history.messages[messageId] = userMessage;
				parentMessage = userMessage;
				currentParentId = messageId;
			} else {
				const responseMessage = {
					id: messageId,
					parentId: currentParentId,
					childrenIds: [],
					done: true,
					model: model.id,
					modelName: model.name ?? model.id,
					modelIdx: 0,
					timestamp: Math.floor(Date.now() / 1000),
					...message
				};

				if (parentMessage) {
					parentMessage.childrenIds.push(messageId);
					history.messages[parentMessage.id] = parentMessage;
				}

				history.messages[messageId] = responseMessage;
				parentMessage = responseMessage;
				currentParentId = messageId;
			}
		}

		history.currentId = currentParentId;
		await tick();

		if (autoScroll) {
			scrollToBottom();
		}

		if (messages.length === 0) {
			await initChatHandler(history);
		} else {
			await saveChatHandler($chatId, history);
		}
	};

	const chatCompletionEventHandler = async (data, message, chatId) => {
		const { id, done, choices, content, output, sources, selected_model_id, error, usage } = data;
		const finishReason = choices?.[0]?.finish_reason ?? choices?.[0]?.finishReason ?? null;
		const isCompletionFinished =
			done ||
			(finishReason &&
				!['tool_calls', 'function_call', 'tool_call'].includes(String(finishReason)));

		// Store raw OR-aligned output items from backend
		if (output) {
			message.output = output;
		}

		if (error) {
			await handleOpenAIError(error, message);
		}

		if (sources && !message?.sources) {
			message.sources = sources;
		}

		if (choices) {
			if (choices[0]?.message?.content) {
				// Non-stream response
				message.content += choices[0]?.message?.content;
			} else {
				// Stream response
				let value = choices[0]?.delta?.content ?? '';
				if (message.content == '' && value == '\n') {
					console.log('Empty response');
				} else {
					message.content += value;

					if (navigator.vibrate && ($settings?.hapticFeedback ?? false)) {
						navigator.vibrate(5);
					}

					// Emit chat event for TTS (only when call overlay is active)
					if ($showCallOverlay) {
						const messageContentParts = getMessageContentParts(
							removeAllDetails(message.content),
							$config?.audio?.tts?.split_on ?? 'punctuation'
						);
						messageContentParts.pop();

						// dispatch only last sentence and make sure it hasn't been dispatched before
						if (
							messageContentParts.length > 0 &&
							messageContentParts[messageContentParts.length - 1] !== message.lastSentence
						) {
							message.lastSentence = messageContentParts[messageContentParts.length - 1];
							eventTarget.dispatchEvent(
								new CustomEvent('chat', {
									detail: {
										id: message.id,
										content: messageContentParts[messageContentParts.length - 1]
									}
								})
							);
						}
					}
				}
			}
		}

		if (content) {
			// REALTIME_CHAT_SAVE is disabled
			message.content = content;

			if (navigator.vibrate && ($settings?.hapticFeedback ?? false)) {
				navigator.vibrate(5);
			}

			// Emit chat event for TTS (only when call overlay is active)
			if ($showCallOverlay) {
				const messageContentParts = getMessageContentParts(
					removeAllDetails(message.content),
					$config?.audio?.tts?.split_on ?? 'punctuation'
				);
				messageContentParts.pop();

				// dispatch only last sentence and make sure it hasn't been dispatched before
				if (
					messageContentParts.length > 0 &&
					messageContentParts[messageContentParts.length - 1] !== message.lastSentence
				) {
					message.lastSentence = messageContentParts[messageContentParts.length - 1];
					eventTarget.dispatchEvent(
						new CustomEvent('chat', {
							detail: {
								id: message.id,
								content: messageContentParts[messageContentParts.length - 1]
							}
						})
					);
				}
			}
		}

		if (selected_model_id) {
			message.selectedModelId = selected_model_id;
			message.arena = true;
		}

		if (usage) {
			message.usage = usage;
		}

		history.messages[message.id] = message;

		if (isCompletionFinished && message.done !== true) {
			message.done = true;

			if ($settings.responseAutoCopy) {
				copyToClipboard(message.content);
			}

			if ($settings.responseAutoPlayback && !$showCallOverlay) {
				await tick();
				document.getElementById(`speak-button-${message.id}`)?.click();
			}

			// Emit chat event for TTS (only when call overlay is active)
			if ($showCallOverlay) {
				let lastMessageContentPart =
					getMessageContentParts(
						removeAllDetails(message.content),
						$config?.audio?.tts?.split_on ?? 'punctuation'
					)?.at(-1) ?? '';
				if (lastMessageContentPart) {
					eventTarget.dispatchEvent(
						new CustomEvent('chat', {
							detail: { id: message.id, content: lastMessageContentPart }
						})
					);
				}
			}
			eventTarget.dispatchEvent(
				new CustomEvent('chat:finish', {
					detail: {
						id: message.id,
						content: message.content
					}
				})
			);

			history.messages[message.id] = message;

			await tick();
			if (autoScroll) {
				scrollToBottom();
			}

			// Fire-and-forget: run chatCompletedHandler for background work
			// (outlet filters, chat save, title gen, follow-ups, tags)
			// without blocking the user from sending new messages.
			chatCompletedHandler(
				chatId,
				message.model,
				message.id,
				createMessagesList(history, message.id)
			);

			// Process next queued request if any
			await processNextInQueue(chatId);
		}

		console.log(data);
		await tick();

		if (autoScroll) {
			scheduleScrollToBottom();
		}
	};

	//////////////////////////
	// Chat functions
	//////////////////////////

	const submitPrompt = async (inputContent, inputFiles) => {
		const _files = structuredClone(inputFiles);

		chatFiles.push(
			..._files.filter(
				(item) =>
					['doc', 'text', 'note', 'chat', 'folder', 'collection'].includes(item.type) ||
					(item.type === 'file' && !(item?.content_type ?? '').startsWith('image/'))
			)
		);
		chatFiles = chatFiles.filter(
			// Remove duplicates
			(item, index, array) => array.findIndex((i) => equal(i, item)) === index
		);

		// Create user message
		let userMessageId = uuidv4();
		let userMessage = {
			id: userMessageId,
			parentId: history.currentId ?? null,
			childrenIds: [],
			role: 'user',
			content: inputContent,
			files: _files.length > 0 ? _files : undefined,
			timestamp: Math.floor(Date.now() / 1000), // Unix epoch
			models: selectedModels
		};

		// Add message to history and Set currentId to messageId
		history.messages[userMessageId] = userMessage;

		// Append messageId to childrenIds of parent message
		if (history.currentId !== null) {
			history.messages[history.currentId].childrenIds.push(userMessageId);
		}

		history.currentId = userMessageId;

		focusChatInput();

		saveSessionSelectedModels();

		await sendMessage(history, userMessageId);
	};

	const submitHandler = async (userPrompt, { _raw = false } = {}) => {
		console.log('submitHandler', userPrompt, $chatId);

		const _selectedModels = selectedModels.map((modelId) =>
			$models.map((m) => m.id).includes(modelId) ? modelId : ''
		);

		if (!equal(selectedModels, _selectedModels)) {
			selectedModels = _selectedModels;
		}

		if (pendingOAuthTools.length > 0) {
			toast.warning($i18n.t('Please connect all required integrations before sending a message'));
			return;
		}
		if (userPrompt === '' && files.length === 0) {
			toast.error($i18n.t('Please enter a prompt'));
			return;
		}
		if (selectedModels.includes('')) {
			toast.error($i18n.t('Model not selected'));
			return;
		}

		if (
			files.length > 0 &&
			files.filter((file) => file.type !== 'image' && file.status === 'uploading').length > 0
		) {
			toast.error(
				$i18n.t(`Oops! There are files still uploading. Please wait for the upload to complete.`)
			);
			return;
		}

		if (
			($config?.file?.max_count ?? null) !== null &&
			files.length + chatFiles.length > $config?.file?.max_count
		) {
			toast.error(
				$i18n.t(`You can only chat with a maximum of {{maxCount}} file(s) at a time.`, {
					maxCount: $config?.file?.max_count
				})
			);
			return;
		}

		// Check if the assistant is still generating the main response
		// (don't block on background tasks like title gen, follow-ups, tags)
		const lastMessage = history.currentId ? history.messages[history.currentId] : null;
		const isGenerating = lastMessage && lastMessage.role === 'assistant' && !lastMessage.done;

		if (isGenerating) {
			if ($settings?.enableMessageQueue ?? true) {
				// Enqueue the request
				const _files = structuredClone(files);
				chatRequestQueues.update((q) => ({
					...q,
					[$chatId]: [...(q[$chatId] ?? []), { id: uuidv4(), prompt: userPrompt, files: _files }]
				}));
				// Clear input
				messageInput?.setText('');
				prompt = '';
				files = [];
				return;
			} else {
				// Interrupt: stop current generation and proceed
				await stopResponse();
				await tick();
			}
		}

		if (history?.currentId) {
			const currentMessage = history.messages[history.currentId];

			if (currentMessage.error && !currentMessage.content) {
				// Error in response
				toast.error($i18n.t(`Oops! There was an error in the previous response.`));
				return;
			}
		}

		// Clear input and submit
		messageInput?.setText('');
		prompt = '';
		const _files = structuredClone(files);
		files = [];
		messageInput?.setText('');

		await submitPrompt(userPrompt, _files);
	};

	const sendMessage = async (
		_history,
		parentId: string,
		{
			messages = null,
			modelId = null,
			modelIdx = null
		}: {
			messages?: any[] | null;
			modelId?: string | null;
			modelIdx?: number | null;
		} = {}
	) => {
		if (autoScroll) {
			scrollToBottom();
		}

		let _chatId = JSON.parse(JSON.stringify($chatId));
		_history = structuredClone(_history);

		const responseMessageIds: Record<PropertyKey, string> = {};
		// If modelId is provided, use it, else use selected model
		let selectedModelIds = modelId
			? [modelId]
			: atSelectedModel !== undefined
				? [atSelectedModel.id]
				: selectedModels;

		// Create response messages for each selected model
		// Build message_ids map: {model_id: assistant_message_id}
		const messageIdsMap: Record<string, string> = {};
		for (const [_modelIdx, modelId] of selectedModelIds.entries()) {
			const model = $models.filter((m) => m.id === modelId).at(0);

			if (model) {
				let responseMessageId = uuidv4();
				let responseMessage = {
					parentId: parentId,
					id: responseMessageId,
					childrenIds: [],
					role: 'assistant',
					content: '',
					done: false,
					model: model.id,
					modelName: model.name ?? model.id,
					modelIdx: modelIdx ? modelIdx : _modelIdx,
					timestamp: Math.floor(Date.now() / 1000) // Unix epoch
				};

				// Add message to history and Set currentId to messageId
				history.messages[responseMessageId] = responseMessage;
				history.currentId = responseMessageId;

				// Append messageId to childrenIds of parent message
				if (parentId !== null && history.messages[parentId]) {
					history.messages[parentId].childrenIds = [
						...history.messages[parentId].childrenIds,
						responseMessageId
					];
				}

				responseMessageIds[`${modelId}-${modelIdx ? modelIdx : _modelIdx}`] = responseMessageId;
				messageIdsMap[modelId] = responseMessageId;
			}
		}
		history = history;

		// New chat — backend generates the chat_id on first request
		if (!_chatId) {
			currentChatFolderId = getNewChatFolderId();
			await tick();
		}

		await tick();

		// Re-clone history so sendMessageSocket gets the response messages we just added
		_history = structuredClone(history);

		// Vision capability check
		for (const mid of selectedModelIds) {
			const model = $models.filter((m) => m.id === mid).at(0);
			if (model) {
				const hasImages = createMessagesList(_history, parentId).some((message) =>
					message.files?.some(
						(file) => file.type === 'image' || (file?.content_type ?? '').startsWith('image/')
					)
				);

				if (
					hasImages &&
					!(model.info?.meta?.capabilities?.vision ?? true) &&
					!imageGenerationEnabled
				) {
					toast.error(
						$i18n.t('Model {{modelName}} is not vision capable', {
							modelName: model.name ?? model.id
						})
					);
				}
			}
		}

		// Single request — backend fans out to all models
		const primaryModelId = selectedModelIds[0];
		const primaryModel = $models.filter((m) => m.id === primaryModelId).at(0);
		const primaryResponseMessageId = messageIdsMap[primaryModelId];

		if (primaryModel && primaryResponseMessageId) {
			const chatEventEmitter = await getChatEventEmitter(primaryModel.id, _chatId);

			scrollToBottom();
			await sendMessageSocket(
				primaryModel,
				messages && messages.length > 0
					? messages
					: createMessagesList(_history, primaryResponseMessageId),
				_history,
				primaryResponseMessageId,
				_chatId,
				selectedModelIds.length > 1 ? messageIdsMap : undefined
			);

			if (chatEventEmitter) clearInterval(chatEventEmitter);
		}
	};

	const getFeatures = () => {
		let features = {};

		if ($config?.features)
			features = {
				voice: $showCallOverlay,
				image_generation:
					$config?.features?.enable_image_generation &&
					($user?.role === 'admin' || $user?.permissions?.features?.image_generation)
						? imageGenerationEnabled
						: false,
				code_interpreter:
					$config?.features?.enable_code_interpreter &&
					($user?.role === 'admin' || $user?.permissions?.features?.code_interpreter)
						? codeInterpreterEnabled
						: false,
				web_search:
					$config?.features?.enable_web_search &&
					($user?.role === 'admin' || $user?.permissions?.features?.web_search)
						? webSearchEnabled
						: false
			};

		const currentModels = atSelectedModel?.id ? [atSelectedModel.id] : selectedModels;
		if (
			currentModels.filter(
				(model) => $models.find((m) => m.id === model)?.info?.meta?.capabilities?.web_search ?? true
			).length === currentModels.length
		) {
			if ($config?.features?.enable_web_search && ($settings?.webSearch ?? false) === 'always') {
				features = { ...features, web_search: true };
			}
		}

		if ($settings?.memory ?? false) {
			features = { ...features, memory: true };
		}

		return features;
	};

	const sendMessageSocket = async (
		model,
		_messages,
		_history,
		responseMessageId,
		_chatId,
		messageIdsMap?: Record<string, string>
	) => {
		const responseMessage = _history.messages[responseMessageId];
		const userMessage = _history.messages[responseMessage.parentId];

		const chatMessageFiles = _messages
			.filter((message) => message.files)
			.flatMap((message) => message.files);

		// Filter chatFiles to only include files that are in the chatMessageFiles
		chatFiles = chatFiles.filter((item) => {
			const fileExists = chatMessageFiles.some((messageFile) => messageFile.id === item.id);
			return fileExists;
		});

		let files = (userMessage?.files ?? []).filter(
			(item) =>
				['doc', 'text', 'note', 'chat', 'collection'].includes(item.type) ||
				(item.type === 'file' && !(item?.content_type ?? '').startsWith('image/'))
		);
		// Remove duplicates
		files = files.filter((item, index, array) => array.findIndex((i) => equal(i, item)) === index);

		scrollToBottom();
		eventTarget.dispatchEvent(
			new CustomEvent('chat:start', {
				detail: {
					id: responseMessageId
				}
			})
		);
		await tick();

		let userLocation;
		if ($settings?.userLocation) {
			userLocation = await getAndUpdateUserLocation(localStorage.token).catch((err) => {
				console.error(err);
				return undefined;
			});
		}

		const stream = model?.info?.params?.stream_response ?? true;
		let messages = [
			{
				role: 'user',
				content: processDetails(userMessage?.merged?.content ?? userMessage?.content ?? ''),
				...(userMessage?.files ? { files: userMessage.files } : {})
			}
		];

		const toolIds = [];
		const toolServerIds = [];

		for (const toolId of selectedToolIds) {
			if (toolId.startsWith('direct_server:')) {
				let serverId = toolId.replace('direct_server:', '');
				// Check if serverId is a number
				if (!isNaN(parseInt(serverId))) {
					toolServerIds.push(parseInt(serverId));
				} else {
					toolServerIds.push(serverId);
				}
			} else {
				toolIds.push(toolId);
			}
		}

		// Parse skill mentions (<$skillId|label>) from user messages
		const skillMentionRegex = /<\$([^|>]+)\|?[^>]*>/g;
		const skillIds = [];
		for (const message of messages) {
			const content =
				typeof message.content === 'string' ? message.content : (message.content?.[0]?.text ?? '');
			for (const match of content.matchAll(skillMentionRegex)) {
				if (!skillIds.includes(match[1])) {
					skillIds.push(match[1]);
				}
			}
		}

		// Strip skill mentions from message content
		if (skillIds.length > 0) {
			messages = messages.map((message) => {
				if (typeof message.content === 'string') {
					return {
						...message,
						content: message.content.replace(/<\$[^>]+>/g, '').trim()
					};
				} else if (Array.isArray(message.content)) {
					return {
						...message,
						content: message.content.map((part) =>
							part.type === 'text'
								? { ...part, text: part.text.replace(/<\$[^>]+>/g, '').trim() }
								: part
						)
					};
				}
				return message;
			});
		}

		// Use the user-selected terminal from the dropdown
		const activeTerminalId = $selectedTerminalId ?? null;

		// Only send terminal_id if the model has terminal capability enabled
		const terminalEnabled = model.info?.meta?.capabilities?.terminal ?? true;

		const res = await generateOpenAIChatCompletion(
			localStorage.token,
			{
				stream: stream,
				model: model.id,
				...(messages.length > 0 ? { messages } : {}),

				files: (files?.length ?? 0) > 0 ? files : undefined,

				filter_ids: selectedFilterIds.length > 0 ? selectedFilterIds : undefined,
				tool_ids: toolIds.length > 0 ? toolIds : undefined,
				skill_ids: skillIds.length > 0 ? skillIds : undefined,
				terminal_id: terminalEnabled ? (activeTerminalId ?? undefined) : undefined,
				tool_servers: [
					...($toolServers ?? []).filter(
						(server, idx) => toolServerIds.includes(idx) || toolServerIds.includes(server?.id)
					),
					// Direct terminal servers — always included when enabled (not routed through selectedToolIds)
					...($terminalServers ?? []).filter((t) => !t.id)
				],
				features: getFeatures(),
				variables: {
					...getPromptVariables(
						$user?.name,
						$settings?.userLocation ? userLocation : undefined,
						$user?.email
					)
				},
				model_item: $models.find((m) => m.id === model.id),

				session_id: $socket?.id,
				chat_id: _chatId || undefined,
				folder_id: getNewChatFolderId() ?? undefined,

				id: responseMessageId,
				...(messageIdsMap ? { message_ids: messageIdsMap } : {}),
				parent_id: userMessage?.parentId ?? null,
				user_message: userMessage,

				background_tasks: {
					...((userMessage?.parentId ?? null) === null
						? {
								title_generation: $settings?.title?.auto ?? true,
								tags_generation: $settings?.autoTags ?? true
							}
						: {}),
					follow_up_generation: $settings?.autoFollowUps ?? true
				},

				...(stream && (model.info?.meta?.capabilities?.usage ?? false)
					? {
							stream_options: {
								include_usage: true
							}
						}
					: {})
			},
			`${WEBUI_BASE_URL}/api`
		).catch(async (error) => {
			console.log(error);

			let errorMessage = error;
			if (error?.error?.message) {
				errorMessage = error.error.message;
			} else if (error?.message) {
				errorMessage = error.message;
			}

			if (typeof errorMessage === 'object') {
				errorMessage = $i18n.t(`Uh-oh! There was an issue with the response.`);
			}

			toast.error(`${errorMessage}`);
			responseMessage.error = {
				content: error
			};

			responseMessage.done = true;

			history.messages[responseMessageId] = responseMessage;
			history.currentId = responseMessageId;

			return null;
		});

		if (res) {
			if (res.error) {
				await handleOpenAIError(res.error, responseMessage);
			} else {
				// Backend returns task_ids (multi-model) or task_id (single model)
				const newTaskIds = res.task_ids ?? (res.task_id ? [res.task_id] : []);
				if (taskIds) {
					taskIds.push(...newTaskIds);
				} else {
					taskIds = newTaskIds;
				}

				if (!$temporaryChatEnabled) {
					void watchGeneratedChatTitle(res.chat_id ?? _chatId ?? $chatId, currentChatFolderId);
				}

				// Backend returns chat_id for new chats — set store + URL.
				// Only update if the user hasn't navigated to a different chat
				// while the request was in flight (prevents overwriting $chatId
				// and causing spurious toast notifications / state duplication).
				const responseBelongsToCurrentChat =
					$chatId === _chatId || (!$chatId && !_chatId) || $chatId === res.chat_id;

				if (res.chat_id && responseBelongsToCurrentChat) {
					if ($chatId !== res.chat_id) {
						await chatId.set(res.chat_id);
					}
					if (!$temporaryChatEnabled) {
						if (window.location.pathname !== `/c/${res.chat_id}`) {
							window.history.replaceState(history.state, '', `/c/${res.chat_id}`);
						}
						currentChatPage.set(1);
						await chats.set(await getChatList(localStorage.token, $currentChatPage));
						refreshFolderChatList();
						newChatFolder.set(undefined);
						selectedFolder.set(null);
					}
				}
			}
		}

		await tick();
		scrollToBottom();
	};

	const handleOpenAIError = async (error, responseMessage) => {
		let errorMessage = '';
		let innerError;

		if (error) {
			innerError = error;
		}

		console.error(innerError);
		if ('detail' in innerError) {
			// FastAPI error
			toast.error(innerError.detail);
			errorMessage = innerError.detail;
		} else if ('error' in innerError) {
			// OpenAI error
			if ('message' in innerError.error) {
				toast.error(innerError.error.message);
				errorMessage = innerError.error.message;
			} else {
				toast.error(innerError.error);
				errorMessage = innerError.error;
			}
		} else if ('message' in innerError) {
			// OpenAI error
			toast.error(innerError.message);
			errorMessage = innerError.message;
		}

		responseMessage.error = {
			content: $i18n.t(`Uh-oh! There was an issue with the response.`) + '\n' + errorMessage
		};
		responseMessage.done = true;

		if (responseMessage.statusHistory) {
			responseMessage.statusHistory = responseMessage.statusHistory.filter(
				(status) => status.action !== 'knowledge_search'
			);
		}

		history.messages[responseMessage.id] = responseMessage;
	};

	const stopResponse = async (processQueue = true) => {
		if (taskIds) {
			if ($chatId) {
				await stopTasksByChatId(localStorage.token, $chatId).catch((error) => {
					toast.error(`${error}`);
					return null;
				});
			} else {
				for (const taskId of taskIds) {
					const res = await stopTask(localStorage.token, taskId).catch((error) => {
						toast.error(`${error}`);
						return null;
					});
				}
			}

			taskIds = null;

			const responseMessage = history.messages[history.currentId];
			// Set all response messages to done
			if (responseMessage.parentId && history.messages[responseMessage.parentId]) {
				for (const messageId of history.messages[responseMessage.parentId].childrenIds) {
					history.messages[messageId].done = true;
				}
			}

			history.messages[history.currentId] = responseMessage;

			if (autoScroll) {
				scrollToBottom();
			}
		}

		if (generating) {
			generating = false;
			generationController?.abort();
			generationController = null;
		}

		if (processQueue) {
			await processNextInQueue($chatId);
		}
	};

	const submitMessage = async (parentId, prompt) => {
		let userPrompt = prompt;
		let userMessageId = uuidv4();

		let userMessage = {
			id: userMessageId,
			parentId: parentId,
			childrenIds: [],
			role: 'user',
			content: userPrompt,
			models: selectedModels,
			timestamp: Math.floor(Date.now() / 1000) // Unix epoch
		};

		if (parentId !== null) {
			history.messages[parentId].childrenIds = [
				...history.messages[parentId].childrenIds,
				userMessageId
			];
		}

		history.messages[userMessageId] = userMessage;
		history.currentId = userMessageId;

		await tick();

		if (autoScroll) {
			scrollToBottom();
		}

		await sendMessage(history, userMessageId);
	};

	const regenerateResponse = async (message, suggestionPrompt = null) => {
		console.log('regenerateResponse');

		if (history.currentId) {
			let userMessage = history.messages[message.parentId];

			if (!userMessage) {
				toast.error($i18n.t('Parent message not found'));
				return;
			}

			if (autoScroll) {
				scrollToBottom();
			}

			await sendMessage(history, userMessage.id, {
				...(suggestionPrompt
					? {
							messages: [
								...createMessagesList(history, message.id),
								{
									role: 'user',
									content: suggestionPrompt
								}
							]
						}
					: {}),
				...((userMessage?.models ?? [...selectedModels]).length > 1
					? {
							// If multiple models are selected, use the model from the message
							modelId: message.model,
							modelIdx: message.modelIdx
						}
					: {})
			});
		}
	};

	const continueResponse = async () => {
		console.log('continueResponse');
		const _chatId = JSON.parse(JSON.stringify($chatId));

		if (history.currentId && history.messages[history.currentId].done == true) {
			const responseMessage = history.messages[history.currentId];
			responseMessage.done = false;
			await tick();

			const model = $models
				.filter((m) => m.id === (responseMessage?.selectedModelId ?? responseMessage.model))
				.at(0);

			if (model) {
				await sendMessageSocket(
					model,
					createMessagesList(history, responseMessage.id),
					history,
					responseMessage.id,
					_chatId
				);
			}
		}
	};

	const mergeResponses = async (messageId, responses, _chatId) => {
		console.log('mergeResponses', messageId, responses);
		const message = history.messages[messageId];
		const mergedResponse = {
			status: true,
			content: ''
		};
		message.merged = mergedResponse;
		history.messages[messageId] = message;

		try {
			generating = true;
			const [res, controller] = await generateMoACompletion(
				localStorage.token,
				message.model ?? '',
				message.parentId ? history.messages[message.parentId].content : '',
				responses
			);

			if (res && res.ok && res.body && generating) {
				generationController = controller as AbortController;
				const textStream = await createOpenAITextStream(
					res.body,
					Boolean($settings?.splitLargeChunks ?? false)
				);
				for await (const update of textStream) {
					const { value, done, sources, error, usage } = update;
					if (error || done) {
						generating = false;
						generationController = null;
						break;
					}

					if (mergedResponse.content == '' && value == '\n') {
						continue;
					} else {
						mergedResponse.content += value;
						history.messages[messageId] = message;
					}

					if (autoScroll) {
						scheduleScrollToBottom();
					}
				}

				await saveChatHandler(_chatId, history);
			} else {
				console.error(res);
			}
		} catch (e) {
			console.error(e);
		}
	};

	const getInitialChatTitle = (messages, maxLength = 100) => {
		const userMessage = messages.find((message) => message.role === 'user');
		let content = userMessage?.content ?? '';

		if (Array.isArray(content)) {
			content = content
				.filter((part) => part?.type === 'text')
				.map((part) => part.text ?? '')
				.join(' ');
		}

		const title = String(content ?? '')
			.replace(/\s+/g, ' ')
			.trim();
		return title.length > maxLength ? `${title.slice(0, maxLength).trimEnd()}...` : title;
	};

	const initChatHandler = async (history) => {
		let _chatId = $chatId;
		const folderId = getNewChatFolderId();
		currentChatFolderId = folderId;
		const initialTitle =
			getInitialChatTitle(createMessagesList(history, history.currentId)) || $i18n.t('New Chat');

		await chatTitle.set(initialTitle);

		if (!$temporaryChatEnabled) {
			chat = await createNewChat(
				localStorage.token,
				{
					id: _chatId,
					title: initialTitle,
					models: selectedModels,
					history: history,
					messages: createMessagesList(history, history.currentId),
					meta: buildChatMeta(),
					tags: [],
					timestamp: Date.now()
				},
				folderId
			);

			_chatId = chat.id;
			await chatId.set(_chatId);

			window.history.replaceState(history.state, '', `/c/${_chatId}`);

			await tick();

			await chats.set(await getChatList(localStorage.token, $currentChatPage));
			currentChatPage.set(1);

			if (folderId) {
				refreshFolderChatList(folderId);
			}

			newChatFolder.set(undefined);
			selectedFolder.set(null);
		} else {
			_chatId = `local:${$socket?.id}`; // Use socket id for temporary chat
			await chatId.set(_chatId);
		}
		await tick();

		return _chatId;
	};

	const saveChatHandler = async (_chatId, history) => {
		if ($chatId == _chatId) {
			if (!$temporaryChatEnabled) {
				chat = await updateChatById(localStorage.token, _chatId, {
					models: selectedModels,
					history: history,
					messages: createMessagesList(history, history.currentId),
					files: chatFiles,
					meta: buildChatMeta()
				});
			}
		}
	};

	const MAX_DRAFT_LENGTH = 5000;
	let saveDraftTimeout: ReturnType<typeof setTimeout> | null = null;

	const saveDraft = async (draft: any, chatId: string | null = null) => {
		if (saveDraftTimeout) {
			clearTimeout(saveDraftTimeout);
		}

		if (draft.prompt !== null && draft.prompt.length < MAX_DRAFT_LENGTH) {
			saveDraftTimeout = setTimeout(async () => {
				await sessionStorage.setItem(
					`chat-input${chatId ? `-${chatId}` : ''}`,
					JSON.stringify(draft)
				);
			}, 500);
		} else {
			sessionStorage.removeItem(`chat-input${chatId ? `-${chatId}` : ''}`);
		}
	};

	const clearDraft = async (chatId: string | null = null) => {
		if (saveDraftTimeout) {
			clearTimeout(saveDraftTimeout);
		}
		await sessionStorage.removeItem(`chat-input${chatId ? `-${chatId}` : ''}`);
	};

	const moveChatHandler = async (chatId, folderId) => {
		if (chatId && folderId) {
			const res = await updateChatFolderIdById(localStorage.token, chatId, folderId).catch(
				(error) => {
					toast.error(`${error}`);
					return null;
				}
			);

			if (res) {
				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, $currentChatPage));
				await pinnedChats.set(await getPinnedChatList(localStorage.token));

				toast.success($i18n.t('Chat moved successfully'));
			}
		} else {
			toast.error($i18n.t('Failed to move chat'));
		}
	};

	const archiveChatHandler = async (id: string) => {
		try {
			await archiveChatById(localStorage.token, id);
			currentChatPage.set(1);
			initNewChat();
			await goto('/');
			chats.set(await getChatList(localStorage.token, $currentChatPage));
			pinnedChats.set(await getPinnedChatList(localStorage.token));
			toast.success($i18n.t('Chat archived.'));
		} catch (error) {
			console.error('Error archiving chat:', error);
			toast.error($i18n.t('Failed to archive chat.'));
		}
	};
</script>

<svelte:head>
	<title>
		{$settings.showChatTitleInTab !== false && $chatTitle
			? `${$chatTitle.length > 30 ? `${$chatTitle.slice(0, 30)}...` : $chatTitle} • ${$WEBUI_NAME}`
			: `${$WEBUI_NAME}`}
	</title>
</svelte:head>

<audio id="audioElement" src="" style="display: none;"></audio>

<EventConfirmDialog
	bind:show={showEventConfirmation}
	title={eventConfirmationTitle}
	message={eventConfirmationMessage}
	input={eventConfirmationInput}
	inputPlaceholder={eventConfirmationInputPlaceholder}
	inputValue={eventConfirmationInputValue}
	inputType={eventConfirmationInputType}
	on:confirm={(e) => {
		if (e.detail) {
			eventCallback(e.detail);
		} else {
			eventCallback(true);
		}
	}}
	on:cancel={() => {
		eventCallback(false);
	}}
/>

<div
	class="h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''} w-full max-w-full flex flex-col ml-5"
	class:chat-side-panel-open={$showArtifacts || $showExpertAgentDrawer}
	id="chat-container"
>
	{#if !loading}
		<div in:fade={{ duration: 50 }} class="w-full h-full flex flex-col">
			{#if $selectedFolder && $selectedFolder?.meta?.background_image_url}
				<div
					class="absolute top-0 left-0 w-full h-full bg-cover bg-center bg-no-repeat"
					style="background-image: url({$selectedFolder?.meta?.background_image_url})  "
				></div>

				<div
					class="absolute top-0 left-0 w-full h-full bg-linear-to-t from-white to-white/85 dark:from-gray-900 dark:to-gray-900/90 z-0"
				></div>
			{:else if $settings?.backgroundImageUrl ?? $config?.license_metadata?.background_image_url ?? null}
				<div
					class="absolute top-0 left-0 w-full h-full bg-cover bg-center bg-no-repeat"
					style="background-image: url({$settings?.backgroundImageUrl ??
						$config?.license_metadata?.background_image_url})  "
				></div>

				<div
					class="absolute top-0 left-0 w-full h-full bg-linear-to-t from-white to-white/85 dark:from-gray-900 dark:to-gray-900/90 z-0"
				></div>
			{/if}

			<PaneGroup direction="horizontal" class="w-full h-full">
				<Pane defaultSize={50} minSize={30} class="h-full flex relative max-w-full flex-col">
					<FilesOverlay show={dragged} />
					<Navbar
						bind:this={navbarElement}
						chat={{
							id: $chatId,
							chat: {
								title: $chatTitle,
								models: selectedModels,
								history: history,
								timestamp: Date.now()
							}
						}}
						{history}
						title={$chatTitle}
						bind:selectedModels
						shareEnabled={!!history.currentId}
						{initNewChat}
						{archiveChatHandler}
						{moveChatHandler}
						onSaveTempChat={async () => {
							try {
								if (!history?.currentId || !Object.keys(history.messages).length) {
									toast.error($i18n.t('No conversation to save'));
									return;
								}
								const messages = createMessagesList(history, history.currentId);
								const title =
									messages.find((m) => m.role === 'user')?.content ?? $i18n.t('New Chat');

								const savedChat = await createNewChat(
									localStorage.token,
									{
										id: uuidv4(),
										title: title.length > 50 ? `${title.slice(0, 50)}...` : title,
										models: selectedModels,
										history: history,
										messages: messages,
										meta: buildChatMeta(),
										timestamp: Date.now()
									},
									null
								);

								if (savedChat) {
									temporaryChatEnabled.set(false);
									chatId.set(savedChat.id);
									chats.set(await getChatList(localStorage.token, $currentChatPage));

									await goto(`/c/${savedChat.id}`);
									toast.success($i18n.t('Conversation saved successfully'));
								}
							} catch (error) {
								console.error('Error saving conversation:', error);
								toast.error($i18n.t('Failed to save conversation'));
							}
						}}
					/>

					<div
						id="chat-pane"
						class="relative flex flex-col flex-auto z-10 w-full @container overflow-auto"
					>
						{#if activeExpertSkillName}
							<div
								class="pointer-events-none absolute inset-x-0 top-3 z-30 flex justify-center px-4"
							>
								<div
									class="inline-flex max-w-full items-center gap-1.5 rounded-[20px] bg-[#69a259] px-3.5 py-1.5 text-sm font-semibold text-white shadow-[0_8px_24px_rgba(31,41,55,0.22)]"
								>
									<span aria-hidden="true">🧩</span>
									<span class="truncate">专家模式：{activeExpertSkillName}</span>
								</div>
							</div>
						{/if}

						{#if ($settings?.landingPageMode === 'chat' && !$selectedFolder) || createMessagesList(history, history.currentId).length > 0}
							<div
								class=" pb-2.5 flex flex-col justify-between w-full flex-auto overflow-auto h-0 max-w-full z-10 scrollbar-hidden"
								id="messages-container"
								bind:this={messagesContainerElement}
								on:scroll={(e) => {
									autoScroll =
										messagesContainerElement.scrollHeight - messagesContainerElement.scrollTop <=
										messagesContainerElement.clientHeight + 5;
								}}
							>
								<div class=" h-full w-full flex flex-col">
									<Messages
										chatId={$chatId}
										bind:history
										bind:autoScroll
										bind:prompt
										setInputText={(text) => {
											messageInput?.setText(text);
										}}
										{selectedModels}
										{atSelectedModel}
										{sendMessage}
										{showMessage}
										{submitMessage}
										{continueResponse}
										{regenerateResponse}
										{mergeResponses}
										{chatActionHandler}
										{addMessages}
										topPadding={true}
										bottomPadding={files.length > 0}
										{onSelect}
									/>
								</div>
							</div>

							<div class=" pb-2 {dragged ? 'z-0' : 'z-10'}">
								<MessageInput
									bind:this={messageInput}
									{history}
									{taskIds}
									{selectedModels}
									bind:files
									bind:prompt
									bind:autoScroll
									bind:selectedToolIds
									bind:selectedFilterIds
									bind:imageGenerationEnabled
									bind:codeInterpreterEnabled
									{pendingOAuthTools}
									bind:webSearchEnabled
									bind:atSelectedModel
									bind:showCommands
									bind:dragged
									toolServers={$toolServers}
									{generating}
									{stopResponse}
									{createMessagePair}
									{onUpload}
									{ensureChatId}
									messageQueue={$chatRequestQueues[$chatId] ?? []}
									{chatTasks}
									onQueueSendNow={async (id) => {
										const queue = $chatRequestQueues[$chatId] ?? [];
										const item = queue.find((m) => m.id === id);
										if (item) {
											// Remove from queue
											chatRequestQueues.update((q) => ({
												...q,
												[$chatId]: queue.filter((m) => m.id !== id)
											}));
											await stopResponse(false);
											await tick();
											await submitPrompt(item.prompt, item.files);
										}
									}}
									onQueueEdit={(id) => {
										const queue = $chatRequestQueues[$chatId] ?? [];
										const item = queue.find((m) => m.id === id);
										if (item) {
											// Remove from queue
											chatRequestQueues.update((q) => ({
												...q,
												[$chatId]: queue.filter((m) => m.id !== id)
											}));
											// Set files and restore prompt to input
											files = item.files;
											messageInput?.setText(item.prompt);
										}
									}}
									onQueueDelete={(id) => {
										const queue = $chatRequestQueues[$chatId] ?? [];
										chatRequestQueues.update((q) => ({
											...q,
											[$chatId]: queue.filter((m) => m.id !== id)
										}));
									}}
									onChange={(data) => {
										if (!$temporaryChatEnabled) {
											saveDraft(data, $chatId);
										}
									}}
									on:submit={async (e) => {
										clearDraft($chatId);
										if (e.detail || files.length > 0) {
											await tick();

											submitHandler(e.detail);
										}
									}}
								/>

								<div
									class="absolute bottom-1 text-xs text-gray-500 text-center line-clamp-1 right-0 left-0"
								>
									<!-- {$i18n.t('LLMs can make mistakes. Verify important information.')} -->
								</div>
							</div>
						{:else}
							<div class="flex items-center h-full">
								<Placeholder
									{history}
									{selectedModels}
									bind:messageInput
									bind:files
									bind:prompt
									bind:autoScroll
									bind:selectedToolIds
									bind:selectedFilterIds
									bind:imageGenerationEnabled
									bind:codeInterpreterEnabled
									bind:webSearchEnabled
									bind:atSelectedModel
									bind:showCommands
									bind:dragged
									{pendingOAuthTools}
									toolServers={$toolServers}
									{stopResponse}
									{createMessagePair}
									{onSelect}
									{onUpload}
									{ensureChatId}
									onChange={(data) => {
										if (!$temporaryChatEnabled) {
											saveDraft(data);
										}
									}}
									on:submit={async (e) => {
										clearDraft();
										if (e.detail || files.length > 0) {
											await tick();
											submitHandler(e.detail);
										}
									}}
								/>
							</div>
						{/if}
					</div>
				</Pane>
			</PaneGroup>
		</div>
	{:else if loading}
		<div class=" flex items-center justify-center h-full w-full">
			<div class="m-auto">
				<Spinner className="size-5" />
			</div>
		</div>
	{/if}
</div>

<ChatSidePanel {history} />

<style>
	:global(:root) {
		--chat-side-panel-width: clamp(640px, 58vw, 800px);
	}

	:global(#chat-container.chat-side-panel-open) {
		max-width: calc(100vw - var(--chat-side-panel-width) - 60px) !important;
		margin-right: calc(var(--chat-side-panel-width) + 20px) !important;
	}

	:global(.app:has(#sidebar[data-state='true']) #chat-container.chat-side-panel-open) {
		max-width: calc(100vw - var(--sidebar-width) - var(--chat-side-panel-width) - 80px) !important;
	}

	@media (max-width: 1023px) {
		:global(#chat-container.chat-side-panel-open),
		:global(.app:has(#sidebar[data-state='true']) #chat-container.chat-side-panel-open) {
			max-width: calc(100vw - 40px) !important;
			margin-right: 20px !important;
		}
	}

	::-webkit-scrollbar {
		height: 0.5rem;
		width: 0.5rem;
	}
</style>
