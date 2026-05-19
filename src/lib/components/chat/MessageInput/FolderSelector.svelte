<script lang="ts">
	import { getContext, onMount, tick } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { createNewFolder, getFolders, updateFolderIsExpandedById } from '$lib/apis/folders';
	import {
		config,
		folderRefreshSignal,
		folders,
		newChatFolder,
		selectedFolder,
		user
	} from '$lib/stores';

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import Folder from '$lib/components/icons/Folder.svelte';
	import PlusAlt from '$lib/components/icons/PlusAlt.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	const i18n = getContext('i18n');

	type FolderItem = {
		id: string;
		name?: string;
		parent_id?: string | null;
		updated_at?: number;
		[key: string]: any;
	};

	let show = false;
	let loading = false;
	let creating = false;
	let search = '';
	let newFolderName = '';

	$: enabled =
		($config?.features?.enable_folders ?? true) &&
		($user?.role === 'admin' || ($user?.permissions?.features?.folders ?? true));

	const sortFolders = (items: FolderItem[] = []) =>
		[...items].sort((a, b) =>
			(a?.name ?? '').localeCompare(b?.name ?? '', undefined, {
				sensitivity: 'base',
				numeric: true
			})
		);

	const getFolderPath = (folder: FolderItem, allFolders: FolderItem[]) => {
		const byId = Object.fromEntries(allFolders.map((item) => [item.id, item]));
		const names = [folder?.name ?? $i18n.t('Folder')];
		let parentId = folder?.parent_id;
		const visited = new Set([folder.id]);

		while (parentId && byId[parentId] && !visited.has(parentId)) {
			visited.add(parentId);
			names.unshift(byId[parentId]?.name ?? $i18n.t('Folder'));
			parentId = byId[parentId]?.parent_id;
		}

		return names.join(' / ');
	};

	$: folderOptions = sortFolders($folders ?? []).map((folder) => ({
		...folder,
		path: getFolderPath(folder, $folders ?? [])
	}));

	$: filteredFolders = folderOptions.filter((folder) =>
		(folder.path ?? '').toLowerCase().includes(search.trim().toLowerCase())
	);

	$: activeFolder = $newChatFolder === undefined ? $selectedFolder : $newChatFolder;

	const refreshFolders = async () => {
		if (!enabled) {
			return;
		}

		loading = true;
		const res = await getFolders(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			folders.set(res);
		}

		loading = false;
	};

	const selectFolder = async (folder: FolderItem | null) => {
		newChatFolder.set(folder);
		show = false;
		search = '';
		await tick();
		document.getElementById('chat-input')?.focus();
	};

	const createFolderHandler = async () => {
		const name = newFolderName.trim();

		if (!name) {
			toast.error($i18n.t('Folder name cannot be empty.'));
			return;
		}

		creating = true;
		const res = await createNewFolder(localStorage.token, {
			name,
			data: {},
			parent_id: null
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			await updateFolderIsExpandedById(localStorage.token, res.id, true).catch(() => null);
			newFolderName = '';
			await refreshFolders();
			await selectFolder(res);
			folderRefreshSignal.set({ id: Date.now(), folderId: res.id });
			toast.success($i18n.t('Folder created successfully'));
		}

		creating = false;
	};

	onMount(() => {
		if (enabled && ($folders ?? []).length === 0) {
			refreshFolders();
		}
	});
</script>

{#if enabled}
	<Dropdown
		bind:show
		side="top"
		align="start"
		sideOffset={8}
		contentClass="w-72 rounded-2xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-850 dark:text-white shadow-lg p-1 z-50"
		onOpenChange={(state) => {
			if (state && ($folders ?? []).length === 0) {
				refreshFolders();
			}
		}}
	>
		<Tooltip content={$i18n.t('Select Folder')} placement="top">
			<button
				type="button"
				class="group h-8 min-w-0 max-w-40 px-2 flex items-center gap-1.5 rounded-full text-gray-600 hover:text-gray-900 hover:bg-gray-100 dark:text-gray-300 dark:hover:text-white dark:hover:bg-gray-800 transition"
				aria-label={$i18n.t('Select Folder')}
			>
				<Folder className="size-4 shrink-0" strokeWidth="1.75" />
				<span class="truncate text-xs font-medium">
					{activeFolder?.name ?? $i18n.t('Folder')}
				</span>
			</button>
		</Tooltip>

		<div slot="content" class="flex flex-col">
			<div class="px-2 py-1.5">
				<div
					class="flex items-center gap-2 rounded-xl border border-gray-100 bg-gray-50 px-2 py-1.5 text-gray-500 dark:border-gray-800 dark:bg-gray-900/40"
				>
					<Search className="size-3.5 shrink-0" strokeWidth="1.75" />
					<input
						class="min-w-0 flex-1 bg-transparent text-sm text-gray-900 outline-hidden placeholder:text-gray-400 dark:text-white dark:placeholder:text-gray-500"
						placeholder={$i18n.t('Search folders')}
						bind:value={search}
						autocomplete="off"
					/>
					{#if search}
						<button
							type="button"
							class="rounded-full p-0.5 hover:bg-gray-200 dark:hover:bg-gray-800"
							aria-label={$i18n.t('Clear search')}
							on:click={() => {
								search = '';
							}}
						>
							<XMark className="size-3.5" strokeWidth="1.75" />
						</button>
					{/if}
				</div>
			</div>

			<div class="max-h-52 overflow-y-auto px-1 pb-1 scrollbar-thin">
				<button
					type="button"
					class="flex w-full items-center gap-2 rounded-xl px-3 py-1.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-800"
					on:click={() => selectFolder(null)}
				>
					<div class="size-4 shrink-0">
						{#if !activeFolder}
							<Check className="size-4" strokeWidth="1.75" />
						{/if}
					</div>
					<span class="truncate">{$i18n.t('No Folder')}</span>
				</button>

				{#if loading}
					<div class="px-3 py-2 text-sm text-gray-500">{$i18n.t('Loading...')}</div>
				{:else if filteredFolders.length === 0}
					<div class="px-3 py-2 text-sm text-gray-500">{$i18n.t('No folders found')}</div>
				{:else}
					{#each filteredFolders as folder (folder.id)}
						<button
							type="button"
							class="flex w-full items-center gap-2 rounded-xl px-3 py-1.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-800"
							on:click={() => selectFolder(folder)}
						>
							<div class="size-4 shrink-0">
								{#if activeFolder?.id === folder.id}
									<Check className="size-4" strokeWidth="1.75" />
								{:else}
									<Folder className="size-4 text-gray-400" strokeWidth="1.5" />
								{/if}
							</div>
							<span class="truncate">{folder.path}</span>
						</button>
					{/each}
				{/if}
			</div>

			<div class="border-t border-gray-100 p-2 dark:border-gray-800">
				<form class="flex items-center gap-1.5" on:submit|preventDefault={createFolderHandler}>
					<input
						class="min-w-0 flex-1 rounded-xl border border-gray-100 bg-transparent px-3 py-1.5 text-sm outline-hidden placeholder:text-gray-400 dark:border-gray-800 dark:placeholder:text-gray-500"
						placeholder={$i18n.t('New Folder')}
						bind:value={newFolderName}
						autocomplete="off"
					/>
					<Tooltip content={$i18n.t('Create Folder')} placement="top">
						<button
							type="submit"
							class="flex size-8 shrink-0 items-center justify-center rounded-full bg-gray-900 text-white transition hover:bg-black disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500 dark:bg-white dark:text-gray-900 dark:hover:bg-gray-100 dark:disabled:bg-gray-700"
							disabled={creating || newFolderName.trim() === ''}
							aria-label={$i18n.t('Create Folder')}
						>
							<PlusAlt className="size-4.5" strokeWidth="2" />
						</button>
					</Tooltip>
				</form>
			</div>
		</div>
	</Dropdown>
{/if}
