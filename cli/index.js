#!/usr/bin/env node
/**
 * johns-os: install and manage the johns-os Claude Code plugin marketplace.
 *
 * Dependency-free by design. This runs via `npx` on machines that have nothing
 * set up, so anything it needs to install first is a reason it will not get used.
 *
 * The command that matters most is `doctor`. Plugins execute from a
 * version-pinned copy under ~/.claude/plugins/cache, and for a git-sourced
 * marketplace that copy is fetched from the remote. A checkout can therefore be
 * many commits ahead of what is actually running, with no visible symptom beyond
 * edits appearing to do nothing. `doctor` reports that gap directly.
 */

import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const MARKETPLACE = 'johns-os';
const REPO = 'https://github.com/johnoconnor0/johns-os';
const WINDOWS = process.platform === 'win32';

// `import.meta.dirname` needs Node 20.11. package.json says >=20.11 now, but this
// spelling also works on 18, and being wrong here means every command throws
// TypeError rather than degrading - so prefer the form with no floor at all.
const HERE = path.dirname(fileURLToPath(import.meta.url));

const SCOPES = ['user', 'project', 'local'];
// Plugin directory names, which is what a marketplace entry name has to be.
const PLUGIN_NAME = /^[a-z0-9][a-z0-9-]*$/;

const claudeHome = () => process.env.CLAUDE_CONFIG_DIR ?? path.join(homedir(), '.claude');

function fail(message) {
  console.error(message);
  process.exit(2);
}

