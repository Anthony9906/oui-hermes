import { copyFile, mkdir, readdir, rm, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const sourceDir = join(root, 'node_modules', 'lucide-static', 'icons');
const targetDir = join(root, 'static', 'assets', 'icons', 'lucide');
const iconNamesFile = join(root, 'src', 'lib', 'components', 'expert-agents', 'lucideIconNames.ts');

const files = (await readdir(sourceDir))
	.filter((file) => file.endsWith('.svg'))
	.sort((a, b) => a.localeCompare(b));

await mkdir(targetDir, { recursive: true });

for (const file of await readdir(targetDir)) {
	if (file.endsWith('.svg')) {
		await rm(join(targetDir, file));
	}
}

for (const file of files) {
	await copyFile(join(sourceDir, file), join(targetDir, file));
}

const iconNames = files.map((file) => file.replace(/\.svg$/, ''));
const iconNamesSource = `export const LUCIDE_ICON_NAMES = [
${iconNames.map((name) => `\t'${name}'`).join(',\n')}
] as const;

const LUCIDE_ICON_NAME_SET = new Set<string>(LUCIDE_ICON_NAMES);

export const isLocalLucideIconName = (name: string) => LUCIDE_ICON_NAME_SET.has(name);
`;

await writeFile(iconNamesFile, iconNamesSource);

console.log(`Synced ${files.length} lucide icons to static/assets/icons/lucide`);
