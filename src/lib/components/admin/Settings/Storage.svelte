<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { getStorageConfig, setStorageConfig, verifyStorageConfig } from '$lib/apis/configs';

	const i18n = getContext('i18n');

	export let saveHandler: () => void = () => {};

	let loading = true;
	let saving = false;
	let verifying = false;

	let provider = 'r2';
	let endpointUrl = '';
	let bucketName = '';
	let regionName = '';
	let accessKeyId = '';
	let secretAccessKey = '';
	let addressingStyle = 'path';
	let keyPrefix = '';
	let publicBaseUrl = '';
	let accessKeyConfigured = false;
	let secretKeyConfigured = false;

	const toPayload = () => ({
		provider,
		endpoint_url: endpointUrl,
		bucket_name: bucketName,
		region_name: regionName,
		access_key_id: accessKeyId,
		secret_access_key: secretAccessKey,
		addressing_style: addressingStyle,
		key_prefix: keyPrefix,
		public_base_url: publicBaseUrl
	});

	const applyConfig = (config) => {
		provider = config.provider || 'r2';
		endpointUrl = config.endpoint_url || '';
		bucketName = config.bucket_name || '';
		regionName = config.region_name || '';
		addressingStyle = config.addressing_style || (provider === 'r2' ? 'path' : '');
		keyPrefix = config.key_prefix || '';
		publicBaseUrl = config.public_base_url || '';
		accessKeyConfigured = Boolean(config.access_key_configured);
		secretKeyConfigured = Boolean(config.secret_key_configured);
		accessKeyId = '';
		secretAccessKey = '';
	};

	const loadConfig = async () => {
		loading = true;
		const config = await getStorageConfig(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (config) {
			applyConfig(config);
		}
		loading = false;
	};

	const saveConfig = async () => {
		saving = true;
		const config = await setStorageConfig(localStorage.token, toPayload()).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (config) {
			applyConfig(config);
			saveHandler();
		}
		saving = false;
	};

	const verifyConfig = async () => {
		verifying = true;
		const result = await verifyStorageConfig(localStorage.token, toPayload()).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (result?.status) {
			toast.success($i18n.t('Storage connection verified'));
		}
		verifying = false;
	};

	onMount(loadConfig);
</script>

<div class="flex flex-col gap-6 text-sm text-gray-700 dark:text-gray-200">
	<div>
		<div class="text-base font-medium text-gray-900 dark:text-gray-100">
			{$i18n.t('Attachment Storage')}
		</div>
		<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
			{$i18n.t('Configure the object storage used for uploaded attachments.')}
		</div>
	</div>

	{#if loading}
		<div class="text-sm text-gray-500 dark:text-gray-400">{$i18n.t('Loading...')}</div>
	{:else}
		<div class="grid grid-cols-1 gap-4 max-w-3xl">
			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium">{$i18n.t('Provider')}</span>
				<select
					class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 outline-hidden"
					bind:value={provider}
				>
					<option value="r2">Cloudflare R2</option>
					<option value="s3">S3 Compatible</option>
				</select>
			</label>

			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium">{$i18n.t('Endpoint URL')}</span>
				<input
					class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 outline-hidden"
					placeholder="https://<account-id>.r2.cloudflarestorage.com"
					bind:value={endpointUrl}
				/>
			</label>

			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium">{$i18n.t('Bucket')}</span>
					<input
						class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 outline-hidden"
						bind:value={bucketName}
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium">{$i18n.t('Region')}</span>
					<input
						class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 outline-hidden"
						placeholder={provider === 'r2' ? 'auto' : 'us-east-1'}
						bind:value={regionName}
					/>
				</label>
			</div>

			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium">{$i18n.t('Access Key')}</span>
					<input
						class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 outline-hidden"
						placeholder={accessKeyConfigured ? $i18n.t('Configured') : ''}
						bind:value={accessKeyId}
						autocomplete="off"
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium">{$i18n.t('Secret Key')}</span>
					<input
						type="password"
						class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 outline-hidden"
						placeholder={secretKeyConfigured ? $i18n.t('Configured') : ''}
						bind:value={secretAccessKey}
						autocomplete="new-password"
					/>
				</label>
			</div>

			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium">{$i18n.t('Addressing Style')}</span>
					<select
						class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 outline-hidden"
						bind:value={addressingStyle}
					>
						<option value="">{$i18n.t('Default')}</option>
						<option value="path">path</option>
						<option value="virtual">virtual</option>
					</select>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs font-medium">{$i18n.t('Key Prefix')}</span>
					<input
						class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 outline-hidden"
						placeholder="open-webui"
						bind:value={keyPrefix}
					/>
				</label>
			</div>

			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium">{$i18n.t('Public Base URL')}</span>
				<input
					class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 outline-hidden"
					placeholder="https://assets.example.com"
					bind:value={publicBaseUrl}
				/>
			</label>
		</div>

		<div class="flex gap-2">
			<button
				class="px-3.5 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700"
				disabled={verifying || saving}
				on:click={verifyConfig}
			>
				{verifying ? $i18n.t('Verifying...') : $i18n.t('Verify')}
			</button>
			<button
				class="px-3.5 py-2 rounded-lg bg-black text-white hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200"
				disabled={saving || verifying}
				on:click={saveConfig}
			>
				{saving ? $i18n.t('Saving...') : $i18n.t('Save')}
			</button>
		</div>
	{/if}
</div>
