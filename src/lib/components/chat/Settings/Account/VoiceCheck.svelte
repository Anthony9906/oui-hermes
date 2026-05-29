<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { settings } from '$lib/stores';
	import { transcribeAudio } from '$lib/apis/audio';

	import VoiceRecording from '$lib/components/chat/MessageInput/VoiceRecording.svelte';
	import Mic from '$lib/components/icons/Mic.svelte';
	import CheckCircle from '$lib/components/icons/CheckCircle.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import Refresh from '$lib/components/icons/Refresh.svelte';

	const i18n = getContext('i18n');

	export let saveSettings: Function;

	type VoiceProfile = {
		version: number;
		embedding: number[];
		dimensions: number;
		enrolledAt: number;
		transcript?: string;
		transcripts?: string[];
		sampleCount?: number;
		durationSeconds?: number;
		threshold: number;
	};

	type EnrollmentSample = {
		embedding: number[];
		transcript?: string;
		challengeText?: string;
		durationSeconds?: number;
	};

	type VoiceTestResult = {
		score: number;
		passed: boolean;
		transcript?: string;
		textMatched?: boolean;
		durationSeconds?: number;
	};

	let show = false;
	let recording = false;
	let recordingMode: 'enroll' | 'test' | null = null;
	let processing = false;
	let testResult: VoiceTestResult | null = null;
	let challengeText = '';
	let enrollmentChallengeText = '';
	let voiceProfile: VoiceProfile | undefined;
	let enrollmentSamples: EnrollmentSample[] = [];

	const DEFAULT_THRESHOLD = 0.82;
	const ENROLLMENT_SAMPLE_COUNT = 3;
	const BAND_FREQUENCIES = [120, 180, 260, 380, 550, 800, 1150, 1650, 2400, 3400];
	const SEGMENT_COUNT = 16;
	const TARGET_SAMPLE_RATE = 16000;

	$: voiceProfile = $settings?.experimentalVoiceCheck as VoiceProfile | undefined;

	const generateChallengeText = () => {
		const digits = Array.from({ length: 6 }, () => Math.floor(Math.random() * 10)).join('');
		challengeText = `${digits.slice(0, 3)} ${digits.slice(3)}`;
	};

	const generateEnrollmentChallengeText = () => {
		const digits = Array.from({ length: 6 }, () => Math.floor(Math.random() * 10)).join('');
		enrollmentChallengeText = `${digits.slice(0, 3)} ${digits.slice(3)}`;
	};

	const DIGIT_WORDS = [
		['zero', '0'],
		['one', '1'],
		['two', '2'],
		['three', '3'],
		['four', '4'],
		['five', '5'],
		['six', '6'],
		['seven', '7'],
		['eight', '8'],
		['nine', '9'],
		['零', '0'],
		['〇', '0'],
		['一', '1'],
		['二', '2'],
		['两', '2'],
		['三', '3'],
		['四', '4'],
		['五', '5'],
		['六', '6'],
		['七', '7'],
		['八', '8'],
		['九', '9']
	];

	const normalizeText = (text: string) => {
		let normalized = text.toLowerCase();

		for (const [word, digit] of DIGIT_WORDS) {
			normalized = normalized.replaceAll(word, digit);
		}

		return normalized.replace(/[^a-z0-9]/g, '');
	};

	const hasChallengeMatch = (transcript = '', expectedText = challengeText) => {
		const expected = normalizeText(expectedText);
		if (!expected) {
			return undefined;
		}

		return normalizeText(transcript).includes(expected);
	};

	const cosineSimilarity = (a: number[], b: number[]) => {
		if (a.length !== b.length || a.length === 0) {
			return 0;
		}

		let dot = 0;
		let normA = 0;
		let normB = 0;

		for (let i = 0; i < a.length; i++) {
			dot += a[i] * b[i];
			normA += a[i] * a[i];
			normB += b[i] * b[i];
		}

		if (normA === 0 || normB === 0) {
			return 0;
		}

		return dot / (Math.sqrt(normA) * Math.sqrt(normB));
	};

	const averageEmbeddings = (samples: EnrollmentSample[]) => {
		const dimensions = samples[0]?.embedding?.length ?? 0;
		if (!dimensions || samples.some((sample) => sample.embedding.length !== dimensions)) {
			throw new Error('Voice samples are not compatible.');
		}

		const averaged = Array(dimensions).fill(0);

		for (const sample of samples) {
			for (let i = 0; i < dimensions; i++) {
				averaged[i] += sample.embedding[i];
			}
		}

		return averaged.map((value) => Number((value / samples.length).toFixed(5)));
	};

	const downsample = (input: Float32Array, inputSampleRate: number) => {
		if (inputSampleRate === TARGET_SAMPLE_RATE) {
			return input;
		}

		const sampleRateRatio = inputSampleRate / TARGET_SAMPLE_RATE;
		const outputLength = Math.floor(input.length / sampleRateRatio);
		const output = new Float32Array(outputLength);

		for (let i = 0; i < outputLength; i++) {
			const start = Math.floor(i * sampleRateRatio);
			const end = Math.min(Math.floor((i + 1) * sampleRateRatio), input.length);
			let sum = 0;

			for (let j = start; j < end; j++) {
				sum += input[j];
			}

			output[i] = sum / Math.max(1, end - start);
		}

		return output;
	};

	const trimSilence = (samples: Float32Array) => {
		const windowSize = Math.floor(TARGET_SAMPLE_RATE * 0.03);
		const threshold = 0.01;
		let start = 0;
		let end = samples.length;

		for (let i = 0; i < samples.length - windowSize; i += windowSize) {
			let energy = 0;
			for (let j = i; j < i + windowSize; j++) {
				energy += samples[j] * samples[j];
			}

			if (Math.sqrt(energy / windowSize) > threshold) {
				start = i;
				break;
			}
		}

		for (let i = samples.length - windowSize; i > windowSize; i -= windowSize) {
			let energy = 0;
			for (let j = i; j < i + windowSize; j++) {
				energy += samples[j] * samples[j];
			}

			if (Math.sqrt(energy / windowSize) > threshold) {
				end = i + windowSize;
				break;
			}
		}

		return samples.slice(start, Math.max(start + 1, end));
	};

	const goertzelPower = (samples: Float32Array, start: number, end: number, frequency: number) => {
		const length = Math.max(1, end - start);
		const normalizedFrequency = frequency / TARGET_SAMPLE_RATE;
		const coefficient = 2 * Math.cos(2 * Math.PI * normalizedFrequency);
		let previous = 0;
		let previous2 = 0;

		for (let i = start; i < end; i++) {
			const value = samples[i] + coefficient * previous - previous2;
			previous2 = previous;
			previous = value;
		}

		return (
			(previous2 * previous2 + previous * previous - coefficient * previous * previous2) / length
		);
	};

	const normalizeVector = (vector: number[]) => {
		const mean = vector.reduce((sum, value) => sum + value, 0) / vector.length;
		const variance =
			vector.reduce((sum, value) => sum + Math.pow(value - mean, 2), 0) / vector.length;
		const std = Math.sqrt(variance) || 1;

		return vector.map((value) => Number(((value - mean) / std).toFixed(5)));
	};

	const extractVoiceEmbedding = async (blob: Blob) => {
		const AudioContextClass =
			window.AudioContext ||
			(window as Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext })
				.webkitAudioContext;
		if (!AudioContextClass) {
			throw new Error('Audio processing is not supported in this browser.');
		}

		const audioContext = new AudioContextClass();

		try {
			const audioBuffer = await audioContext.decodeAudioData(await blob.arrayBuffer());
			const samples = trimSilence(
				downsample(audioBuffer.getChannelData(0), audioBuffer.sampleRate)
			);
			const durationSeconds = samples.length / TARGET_SAMPLE_RATE;

			if (durationSeconds < 1.2) {
				throw new Error('Recording is too short.');
			}

			const vector: number[] = [];
			const segmentLength = Math.floor(samples.length / SEGMENT_COUNT);

			for (let segment = 0; segment < SEGMENT_COUNT; segment++) {
				const start = segment * segmentLength;
				const end =
					segment === SEGMENT_COUNT - 1
						? samples.length
						: Math.min(samples.length, start + segmentLength);

				let energy = 0;
				let zeroCrossings = 0;
				for (let i = start + 1; i < end; i++) {
					energy += samples[i] * samples[i];
					if ((samples[i - 1] < 0 && samples[i] >= 0) || (samples[i - 1] >= 0 && samples[i] < 0)) {
						zeroCrossings++;
					}
				}

				vector.push(Math.log(Math.sqrt(energy / Math.max(1, end - start)) + 1e-6));
				vector.push(zeroCrossings / Math.max(1, end - start));

				for (const frequency of BAND_FREQUENCIES) {
					vector.push(Math.log(goertzelPower(samples, start, end, frequency) + 1e-8));
				}
			}

			return {
				embedding: normalizeVector(vector),
				durationSeconds
			};
		} finally {
			await audioContext.close();
		}
	};

	const transcribeRecording = async (file: File) => {
		const res = await transcribeAudio(
			localStorage.token,
			file,
			$settings?.audio?.stt?.language
		).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		return res?.text ?? res?.transcript ?? '';
	};

	const saveVoiceProfile = async (profile: VoiceProfile | null) => {
		await saveSettings({
			experimentalVoiceCheck: profile ?? undefined
		});
	};

	const processEnrollment = async (file: File, blob: Blob) => {
		processing = true;
		testResult = null;

		try {
			const [{ embedding, durationSeconds }, transcript] = await Promise.all([
				extractVoiceEmbedding(blob),
				transcribeRecording(file)
			]);
			const textMatched = hasChallengeMatch(transcript, enrollmentChallengeText);

			if (textMatched === false) {
				toast.error('Enrollment phrase did not match. Please record this sample again.');
				return;
			}

			const samples = [
				...enrollmentSamples,
				{
					embedding,
					transcript,
					challengeText: enrollmentChallengeText,
					durationSeconds
				}
			];

			enrollmentSamples = samples;

			if (samples.length < ENROLLMENT_SAMPLE_COUNT) {
				toast.success(`Voice sample ${samples.length}/${ENROLLMENT_SAMPLE_COUNT} recorded.`);
				generateEnrollmentChallengeText();
				return;
			}

			const averagedEmbedding = averageEmbeddings(samples);
			const transcripts = samples.map((sample) => sample.transcript ?? '').filter(Boolean);
			const averageDurationSeconds =
				samples.reduce((total, sample) => total + (sample.durationSeconds ?? 0), 0) /
				samples.length;

			await saveVoiceProfile({
				version: 2,
				embedding: averagedEmbedding,
				dimensions: averagedEmbedding.length,
				enrolledAt: Date.now(),
				transcript: transcripts.join(' / '),
				transcripts,
				sampleCount: samples.length,
				durationSeconds: averageDurationSeconds,
				threshold: voiceProfile?.threshold ?? DEFAULT_THRESHOLD
			});

			enrollmentSamples = [];
			generateEnrollmentChallengeText();
			toast.success($i18n.t('Successfully updated.'));
		} catch (error) {
			toast.error(error instanceof Error ? error.message : `${error}`);
		} finally {
			processing = false;
		}
	};

	const processTest = async (file: File, blob: Blob) => {
		if (!voiceProfile?.embedding?.length) {
			toast.error($i18n.t('No voice profile found.'));
			return;
		}

		processing = true;
		testResult = null;

		try {
			const [{ embedding, durationSeconds }, transcript] = await Promise.all([
				extractVoiceEmbedding(blob),
				transcribeRecording(file)
			]);
			const score = cosineSimilarity(voiceProfile.embedding, embedding);
			const textMatched = hasChallengeMatch(transcript);
			const passed =
				score >= (voiceProfile.threshold ?? DEFAULT_THRESHOLD) && textMatched !== false;

			testResult = {
				score,
				passed,
				transcript,
				textMatched,
				durationSeconds
			};
		} catch (error) {
			toast.error(error instanceof Error ? error.message : `${error}`);
		} finally {
			processing = false;
		}
	};

	const handleRecording = async ({ file, blob }) => {
		const mode = recordingMode;
		recordingMode = null;

		if (mode === 'enroll') {
			await processEnrollment(file, blob);
		} else if (mode === 'test') {
			await processTest(file, blob);
		}
	};

	const startRecording = (mode: 'enroll' | 'test') => {
		if (mode === 'enroll' && enrollmentSamples.length >= ENROLLMENT_SAMPLE_COUNT) {
			enrollmentSamples = [];
		}

		if (mode === 'enroll' && !enrollmentChallengeText) {
			generateEnrollmentChallengeText();
		}

		if (mode === 'test' && !challengeText) {
			generateChallengeText();
		}

		recordingMode = mode;
		recording = true;
	};

	const deleteVoiceProfile = async () => {
		await saveVoiceProfile(null);
		testResult = null;
		enrollmentSamples = [];
		generateEnrollmentChallengeText();
		toast.success($i18n.t('Successfully updated.'));
	};

	onMount(() => {
		generateChallengeText();
		generateEnrollmentChallengeText();
	});