function readJson(file) {
  try {
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

// Anything cmd.exe would treat as syntax rather than text. Nothing this CLI
// builds should ever contain one; see the note in `run`.
const SHELL_METACHARACTERS = /[&|<>^"`$;(){}[\]!*?\n\r]/;

function run(command, args, { capture = false } = {}) {
  // `claude` ships as claude.cmd on Windows, and since the CVE-2024-27980 fix
  // Node refuses to spawn a .cmd without a shell - so shell:true is not optional
  // there. What makes that safe is that every dynamic argument reaching this
  // function has already been checked against a strict charset (plugin names
  // against PLUGIN_NAME, scope against SCOPES); the rest are our own literals.
  // This assertion is the backstop for a future caller that forgets.
  const offender = args.find((arg) => SHELL_METACHARACTERS.test(String(arg)));
  if (offender !== undefined) {
    fail(`Refusing to run a command containing shell metacharacters: ${JSON.stringify(offender)}`);
  }
  // spawnSync joins argv into one command line under shell:true and does not
  // quote it, so an argument with a space would arrive as two.
  const spawnArgs = WINDOWS ? args.map((arg) => (/\s/.test(arg) ? `"${arg}"` : arg)) : args;
  const result = spawnSync(command, spawnArgs, {
    stdio: capture ? 'pipe' : 'inherit',
    encoding: 'utf8',
    shell: WINDOWS,
  });
  if (result.error) {
    return { code: 127, out: '', err: result.error.message };
  }
  return { code: result.status ?? 1, out: (result.stdout ?? '').trim(), err: (result.stderr ?? '').trim() };
}

/** Positional plugin names and an optional --scope, with everything else rejected.
 *
 * The old parser filtered `a !== scope`, a value-identity test standing in for a
 * positional one: with the default scope of 'user' a plugin literally named
 * `user` vanished, and `update --scope project` produced a plugin named
 * `project`. Consuming the value by index is what fixes both.
 */
function parseArgs(args, { validateNames = true } = {}) {
  const plugins = [];
  let scope = 'user';
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === '--scope') {
      const value = args[i + 1];
      if (value === undefined) fail(`--scope requires a value: ${SCOPES.join(', ')}`);
      if (!SCOPES.includes(value)) fail(`Invalid --scope ${JSON.stringify(value)}. Expected one of: ${SCOPES.join(', ')}`);
      scope = value;
      i += 1;
      continue;
    }
    if (arg.startsWith('-')) fail(`Unknown option: ${arg}`);
    if (!PLUGIN_NAME.test(arg)) fail(`Invalid plugin name: ${JSON.stringify(arg)}`);
    if (!plugins.includes(arg)) plugins.push(arg);
  }
  if (validateNames && plugins.length) {
    const known = marketplacePlugins().map((p) => p.name);
    const unknown = plugins.filter((name) => !known.includes(name));
    if (unknown.length) {
      fail(`Not in the ${MARKETPLACE} marketplace: ${unknown.join(', ')}\nAvailable: ${known.join(', ')}`);
    }
  }
  return { scope, plugins };
}

function requireClaude() {
  const probe = run('claude', ['--version'], { capture: true });
  if (probe.code !== 0) {
    console.error('The `claude` CLI was not found on PATH.');
    console.error('Install Claude Code first: https://claude.com/claude-code');
    process.exit(127);
  }
}

/** Plugins declared by the marketplace manifest, packaged copy first.
 *
 * `files` in package.json cannot reference a parent directory, so the checkout
 * path below is never present in a published tarball - which meant every
 * published `list` silently used a hardcoded fallback with different wording and
 * no versions. `prepack` now copies the manifest in beside this file, and this
 * prefers that copy. The fallback stays only for the case where both are absent.
 */
function marketplacePlugins() {
  const manifest =
    readJson(path.join(HERE, 'marketplace.json')) ??
    readJson(path.resolve(HERE, '..', '.claude-plugin', 'marketplace.json'));
  const plugins = Array.isArray(manifest?.plugins) ? manifest.plugins : [];
  const declared = plugins
    .filter((entry) => entry && typeof entry.name === 'string')
    .map((entry) => ({ name: entry.name, version: entry.version, description: entry.description }));
  if (declared.length) return declared;
  return [
    { name: 'engineering-lifecycle', description: 'Structured engineering lifecycle skills' },
    { name: 'business-development', description: 'Service definition and outline authoring' },
    { name: 'ai-utilities', description: 'Author, review and audit Claude Code extensions' },
  ];
}

/** The plugin name out of an `<name>@<marketplace>` install key.
 *
 * Split on the LAST `@` rather than the first, so a name containing one is not
 * truncated, and compare the marketplace exactly rather than by suffix.
 */
function splitInstallKey(key) {
  const at = key.lastIndexOf('@');
  if (at <= 0) return null;
  return { name: key.slice(0, at), marketplace: key.slice(at + 1) };
}

function installedRecords() {
  const data = readJson(path.join(claudeHome(), 'plugins', 'installed_plugins.json'));
  // Claude owns this file's shape and may change it. A malformed or
  // different-version file should degrade to "nothing installed" rather than
  // crash `list`, `update` and `doctor` on a TypeError.
  const plugins = data?.plugins;
  if (!plugins || typeof plugins !== 'object' || Array.isArray(plugins)) return [];
  const found = [];
  for (const [key, entries] of Object.entries(plugins)) {
    const split = splitInstallKey(key);
    if (!split || split.marketplace !== MARKETPLACE) continue;
    if (!Array.isArray(entries)) continue;
    for (const entry of entries) {
      if (entry && typeof entry === 'object') found.push({ key, name: split.name, ...entry });
    }
  }
  return found;
}

function marketplaceSource() {
  const known = readJson(path.join(claudeHome(), 'plugins', 'known_marketplaces.json'));
  const entry = (known?.marketplaces ?? known ?? {})[MARKETPLACE];
  return entry?.source ?? null;
}

const commands = {
  list() {
    const plugins = marketplacePlugins();
    const installed = new Map(installedRecords().map((r) => [r.name, r]));
    console.log(`Plugins in the ${MARKETPLACE} marketplace:\n`);
    for (const plugin of plugins) {
      const record = installed.get(plugin.name);
      const state = record ? `installed ${record.version ?? '?'}` : 'not installed';
      // The published package used to lose this column entirely, because the
      // fallback list carries no versions. Printing it is what the CI smoke test
      // asserts on.
      const available = plugin.version ? `  (marketplace ${plugin.version})` : '';
      console.log(`  ${plugin.name.padEnd(24)} ${state}${available}`);
      if (plugin.description) console.log(`  ${''.padEnd(24)} ${plugin.description}`);
    }
    console.log(`\n${REPO}`);
    return 0;
  },

  install(args) {
    requireClaude();
    const { scope, plugins } = parseArgs(args);
    const targets = plugins.length ? plugins : marketplacePlugins().map((p) => p.name);

    if (!marketplaceSource()) {
      console.log(`Adding the ${MARKETPLACE} marketplace...`);
      const added = run('claude', ['plugin', 'marketplace', 'add', REPO]);
      if (added.code !== 0) return added.code;
    }

    let failed = 0;
    for (const name of targets) {
      console.log(`\nInstalling ${name}@${MARKETPLACE}...`);
      const result = run('claude', ['plugin', 'install', `${name}@${MARKETPLACE}`, '--scope', scope]);
      if (result.code !== 0) failed += 1;
    }
    if (!failed) console.log('\nDone. Restart Claude Code to load the plugins.');
    return failed ? 1 : 0;
  },

  update(args) {
    requireClaude();
    // `claude plugin update` takes no scope, but accepting and ignoring --scope
    // here is what stops its value being read as a plugin name.
    const { plugins } = parseArgs(args);
    console.log(`Refreshing the ${MARKETPLACE} marketplace...`);
    const refreshed = run('claude', ['plugin', 'marketplace', 'update', MARKETPLACE]);
    if (refreshed.code !== 0) return refreshed.code;

    const targets = plugins.length ? plugins : installedRecords().map((r) => r.name);
    if (!targets.length) {
      console.log('Nothing installed from this marketplace yet. Run `npx johns-os install`.');
      return 0;
    }
    let failed = 0;
    for (const name of targets) {
      console.log(`\nUpdating ${name}@${MARKETPLACE}...`);
      if (run('claude', ['plugin', 'update', `${name}@${MARKETPLACE}`]).code !== 0) failed += 1;
    }
    if (!failed) console.log('\nDone. Restart Claude Code to apply.');
    return failed ? 1 : 0;
  },

  init(args) {
    requireClaude();
    const unknown = args.filter((arg) => arg !== 'here' && arg !== '--here');
    if (unknown.length) fail(`Unknown argument for init: ${unknown[0]}\nUsage: johns-os init [here]`);
    console.log('Initializing the Engineering Lifecycle workspace in this directory...');
    const here = args.includes('here') || args.includes('--here');
    // `run` quotes this for the Windows shell; without that the space made
    // `here` arrive as a separate argument and the flag was silently dropped.
    return run('claude', ['-p', here ? '/project-init here' : '/project-init']).code;
  },

  doctor() {
    const source = marketplaceSource();
    const records = installedRecords();

    console.log(`marketplace  ${MARKETPLACE}`);
    if (source) {
      const origin = source.url ?? source.path ?? '?';
      console.log(`  source     ${source.source ?? '?'}: ${origin}`);
      if (source.source === 'git') {
        console.log('             fetches from the remote, so local commits must be pushed before they take effect');
      }
    } else {
      console.log('  source     not configured. Run `npx johns-os install`.');
    }

    if (!records.length) {
      console.log('\nNo plugins from this marketplace are installed.');
      return 0;
    }

    let stale = false;
    for (const record of records) {
      const installPath = record.installPath ?? '';
      console.log(`\ninstalled    ${record.key}  (scope: ${record.scope ?? '?'})`);
      console.log(`  version    ${record.version ?? '?'}`);
      console.log(`  path       ${installPath}`);
      if (record.gitCommitSha) console.log(`  commit     ${record.gitCommitSha.slice(0, 7)}`);

      if (installPath && existsSync(installPath)) {
        const manifest = readJson(path.join(installPath, '.claude-plugin', 'plugin.json'));
        const declared = manifest?.version;
        if (declared && record.version && declared !== record.version) {
          console.log(`  MISMATCH   manifest says ${declared}, install record says ${record.version}`);
          stale = true;
        }
        // Regenerable litter inside an install directory is a symptom of hooks
        // running without -B, and is safe to remove.
        const junk = ['.pytest_cache', '.project'].filter((d) => existsSync(path.join(installPath, d)));
        if (junk.length) console.log(`  litter     ${junk.join(', ')}`);
        const locks = path.join(installPath, '.in_use');
        if (existsSync(locks)) {
          const pids = readdirSync(locks);
          if (pids.length) console.log(`  in use     session lock(s) ${pids.join(', ')} (Claude Code's own, leave alone)`);
        }
      } else if (installPath) {
        console.log('  MISSING    install path does not exist; reinstall');
        stale = true;
      }
    }

    console.log('\nA checkout can be many commits ahead of the running copy with no visible symptom.');
    console.log('To resync after pushing:  npx johns-os update');
    return stale ? 1 : 0;
  },
};

function usage() {
  console.log(`johns-os - Claude Code plugin marketplace for engineering, business development and AI utilities

Usage:
  npx johns-os <command> [options]

Commands:
  install [plugin...]   Add the marketplace and install plugins (all by default)
                        --scope user|project|local  (default: user)
  list                  Show marketplace plugins and what is installed
  update [plugin...]    Refresh the marketplace and update installed plugins
  init [here]           Create the Engineering Lifecycle workspace in this repo
  doctor                Report where the running copy came from and whether it is stale

${REPO}`);
}

const [command, ...args] = process.argv.slice(2);
if (!command || command === '--help' || command === '-h') {
  usage();
  process.exit(0);
}
if (command === '--version' || command === '-v') {
  console.log(readJson(path.join(HERE, 'package.json'))?.version ?? 'unknown');
  process.exit(0);
}
if (!Object.hasOwn(commands, command)) {
  console.error(`Unknown command: ${command}\n`);
  usage();
  process.exit(1);
}
process.exit(commands[command](args) ?? 0);
