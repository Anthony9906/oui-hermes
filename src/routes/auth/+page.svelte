<script lang="ts">
	import DOMPurify from 'dompurify';
	import { marked } from 'marked';

	import { toast } from 'svelte-sonner';

	import { onMount, getContext, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { getBackendConfig } from '$lib/apis';
	import {
		ldapUserSignIn,
		getSessionUser,
		userSignIn,
		userSignUp,
		updateUserTimezone
	} from '$lib/apis/auths';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { WEBUI_NAME, config, user, socket } from '$lib/stores';

	import { generateInitialsImage, canvasPixelTest, getUserTimezone } from '$lib/utils';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import OnBoarding from '$lib/components/OnBoarding.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';

	const i18n = getContext('i18n');

	let loaded = false;

	let mode = $config?.features.enable_ldap ? 'ldap' : 'signin';

	let form = null;

	let name = '';
	let email = '';
	let password = '';
	let confirmPassword = '';

	let ldapUsername = '';

	const setSessionUser = async (sessionUser, redirectPath: string | null = null) => {
		if (sessionUser) {
			console.log(sessionUser);
			toast.success($i18n.t(`You're now logged in.`));
			if (sessionUser.token) {
				localStorage.token = sessionUser.token;
			}
			$socket.emit('user-join', { auth: { token: sessionUser.token } });
			await user.set(sessionUser);
			await config.set(await getBackendConfig());

			// Update user timezone
			const timezone = getUserTimezone();
			if (sessionUser.token && timezone) {
				updateUserTimezone(sessionUser.token, timezone);
			}

			if (!redirectPath) {
				redirectPath = $page.url.searchParams.get('redirect') || '/';
			}

			goto(redirectPath);
			localStorage.removeItem('redirectPath');
		}
	};

	const signInHandler = async () => {
		const sessionUser = await userSignIn(email, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		await setSessionUser(sessionUser);
	};

	const signUpHandler = async () => {
		if ($config?.features?.enable_signup_password_confirmation) {
			if (password !== confirmPassword) {
				toast.error($i18n.t('Passwords do not match.'));
				return;
			}
		}

		const sessionUser = await userSignUp(name, email, password, generateInitialsImage(name)).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);

		await setSessionUser(sessionUser);
	};

	const ldapSignInHandler = async () => {
		const sessionUser = await ldapUserSignIn(ldapUsername, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		await setSessionUser(sessionUser);
	};

	const submitHandler = async () => {
		if (mode === 'ldap') {
			await ldapSignInHandler();
		} else if (mode === 'signin') {
			await signInHandler();
		} else {
			await signUpHandler();
		}
	};

	const oauthCallbackHandler = async () => {
		// Get the value of the 'token' cookie
		function getCookie(name) {
			const match = document.cookie.match(
				new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)')
			);
			return match ? decodeURIComponent(match[1]) : null;
		}

		const token = getCookie('token');
		if (!token) {
			return;
		}

		const sessionUser = await getSessionUser(token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (!sessionUser) {
			return;
		}

		localStorage.token = token;
		await setSessionUser(sessionUser, localStorage.getItem('redirectPath') || null);
	};

	let onboarding = false;

	async function setLogoImage() {
		await tick();
		const logo = document.getElementById('logo');

		if (logo) {
			const isDarkMode = document.documentElement.classList.contains('dark');

			if (isDarkMode) {
				const darkImage = new Image();
				darkImage.src = `${WEBUI_BASE_URL}/static/favicon-dark.png`;

				darkImage.onload = () => {
					logo.src = `${WEBUI_BASE_URL}/static/favicon-dark.png`;
					logo.style.filter = ''; // Ensure no inversion is applied if favicon-dark.png exists
				};

				darkImage.onerror = () => {
					logo.style.filter = 'invert(1)'; // Invert image if favicon-dark.png is missing
				};
			}
		}
	}

	onMount(async () => {
		const redirectPath = $page.url.searchParams.get('redirect');
		if ($user !== undefined) {
			goto(redirectPath || '/');
		} else {
			if (redirectPath) {
				localStorage.setItem('redirectPath', redirectPath);
			}
		}

		const error = $page.url.searchParams.get('error');
		if (error) {
			toast.error(error);
		}

		await oauthCallbackHandler();
		form = $page.url.searchParams.get('form');

		loaded = true;
		setLogoImage();

		if (($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false) {
			await signInHandler();
		} else {
			onboarding = $config?.onboarding ?? false;
		}
	});
</script>

<svelte:head>
	<title>
		{`${$WEBUI_NAME}`}
	</title>
</svelte:head>

<OnBoarding
	bind:show={onboarding}
	getStartedHandler={() => {
		onboarding = false;
		mode = $config?.features.enable_ldap ? 'ldap' : 'signup';
	}}
/>

<div class="w-full h-screen max-h-[100dvh] text-[#071f4d] relative" id="auth-page">
	<div class="absolute inset-0 auth-page-bg"></div>

	<div class="w-full absolute top-0 left-0 right-0 h-8 drag-region"></div>

	{#if loaded}
		<div
			class="fixed bg-transparent min-h-screen max-h-[100dvh] overflow-y-auto w-full flex justify-center font-primary z-50 text-[#071f4d] dark:text-white"
			id="auth-container"
		>
			<div class="auth-shell w-full px-5 sm:px-8 min-h-screen flex flex-col text-center">
				{#if ($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false}
					<div class="auth-card my-auto w-full sm:max-w-md">
						<div
							class="flex items-center justify-center gap-3 text-xl sm:text-2xl text-center font-medium text-[#071f4d] dark:text-gray-100"
						>
							<div>
								{$i18n.t('Signing in to {{WEBUI_NAME}}', { WEBUI_NAME: $WEBUI_NAME })}
							</div>

							<div>
								<Spinner className="size-5" />
							</div>
						</div>
					</div>
				{:else}
					<div class="my-auto flex flex-col justify-center items-center">
						<div class="auth-card sm:max-w-md my-auto w-full dark:text-gray-100">
							<div class="auth-brand mb-6 flex items-center justify-center">
								<div class="auth-logo-mark" aria-hidden="true">
									<img
										id="logo"
										src="{WEBUI_BASE_URL}/static/favicon.png"
										class="auth-logo-image"
										alt=""
										draggable="false"
									/>
								</div>
							</div>
							<form
								class=" flex flex-col justify-center"
								on:submit={(e) => {
									e.preventDefault();
									submitHandler();
								}}
							>
								<div class="mb-1">
									<div
										class="auth-title text-2xl font-semibold tracking-normal text-[#071f4d] dark:text-gray-100"
									>
										{#if $config?.onboarding ?? false}
											{$i18n.t(`Get started with {{WEBUI_NAME}}`, { WEBUI_NAME: $WEBUI_NAME })}
										{:else if mode === 'ldap'}
											{$i18n.t(`Sign in with LDAP`, { WEBUI_NAME: $WEBUI_NAME })}
										{:else if mode === 'signin'}
											Expert Agent
										{:else}
											{$i18n.t(`Sign up`, { WEBUI_NAME: $WEBUI_NAME })}
										{/if}
									</div>

									{#if $config?.onboarding ?? false}
										<div class="mt-2 text-xs font-medium text-[#61708f] dark:text-gray-400">
											ⓘ {$WEBUI_NAME}
											{$i18n.t(
												'does not make any external connections, and your data stays securely on your locally hosted server.'
											)}
										</div>
									{/if}
								</div>

								{#if $config?.features.enable_login_form || $config?.features.enable_ldap || form}
									<div class="flex flex-col mt-4">
										{#if mode === 'signup'}
											<div class="mb-2">
												<label for="name" class="auth-label">{$i18n.t('Name')}</label>
												<input
													bind:value={name}
													type="text"
													id="name"
													class="auth-input"
													autocomplete="name"
													placeholder={$i18n.t('Enter Your Full Name')}
													required
												/>
											</div>
										{/if}

										{#if mode === 'ldap'}
											<div class="mb-2">
												<label for="username" class="auth-label">{$i18n.t('Username')}</label>
												<input
													bind:value={ldapUsername}
													type="text"
													class="auth-input"
													autocomplete="username"
													name="username"
													id="username"
													placeholder={$i18n.t('Enter Your Username')}
													required
												/>
											</div>
										{:else}
											<div class="mb-2">
												<label for="email" class="auth-label">{$i18n.t('Email')}</label>
												<input
													bind:value={email}
													type="email"
													id="email"
													class="auth-input"
													autocomplete="email"
													name="email"
													placeholder={$i18n.t('Enter Your Email')}
													required
												/>
											</div>
										{/if}

										<div>
											<label for="password" class="auth-label">{$i18n.t('Password')}</label>
											<SensitiveInput
												bind:value={password}
												type="password"
												id="password"
												outerClassName="auth-sensitive-input"
												inputClassName="w-full text-sm bg-transparent outline-hidden"
												showButtonClassName="pl-2 pr-1 transition bg-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-white"
												placeholder={$i18n.t('Enter Your Password')}
												autocomplete={mode === 'signup' ? 'new-password' : 'current-password'}
												name="password"
												screenReader={true}
												required
												aria-required="true"
											/>
										</div>

										{#if mode === 'signup' && $config?.features?.enable_signup_password_confirmation}
											<div class="mt-2">
												<label for="confirm-password" class="auth-label"
													>{$i18n.t('Confirm Password')}</label
												>
												<SensitiveInput
													bind:value={confirmPassword}
													type="password"
													id="confirm-password"
													outerClassName="auth-sensitive-input"
													inputClassName="w-full text-sm bg-transparent outline-hidden"
													showButtonClassName="pl-2 pr-1 transition bg-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-white"
													placeholder={$i18n.t('Confirm Your Password')}
													autocomplete="new-password"
													name="confirm-password"
													required
												/>
											</div>
										{/if}
									</div>
								{/if}
								<div class="mt-5">
									{#if $config?.features.enable_login_form || $config?.features.enable_ldap || form}
										{#if mode === 'ldap'}
											<button class="auth-primary-button" type="submit">
												{$i18n.t('Authenticate')}
											</button>
										{:else}
											<button class="auth-primary-button" type="submit">
												{mode === 'signin'
													? $i18n.t('Sign in')
													: ($config?.onboarding ?? false)
														? $i18n.t('Create Admin Account')
														: $i18n.t('Create Account')}
											</button>

											{#if $config?.features.enable_signup && !($config?.onboarding ?? false)}
												<div class="mt-4 text-sm text-center text-[#61708f] dark:text-gray-400">
													{mode === 'signin'
														? $i18n.t("Don't have an account?")
														: $i18n.t('Already have an account?')}

													<button
														class="font-semibold text-[#001f5b] underline underline-offset-2 hover:text-[#2563eb] dark:text-gray-200 dark:hover:text-white"
														type="button"
														on:click={() => {
															if (mode === 'signin') {
																mode = 'signup';
															} else {
																mode = 'signin';
															}
														}}
													>
														{mode === 'signin' ? $i18n.t('Sign up') : $i18n.t('Sign in')}
													</button>
												</div>
											{/if}
										{/if}
									{/if}
								</div>
							</form>

							{#if Object.keys($config?.oauth?.providers ?? {}).length > 0}
								<div class="inline-flex items-center justify-center w-full">
									<hr class="w-32 h-px my-4 border-0 bg-gray-200 dark:bg-gray-100/10" />
									{#if $config?.features.enable_login_form || $config?.features.enable_ldap || form}
										<span
											class="px-3 text-sm font-medium text-[#61708f] dark:text-gray-400 bg-transparent"
											>{$i18n.t('or')}</span
										>
									{/if}

									<hr class="w-32 h-px my-4 border-0 bg-gray-200 dark:bg-gray-100/10" />
								</div>
								<div class="flex flex-col space-y-2">
									{#if $config?.oauth?.providers?.google}
										<button
											class="auth-secondary-button"
											on:click={() => {
												window.location.href = `${WEBUI_BASE_URL}/oauth/google/login`;
											}}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 48 48"
												class="size-6 mr-3"
												aria-hidden="true"
											>
												<path
													fill="#EA4335"
													d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
												/><path
													fill="#4285F4"
													d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
												/><path
													fill="#FBBC05"
													d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
												/><path
													fill="#34A853"
													d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
												/><path fill="none" d="M0 0h48v48H0z" />
											</svg>
											<span>{$i18n.t('Continue with {{provider}}', { provider: 'Google' })}</span>
										</button>
									{/if}
									{#if $config?.oauth?.providers?.microsoft}
										<button
											class="auth-secondary-button"
											on:click={() => {
												window.location.href = `${WEBUI_BASE_URL}/oauth/microsoft/login`;
											}}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 21 21"
												class="size-6 mr-3"
												aria-hidden="true"
											>
												<rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect
													x="1"
													y="11"
													width="9"
													height="9"
													fill="#00a4ef"
												/><rect x="11" y="1" width="9" height="9" fill="#7fba00" /><rect
													x="11"
													y="11"
													width="9"
													height="9"
													fill="#ffb900"
												/>
											</svg>
											<span>{$i18n.t('Continue with {{provider}}', { provider: 'Microsoft' })}</span
											>
										</button>
									{/if}
									{#if $config?.oauth?.providers?.github}
										<button
											class="auth-secondary-button"
											on:click={() => {
												window.location.href = `${WEBUI_BASE_URL}/oauth/github/login`;
											}}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 24 24"
												class="size-6 mr-3"
												aria-hidden="true"
											>
												<path
													fill="currentColor"
													d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.92 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57C20.565 21.795 24 17.31 24 12c0-6.63-5.37-12-12-12z"
												/>
											</svg>
											<span>{$i18n.t('Continue with {{provider}}', { provider: 'GitHub' })}</span>
										</button>
									{/if}
									{#if $config?.oauth?.providers?.oidc}
										<button
											class="auth-secondary-button"
											on:click={() => {
												window.location.href = `${WEBUI_BASE_URL}/oauth/oidc/login`;
											}}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="1.5"
												stroke="currentColor"
												class="size-6 mr-3"
												aria-hidden="true"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 1 21.75 8.25Z"
												/>
											</svg>

											<span
												>{$i18n.t('Continue with {{provider}}', {
													provider: $config?.oauth?.providers?.oidc ?? 'SSO'
												})}</span
											>
										</button>
									{/if}
									{#if $config?.oauth?.providers?.feishu}
										<button
											class="auth-secondary-button"
											on:click={() => {
												window.location.href = `${WEBUI_BASE_URL}/oauth/feishu/login`;
											}}
										>
											<span>{$i18n.t('Continue with {{provider}}', { provider: 'Feishu' })}</span>
										</button>
									{/if}
								</div>
							{/if}

							{#if $config?.features.enable_ldap && $config?.features.enable_login_form}
								<div class="mt-2">
									<button
										class="flex justify-center items-center text-xs w-full text-center underline underline-offset-2 text-[#61708f] hover:text-[#2563eb] dark:text-gray-400 dark:hover:text-white"
										type="button"
										on:click={() => {
											if (mode === 'ldap')
												mode = ($config?.onboarding ?? false) ? 'signup' : 'signin';
											else mode = 'ldap';
										}}
									>
										<span
											>{mode === 'ldap'
												? $i18n.t('Continue with Email')
												: $i18n.t('Continue with LDAP')}</span
										>
									</button>
								</div>
							{/if}
						</div>
						{#if $config?.metadata?.login_footer}
							<div class="max-w-3xl mx-auto">
								<div class="mt-4 text-[0.7rem] text-[#61708f] dark:text-gray-400 marked">
									{@html DOMPurify.sanitize(marked($config?.metadata?.login_footer))}
								</div>
							</div>
						{/if}
						<div class="auth-copyright mt-4">© 2026&nbsp;&nbsp;Cowain AI</div>
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	.auth-shell {
		background: transparent;
	}

	.auth-page-bg {
		background: radial-gradient(circle at center, #ffffff 0%, #f7fbff 36%, #e3f1ff 100%);
	}

	:global(.dark) .auth-page-bg {
		background:
			linear-gradient(rgba(74, 85, 104, 0.2) 1px, transparent 1px),
			linear-gradient(90deg, rgba(74, 85, 104, 0.2) 1px, transparent 1px),
			linear-gradient(135deg, #111827 0%, #172033 48%, #0f172a 100%);
		background-size:
			32px 32px,
			32px 32px,
			100% 100%;
	}

	.auth-card {
		position: relative;
		overflow: hidden;
		border-radius: 0.75rem;
		border: 1px solid rgba(185, 211, 238, 0.8);
		background:
			linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(244, 250, 255, 0.9) 100%),
			radial-gradient(circle at 12% 16%, rgba(123, 220, 255, 0.16), transparent 34%);
		box-shadow:
			0 18px 48px rgba(16, 67, 132, 0.1),
			inset 0 1px 0 rgba(255, 255, 255, 0.88);
		padding: 2rem;
	}

	.auth-card::before {
		content: '';
		position: absolute;
		inset: 0;
		border-top: 2px solid rgba(123, 184, 238, 0.72);
		opacity: 0.72;
		pointer-events: none;
	}

	.auth-card > :global(*) {
		position: relative;
		z-index: 1;
	}

	:global(.dark) .auth-card {
		border-color: rgba(255, 255, 255, 0.1);
		background: rgba(23, 29, 45, 0.92);
		box-shadow:
			0 22px 52px rgba(0, 0, 0, 0.28),
			0 1px 0 rgba(255, 255, 255, 0.04) inset;
	}

	:global(.dark) .auth-card::before {
		border-top-color: rgba(154, 166, 200, 0.76);
	}

	.auth-brand {
		color: #2563eb;
	}

	.auth-brand-name {
		font-size: 1.375rem;
		font-weight: 700;
		line-height: 1;
		letter-spacing: 0;
	}

	.auth-logo-mark {
		display: flex;
		height: 2.75rem;
		width: 2.75rem;
		align-items: center;
		justify-content: center;
		border-radius: 0.875rem;
		overflow: hidden;
		background: #346aa8;
		box-shadow: 0 10px 24px rgba(0, 31, 91, 0.18);
	}

	.auth-logo-image {
		display: block;
		height: 100%;
		width: 100%;
		object-fit: cover;
		transform: scale(1.035);
		transform-origin: center;
	}

	.auth-title {
		line-height: 1.2;
	}

	.auth-copyright {
		font-size: 0.75rem;
		font-weight: 500;
		line-height: 1rem;
		color: #8a95a8;
	}

	:global(.dark) .auth-copyright {
		color: #6b7280;
	}

	:global(.auth-label) {
		display: block;
		margin-bottom: 0.375rem;
		text-align: left;
		font-size: 0.875rem;
		font-weight: 600;
		color: #2c3d63;
	}

	:global(.dark .auth-label) {
		color: #dce2ec;
	}

	:global(.auth-input),
	:global(.auth-sensitive-input) {
		width: 100%;
		border-radius: 0.75rem;
		border: 1px solid #d8e5f3;
		background: #fbfdff;
		color: #293246;
		box-shadow: 0 1px 0 rgba(255, 255, 255, 0.92) inset;
		transition:
			border-color 150ms ease,
			box-shadow 150ms ease,
			background 150ms ease;
	}

	:global(.auth-input) {
		padding: 0.75rem 0.875rem;
		font-size: 0.875rem;
		outline: none;
	}

	:global(.auth-sensitive-input) {
		display: flex;
		align-items: center;
		padding: 0.75rem 0.875rem;
	}

	:global(.auth-input::placeholder),
	:global(.auth-sensitive-input input::placeholder) {
		color: #9aa4b5;
	}

	:global(.auth-input:focus),
	:global(.auth-sensitive-input:focus-within) {
		border-color: #5f91c7;
		box-shadow:
			0 0 0 3px rgba(95, 145, 199, 0.16),
			0 1px 0 rgba(255, 255, 255, 0.92) inset;
	}

	:global(.dark .auth-input),
	:global(.dark .auth-sensitive-input) {
		border-color: rgba(255, 255, 255, 0.1);
		background: rgba(255, 255, 255, 0.06);
		color: #f5f7fb;
	}

	:global(.auth-primary-button),
	:global(.auth-secondary-button) {
		display: flex;
		width: 100%;
		align-items: center;
		justify-content: center;
		border-radius: 0.75rem;
		font-size: 0.875rem;
		font-weight: 600;
		transition:
			background-color 150ms ease,
			border-color 150ms ease,
			color 150ms ease,
			box-shadow 150ms ease;
	}

	:global(.auth-primary-button) {
		background: #001f5b;
		color: #ffffff;
		padding: 0.75rem 1rem;
		box-shadow: 0 10px 24px rgba(0, 31, 91, 0.18);
	}

	:global(.auth-primary-button:hover) {
		background: #071f4d;
	}

	:global(.auth-secondary-button) {
		border: 1px solid #d8e5f3;
		background: #ffffff;
		color: #2c3d63;
		padding: 0.625rem 1rem;
	}

	:global(.auth-secondary-button:hover) {
		border-color: #b9d3ee;
		background: #f1f7ff;
		color: #001f5b;
	}

	:global(.dark .auth-secondary-button) {
		border-color: rgba(255, 255, 255, 0.1);
		background: rgba(255, 255, 255, 0.06);
		color: #dce2ec;
	}

	:global(.dark .auth-secondary-button:hover) {
		background: rgba(255, 255, 255, 0.1);
		color: #ffffff;
	}

	@media (max-width: 640px) {
		.auth-card {
			padding: 1.5rem;
		}
	}
</style>