</script>

<div class="flex flex-col text-sm">
	<div class="flex justify-between items-center text-sm">
		<div class="font-medium">
			Voice Check <span class="text-xs text-gray-500">Experimental</span>
		</div>
		<button
			class="text-xs font-medium text-gray-500"
			type="button"
			on:click={() => {
				show = !show;
			}}>{show ? $i18n.t('Hide') : $i18n.t('Show')}</button
		>
	</div>

	{#if show}
		<div class="py-2.5 space-y-3">
			<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
				<button
					type="button"
					class="flex items-center justify-center gap-2 rounded-md border border-gray-100 dark:border-gray-800 px-3 py-2 text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-850 disabled:opacity-50"
					disabled={recording || processing}
					on:click={() => startRecording('enroll')}
				>
					<Mic className="size-4" strokeWidth="2" />
					{#if enrollmentSamples.length > 0}
						Record sample {enrollmentSamples.length + 1}/{ENROLLMENT_SAMPLE_COUNT}
					{:else if voiceProfile}
						Re-record voice profile
					{:else}
						Record voice profile
					{/if}
				</button>

				<button
					type="button"
					class="flex items-center justify-center gap-2 rounded-md border border-gray-100 dark:border-gray-800 px-3 py-2 text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-850 disabled:opacity-50"
					disabled={!voiceProfile || recording || processing}
					on:click={() => startRecording('test')}
				>
					<CheckCircle className="size-4" strokeWidth="2" />
					Test voice check
				</button>
			</div>

			<div class="rounded-md border border-gray-100 dark:border-gray-800 px-3 py-2">
				<div class="text-xs text-gray-500">
					Enrollment sample {Math.min(
						enrollmentSamples.length + 1,
						ENROLLMENT_SAMPLE_COUNT
					)}/{ENROLLMENT_SAMPLE_COUNT}
				</div>
				<div class="mt-1 text-xs text-gray-500">
					Read: <span class="font-medium text-gray-700 dark:text-gray-200"
						>{enrollmentChallengeText}</span
					>
				</div>
			</div>

			{#if recording}
				<VoiceRecording
					bind:recording
					transcribe={false}
					className="p-2 w-full max-w-full"
					onCancel={() => {
						recordingMode = null;
						recording = false;
					}}
					onConfirm={handleRecording}
				/>
			{/if}

			{#if processing}
				<div class="text-xs text-gray-500">Processing voice sample...</div>
			{/if}

			{#if enrollmentSamples.length > 0}
				<div
					class="rounded-md bg-gray-50 dark:bg-gray-850/70 px-3 py-2 text-xs text-gray-600 dark:text-gray-300"
				>
					Enrollment samples: {enrollmentSamples.length}/{ENROLLMENT_SAMPLE_COUNT}
				</div>
			{/if}

			{#if voiceProfile}
				<div
					class="rounded-md bg-gray-50 dark:bg-gray-850/70 px-3 py-2 text-xs text-gray-600 dark:text-gray-300 space-y-1.5"
				>
					<div class="flex items-center justify-between gap-2">
						<div>
							Embedding: {voiceProfile.dimensions} dimensions · threshold {(
								voiceProfile.threshold ?? DEFAULT_THRESHOLD
							).toFixed(2)} · samples {voiceProfile.sampleCount ?? 1}
						</div>
						<button
							type="button"
							class="text-gray-500 hover:text-red-600 dark:hover:text-red-400"
							disabled={processing || recording}
							on:click={deleteVoiceProfile}
							aria-label="Delete voice profile"
						>
							<XMark className="size-4" strokeWidth="2" />
						</button>
					</div>

					{#if voiceProfile.transcript}
						<div class="line-clamp-2">Enrollment STT: {voiceProfile.transcript}</div>
					{/if}
				</div>
			{/if}

			{#if voiceProfile}
				<div class="rounded-md border border-gray-100 dark:border-gray-800 px-3 py-2 space-y-2">
					<div class="flex items-center justify-between gap-3">
						<div class="text-xs text-gray-500">
							Read: <span class="font-medium text-gray-700 dark:text-gray-200">{challengeText}</span
							>
						</div>
						<button
							type="button"
							class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-200 disabled:opacity-50"
							disabled={recording || processing}
							on:click={generateChallengeText}
							aria-label="Refresh challenge text"
						>
							<Refresh className="size-4" strokeWidth="2" />
						</button>
					</div>

					{#if testResult}
						<div
							class="rounded-md px-3 py-2 text-xs {testResult.passed
								? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300'
								: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-300'}"
						>
							<div class="font-medium">
								{testResult.passed ? 'Voice match passed' : 'Voice match failed'} · score {testResult.score.toFixed(
									3
								)}
							</div>
							{#if testResult.transcript}
								<div class="mt-1 text-current/80">STT: {testResult.transcript}</div>
							{/if}
							{#if testResult.textMatched !== undefined}
								<div class="mt-1 text-current/80">
									Challenge text: {testResult.textMatched ? 'matched' : 'not matched'}
								</div>
							{/if}
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>
