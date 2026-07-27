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

const MARKETPLACE = 'johns-os';
const REPO = 'https://github.com/johnoconnor0/johns-os';

const claudeHome = () => process.env.CLAUDE_CONFIG_DIR ?? path.join(homedir(), '.claude');

function readJson(file) {
  try {
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

function run(command, args, { capture = false } = {}) {
  const result = spawnSync(command, args, {
    stdio: capture ? 'pipe' : 'inherit',
    encoding: 'utf8',
    shell: process.platform === 'win32',
  });
  return { code: result.status ?? 1, out: (result.stdout ?? '').trim(), err: (result.stderr ?? '').trim() };
}

function requireClaude() {
  const probe = run('claude', ['--version'], { capture: true });
  if (probe.code !== 0) {
    console.error('The `claude` CLI was not found on PATH.');
    console.error('Install Claude Code first: https://claude.com/claude-code');
    process.exit(127);
  }
}

/** Plugins declared by the marketplace manifest in this package's repo, or the known defaults. */
function marketplacePlugins() {
  const local = path.resolve(import.meta.dirname, '..', '.claude-plugin', 'marketplace.json');
  const manifest = readJson(local);
  if (manifest?.plugins?.length) {
    return manifest.plugins.map((entry) => ({ name: entry.name, version: entry.version, description: entry.description }));
  }
  return [
    { name: 'engineering-lifecycle', description: 'Structured engineering lifecycle skills' },
    { name: 'business-development', description: 'Service definition and outline authoring' },
    { name: 'ai-utilities', description: 'Author, review and audit Claude Code extensions' },
  ];
}

function installedRecords() {
  const data = readJson(path.join(claudeHome(), 'plugins', 'installed_plugins.json'));
  const found = [];
  for (const [key, entries] of Object.entries(data?.plugins ?? {})) {
    if (!key.endsWith(`@${MARKETPLACE}`)) continue;
    for (const entry of entries ?? []) found.push({ key, ...entry });
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
    const installed = new Map(installedRecords().map((r) => [r.key.split('@')[0], r]));
    console.log(`Plugins in the ${MARKETPLACE} marketplace:\n`);
    for (const plugin of plugins) {
      const record = installed.get(plugin.name);
      const state = record ? `installed ${record.version}` : 'not installed';
      console.log(`  ${plugin.name.padEnd(24)} ${state}`);
      if (plugin.description) console.log(`  ${''.padEnd(24)} ${plugin.description}`);
    }
    console.log(`\n${REPO}`);
    return 0;
  },

  install(args) {
    requireClaude();
    const scope = args.includes('--scope') ? args[args.indexOf('--scope') + 1] : 'user';
    const named = args.filter((a) => !a.startsWith('--') && a !== scope);
    const targets = named.length ? named : marketplacePlugins().map((p) => p.name);

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
    const named = args.filter((a) => !a.startsWith('--'));
    console.log(`Refreshing the ${MARKETPLACE} marketplace...`);
    const refreshed = run('claude', ['plugin', 'marketplace', 'update', MARKETPLACE]);
    if (refreshed.code !== 0) return refreshed.code;

    const targets = named.length ? named : installedRecords().map((r) => r.key.split('@')[0]);
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
    console.log('Initializing the Engineering Lifecycle workspace in this directory...');
    const here = args.includes('here') || args.includes('--here');
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
  console.log(readJson(path.join(import.meta.dirname, 'package.json'))?.version ?? 'unknown');
  process.exit(0);
}
if (!Object.hasOwn(commands, command)) {
  console.error(`Unknown command: ${command}\n`);
  usage();
  process.exit(1);
}
process.exit(commands[command](args) ?? 0);
