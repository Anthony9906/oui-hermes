<script lang="ts">
	export let name = 'sparkles';
	export let className = 'size-5';
	export let strokeWidth = '1.9';

	const icons: Record<string, string> = {
		sparkles:
			'<path d="M9.94 15.5 8.5 19.25 7.06 15.5 3.31 14.06 7.06 12.62 8.5 8.87 9.94 12.62 13.69 14.06 9.94 15.5Z"/><path d="M18 8.5 17.25 10.25 15.5 11 17.25 11.75 18 13.5 18.75 11.75 20.5 11 18.75 10.25 18 8.5Z"/><path d="M16 2.75 14.94 5.06 12.63 6.12 14.94 7.18 16 9.49 17.06 7.18 19.37 6.12 17.06 5.06 16 2.75Z"/>',
		'book-open':
			'<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H3Z"/><path d="M21 18h-6a3 3 0 0 0-3 3V7a4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1Z"/>',
		bot: '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
		wrench:
			'<path d="M14.7 6.3a4.1 4.1 0 0 0-5.5 5.5L3 18l3 3 6.2-6.2a4.1 4.1 0 0 0 5.5-5.5l-2.6 2.6-3-3 2.6-2.6Z"/>',
		boxes:
			'<path d="M2.97 12.92 12 17.85l9.03-4.93"/><path d="M12 22.08V17.85"/><path d="m7.5 10.45 9-4.9"/><path d="m7.5 5.55 9 4.9"/><path d="M2.97 7.08 12 2.15l9.03 4.93v9.84L12 21.85l-9.03-4.93V7.08Z"/>',
		compass:
			'<circle cx="12" cy="12" r="10"/><path d="m16.24 7.76-2.12 6.36-6.36 2.12 2.12-6.36 6.36-2.12Z"/>',
		workflow:
			'<rect width="8" height="8" x="3" y="3" rx="2"/><rect width="8" height="8" x="13" y="13" rx="2"/><path d="M7 11v4a2 2 0 0 0 2 2h4"/><path d="M13 7h4a2 2 0 0 1 2 2v4"/>',
		'drafting-compass':
			'<path d="m12 2 7 19"/><path d="m12 2-7 19"/><path d="M19.5 21h-15"/><path d="M12 2v6"/><path d="M8.5 11h7"/>',
		'chart-no-axes-combined':
			'<path d="M12 16v5"/><path d="M16 14v7"/><path d="M20 10v11"/><path d="m22 3-8.65 8.65a.5.5 0 0 1-.7 0L9.35 8.35a.5.5 0 0 0-.7 0L2 15"/><path d="M4 18v3"/><path d="M8 14v7"/>',
		database:
			'<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/>',
		'file-text':
			'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
		lightbulb:
			'<path d="M15 14c.2-1 .7-1.7 1.4-2.5A5 5 0 1 0 7.6 11.5C8.3 12.3 8.8 13 9 14"/><path d="M9 18h6"/><path d="M10 22h4"/><path d="M10 18a2 2 0 1 1 4 0"/>',
		hammer:
			'<path d="m15 12-8.5 8.5a2.12 2.12 0 1 1-3-3L12 9"/><path d="m17.64 15 4.24-4.24"/><path d="m20.49 7.93-1.42-1.42a2 2 0 0 0-2.83 0l-2.12 2.12 4.24 4.24 2.13-2.11a2 2 0 0 0 0-2.83Z"/>',
		cog: '<path d="M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5Z"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 8.92 4a1.65 1.65 0 0 0 1-1.51V2.4a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/>',
		cpu: '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M9 2v2"/><path d="M9 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/>',
		'circuit-board':
			'<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M11 9h4v4h-4z"/><path d="M7 7h.01"/><path d="M7 17h.01"/><path d="M17 17h.01"/><path d="M7 7v4h4"/><path d="M17 17v-4h-2"/><path d="M7 17h4v-4"/>',
		blocks:
			'<rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><path d="M7 14v-2a2 2 0 0 1 2-2h5"/><path d="M17.5 10v4"/>',
		package:
			'<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
		factory:
			'<path d="M2 20h20"/><path d="M4 20V8l6 4V8l6 4V4h4v16"/><path d="M8 16h.01"/><path d="M12 16h.01"/><path d="M16 16h.01"/>',
		ruler:
			'<path d="M21.3 15.3 15.4 21.2a1 1 0 0 1-1.4 0L2.8 10a1 1 0 0 1 0-1.4l5.9-5.9a1 1 0 0 1 1.4 0l11.2 11.2a1 1 0 0 1 0 1.4Z"/><path d="m14.5 5.5-2 2"/><path d="m17.5 8.5-2 2"/><path d="m8.5 11.5-2 2"/><path d="m11.5 14.5-2 2"/>',
		'pencil-ruler':
			'<path d="m15 5 4 4"/><path d="M13 7 4 16v4h4l9-9"/><path d="M19 9 21 7a2.8 2.8 0 0 0-4-4l-2 2"/><path d="M14 4 4 14"/><path d="m5 13 6 6"/>',
		'scan-search':
			'<path d="M7 3H5a2 2 0 0 0-2 2v2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><circle cx="11" cy="11" r="3"/><path d="m16 16-2.2-2.2"/>',
		search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
		'clipboard-list':
			'<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M8 11h8"/><path d="M8 16h8"/>',
		table:
			'<path d="M12 3v18"/><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/>',
		presentation:
			'<path d="M2 3h20"/><path d="M21 3v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3"/><path d="m7 21 5-5 5 5"/>',
		code: '<path d="m16 18 6-6-6-6"/><path d="m8 6-6 6 6 6"/>',
		terminal: '<path d="m4 17 6-6-6-6"/><path d="M12 19h8"/>',
		rocket:
			'<path d="M4.5 16.5c-1.2 1.2-1.5 3.7-1.5 3.7s2.5-.3 3.7-1.5c.7-.7.7-1.8 0-2.5-.6-.5-1.7-.5-2.2.3Z"/><path d="m9 15-4-4s3-6 9-8c3.3-1.1 5.8-.8 6.7-.5.3.9.6 3.4-.5 6.7-2 6-8 9-8 9l-3.2-3.2Z"/><path d="M15 9h.01"/>',
		'shield-check':
			'<path d="M20 13c0 5-3.5 7.5-7.3 8.8a2 2 0 0 1-1.4 0C7.5 20.5 4 18 4 13V5a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.4a1.5 1.5 0 0 1 1.6 0C14.5 2.8 17 4 19 4a1 1 0 0 1 1 1Z"/><path d="m9 12 2 2 4-4"/>',
		'brain-circuit':
			'<path d="M12 5a3 3 0 1 0-5.2 2.1A3 3 0 0 0 7 13a3 3 0 0 0 4 2.8"/><path d="M12 5a3 3 0 1 1 5.2 2.1A3 3 0 0 1 17 13a3 3 0 0 1-4 2.8"/><path d="M12 5v14"/><path d="M9 19h6"/><path d="M19 11h2"/><path d="M3 11h2"/>',
		'messages-square':
			'<path d="M14 9a2 2 0 0 1 2 2v6l-4-3H8a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1"/><path d="M18 9h1a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2h-1l-4 3v-3"/>'
	};

	$: normalizedName = name
		.trim()
		.replace(/\.svg$/i, '')
		.replace(/^lucide[-_]/i, '')
		.replace(/([a-z0-9])([A-Z])/g, '$1-$2')
		.replace(/[\s_]+/g, '-')
		.replace(/[^a-zA-Z0-9-]/g, '')
		.replace(/-+/g, '-')
		.replace(/^-|-$/g, '')
		.toLowerCase();
	$: iconSvg = icons[normalizedName];
	$: remoteIconUrl =
		normalizedName && /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(normalizedName)
			? `https://unpkg.com/lucide-static@latest/icons/${normalizedName}.svg`
			: '';
</script>

{#if iconSvg}
	<svg
		xmlns="http://www.w3.org/2000/svg"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width={strokeWidth}
		stroke-linecap="round"
		stroke-linejoin="round"
		class={className}
		aria-hidden="true"
	>
		{@html iconSvg}
	</svg>
{:else if remoteIconUrl}
	<span
		class={`inline-block bg-current ${className}`}
		style={`mask: url("${remoteIconUrl}") center / contain no-repeat; -webkit-mask: url("${remoteIconUrl}") center / contain no-repeat;`}
		aria-hidden="true"
	></span>
{:else}
	<svg
		xmlns="http://www.w3.org/2000/svg"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width={strokeWidth}
		stroke-linecap="round"
		stroke-linejoin="round"
		class={className}
		aria-hidden="true"
	>
		{@html icons.bot}
	</svg>
{/if}
