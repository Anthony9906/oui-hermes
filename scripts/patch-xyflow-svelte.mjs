import fs from 'node:fs';

const keyHandlerPath = new URL(
	'../node_modules/@xyflow/svelte/dist/lib/components/KeyHandler/KeyHandler.svelte',
	import.meta.url
);

if (!fs.existsSync(keyHandlerPath)) {
	process.exit(0);
}

let source = fs.readFileSync(keyHandlerPath, 'utf8');
const importNeedle = "import { isInputDOMNode, isMacOs } from '@xyflow/system';";
const helperNeedle = 'function isInputDOMNode(event) {';

if (!source.includes(importNeedle) || source.includes(helperNeedle)) {
	process.exit(0);
}

source = source.replace(importNeedle, "import { isMacOs } from '@xyflow/system';");

const helper = `const inputTags = ['INPUT', 'SELECT', 'TEXTAREA'];
function isInputDOMNode(event) {
    const target = event.composedPath?.()?.[0] || event.target;
    if (target?.nodeType !== 1) {
        return false;
    }

    return (
        inputTags.includes(target.nodeName) ||
        target.hasAttribute('contenteditable') ||
        !!target.closest('.nokey')
    );
}
`;

source = source.replace('function resetKeysAndSelection() {', `${helper}function resetKeysAndSelection() {`);
fs.writeFileSync(keyHandlerPath, source);
