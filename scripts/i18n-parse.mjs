import fs from 'node:fs';
import path from 'node:path';

const sourceRoot = path.resolve('src');
const localesRoot = path.resolve('src/lib/i18n/locales');
const languagesFile = path.join(localesRoot, 'languages.json');
const sourceExtensions = new Set(['.js', '.svelte']);

const readJson = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));

const walk = (dir, files = []) => {
	for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
		const fullPath = path.join(dir, entry.name);
		if (entry.isDirectory()) {
			walk(fullPath, files);
		} else if (sourceExtensions.has(path.extname(entry.name))) {
			files.push(fullPath);
		}
	}
	return files;
};

const readQuotedString = (source, start) => {
	const quote = source[start];
	if (quote !== "'" && quote !== '"' && quote !== '`') {
		return null;
	}

	let value = '';
	for (let i = start + 1; i < source.length; i += 1) {
		const ch = source[i];
		if (ch === '\\') {
			const next = source[i + 1];
			if (next === undefined) {
				return null;
			}
			value += ch + next;
			i += 1;
			continue;
		}
		if (ch === quote) {
			try {
				return { value: Function(`return ${source.slice(start, i + 1)}`)(), end: i + 1 };
			} catch {
				return { value, end: i + 1 };
			}
		}
		if (quote === '`' && ch === '$' && source[i + 1] === '{') {
			return null;
		}
		value += ch;
	}

	return null;
};

const extractKeys = () => {
	const keys = new Set();
	const callPattern = /(?:\$i18n|i18n)\.t\s*\(\s*/g;

	for (const file of walk(sourceRoot)) {
		const source = fs.readFileSync(file, 'utf8');
		for (const match of source.matchAll(callPattern)) {
			const parsed = readQuotedString(source, match.index + match[0].length);
			if (parsed?.value) {
				keys.add(parsed.value);
			}
		}
	}

	return [...keys].sort((a, b) => a.localeCompare(b));
};

const writeCatalog = (locale, keys) => {
	const file = path.join(localesRoot, locale, 'translation.json');
	const current = fs.existsSync(file) ? readJson(file) : {};
	const next = {};

	for (const key of keys) {
		next[key] = Object.prototype.hasOwnProperty.call(current, key) ? current[key] : '';
	}

	fs.mkdirSync(path.dirname(file), { recursive: true });
	fs.writeFileSync(file, `${JSON.stringify(next, null, '\t')}\n`);
};

const languages = readJson(languagesFile);
const keys = extractKeys();

for (const language of languages) {
	writeCatalog(language.code, keys);
}

console.log(`Updated ${languages.length} locale catalogs with ${keys.length} keys.`);
