/**
 * Unit and end-to-end tests for the `johns-os` CLI.
 *
 * ## Why this exists
 *
 * This CLI is the only code every external user runs, it is published to npm,
 * and 0.3.0 shipped with three separate defects that reached users:
 *
 *   1. `parseArgs` filtered `a !== scope` - a value-identity test standing in
 *      for a positional one. With the default scope of `user`, a plugin
 *      literally named `user` vanished; `update --scope project` installed a
 *      plugin named `project`.
 *   2. `splitInstallKey` split on the FIRST `@`, truncating any plugin name
 *      that contained one, and compared the marketplace by suffix.
 *   3. `list` in the *published* package silently used a hardcoded fallback
 *      table with no versions, because `files` in package.json cannot pack a
 *      parent directory and the manifest was only ever read from `../`.
 *
 * None of the three was caught before release because the file had no tests at
 * all - and it could not have had any, because it executed at module scope.
 * The entrypoint guard in `index.js` exists so that these functions can be
 * imported without the import itself parsing argv and calling `process.exit`.
 *
 * ## Why two styles of test
 *
 * Pure functions are exercised in-process. Anything whose contract is an exit
 * code or a stream is spawned as a subprocess, because that is the only way to
 * observe what a user observes - the publish smoke test proved that a check
 * which merely asserts "non-zero" cannot tell a rejected argument (2) from a
 * missing `claude` binary (127).
 *
 * ## Why the fixtures build a whole fake package tree
 *
 * `marketplacePlugins()` resolves both manifest paths relative to the directory
 * `index.js` lives in. That resolution IS defect 3, so it cannot be stubbed out
 * and still be tested. Each manifest-precedence test therefore copies
 * `index.js` into a temp tree with the manifests it wants present or absent,
 * and runs the copy. Nothing is written inside the repository.
 *
 * ## Why the `claude` stub records its arguments
 *
 * `install`, `update` and `init` produce exactly one observable thing: the argv
 * they hand to `claude`. An earlier version of this file stubbed `claude` with
 * a script that reported an exit code and threw its arguments away, so nothing
 * here looked at that argv at all - a dropped `--scope`, a missing plugin name,
 * or a `marketplace add` pointing at someone else's repository would all have
 * left the suite green. `claudeStub` now logs each invocation and the
 * "argv handed to claude" section asserts on it.
 */

import { spawnSync } from 'node:child_process';
import {
  chmodSync,
  copyFileSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { after, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CLI_ENTRY = path.join(HERE, '..', 'index.js');

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const scratch = [];

/** A temp directory removed when the file finishes. Never inside the repo. */
function tempDir() {
  const dir = mkdtempSync(path.join(tmpdir(), 'johns-os-cli-'));
  scratch.push(dir);
  return dir;
}

after(() => {
  for (const dir of scratch) {
    // maxRetries: Windows holds handles briefly after a child exits, and a
    // failed cleanup must not be reported as a failed test.
    rmSync(dir, { recursive: true, force: true, maxRetries: 5 });
  }
});

/** Import the CLI in a child process and report what happened.
 *
 * Run at module scope, deliberately BEFORE this file imports the CLI itself.
 */
function probeInertness() {
  const prove = path.join(tempDir(), 'prove-inert.mjs');
  writeFileSync(
    prove,
    `const mod = await import(${JSON.stringify(pathToFileURL(CLI_ENTRY).href)});\n` +
      `process.stdout.write(typeof mod.parseArgs);\n`,
  );
  // `list` as argv[2]: a dispatch that still runs would print the plugin table.
  const result = spawnSync(process.execPath, [prove, 'list'], {
    encoding: 'utf8',
    env: { ...process.env, CLAUDE_CONFIG_DIR: tempDir() },
  });
  return { status: result.status, stdout: result.stdout ?? '', stderr: result.stderr ?? '' };
}

/* Why this check is a module-scope throw and not a test.
 *
 * If the entrypoint guard in index.js regresses, importing the CLI executes the
 * dispatch and calls `process.exit`. A `node --test` child that exits 0 during
 * module evaluation is reported as a PASSING FILE CONTAINING ONE TEST: the
 * suite below silently stops running, the summary reads `pass 1 / fail 0`, and
 * CI stays green while nothing is verified at all. That is measured, not
 * theorised - removing the guard produces exactly that output.
 *
 * No assertion inside a test can defend against it, because no test would run.
 * Throwing here makes it a load failure, which the runner does report.
 */
const INERTNESS = probeInertness();
if (INERTNESS.status !== 0 || INERTNESS.stdout !== 'function') {
  throw new Error(
    'cli/index.js is not inert on import - the entrypoint guard has regressed, and every test ' +
      `in this file would be silently skipped. Child exited ${INERTNESS.status} and wrote ` +
      `${JSON.stringify(INERTNESS.stdout.slice(0, 200))} to stdout.`,
  );
}

const {
  installedRecords,
  marketplacePlugins,
  marketplaceSource,
  parseArgs,
  readJson,
  run,
  splitInstallKey,
  PLUGIN_NAME,
  SCOPES,
  SHELL_METACHARACTERS,
} = await import('../index.js');

/** The marketplace git URL the CLI hands to `claude plugin marketplace add`.
 *
 * Duplicated from index.js rather than imported, deliberately: this is the
 * address a user's Claude Code is pointed at, so a test that read the same
 * constant the code reads would agree with any typo the code contained.
 */
const REPO_URL = 'https://github.com/johnoconnor0/johns-os';

/** Point claudeHome() at a fixture directory for the duration of `fn`.
 *
 * `CLAUDE_CONFIG_DIR` is read on every call rather than captured at import, so
 * setting it around the call is enough - and restoring it afterwards is what
 * keeps one test's fixture out of the next test's answers.
 */
function withConfigDir(dir, fn) {
  const previous = process.env.CLAUDE_CONFIG_DIR;
  process.env.CLAUDE_CONFIG_DIR = dir;
  try {
    return fn();
  } finally {
    if (previous === undefined) delete process.env.CLAUDE_CONFIG_DIR;
    else process.env.CLAUDE_CONFIG_DIR = previous;
  }
}

/** Run `fn` with `process.exit` and `console.error` intercepted.
 *
 * `fail()` writes to stderr and calls `process.exit(2)`. In-process that would
 * kill the test runner mid-file, so exit is swapped for a throw carrying the
 * code. The sentinel is per-call so an unrelated throw from the function under
 * test still propagates rather than being mistaken for a clean rejection.
 */
function captureFail(fn) {
  const realExit = process.exit;
  const realError = console.error;
  const sentinel = Symbol('process.exit');
  const stderr = [];
  let code;
  process.exit = (value) => {
    code = value;
    const stop = new Error('process.exit');
    stop[sentinel] = true;
    throw stop;
  };
  console.error = (...parts) => stderr.push(parts.join(' '));
  try {
    const value = fn();
    return { exited: false, code: undefined, value, stderr: stderr.join('\n') };
  } catch (error) {
    if (error?.[sentinel]) return { exited: true, code, value: undefined, stderr: stderr.join('\n') };
    throw error;
  } finally {
    process.exit = realExit;
    console.error = realError;
  }
}

/** parseArgs on the success path, asserting it did not bail out.
 *
 * `validateNames: false` because name validation reads the real marketplace
 * manifest; these cases are about positional parsing, not membership.
 */
function parse(args) {
  const result = captureFail(() => parseArgs(args, { validateNames: false }));
  assert.equal(result.exited, false, `parseArgs(${JSON.stringify(args)}) exited: ${result.stderr}`);
  return result.value;
}

/** parseArgs on the rejection path, asserting it bailed out with exit 2. */
function parseRejects(args, options = { validateNames: false }) {
  const result = captureFail(() => parseArgs(args, options));
  assert.equal(result.exited, true, `parseArgs(${JSON.stringify(args)}) was accepted, expected rejection`);
  assert.equal(result.code, 2);
  return result.stderr;
}

/** A temp copy of the package, with the two manifests present or absent.
 *
 * Returns the path to the copied `index.js`.
 */
function fakePackage({ packaged, checkout, version = '9.9.9-fixture' } = {}) {
  const root = tempDir();
  const cli = path.join(root, 'cli');
  mkdirSync(cli, { recursive: true });
  copyFileSync(CLI_ENTRY, path.join(cli, 'index.js'));
  // `--version` reads the package.json sitting beside index.js; a deliberately
  // impossible version proves it read this one and not the repository's.
  writeFileSync(
    path.join(cli, 'package.json'),
    JSON.stringify({ name: 'johns-os', version, type: 'module', bin: { 'johns-os': 'index.js' } }),
  );
  if (packaged) writeFileSync(path.join(cli, 'marketplace.json'), JSON.stringify(packaged));
  if (checkout) {
    const parent = path.join(root, '.claude-plugin');
    mkdirSync(parent, { recursive: true });
    writeFileSync(path.join(parent, 'marketplace.json'), JSON.stringify(checkout));
  }
  return path.join(cli, 'index.js');
}

/** A `CLAUDE_CONFIG_DIR` seeded with the given plugin files.
 *
 * Every command that reads install state goes through `CLAUDE_CONFIG_DIR`, so
 * pointing it at a temp directory is what keeps these tests off the developer's
 * real `~/.claude` - both for reading and, more importantly, for never writing.
 */
function fakeConfigDir({ installed, marketplaces } = {}) {
  const dir = tempDir();
  const plugins = path.join(dir, 'plugins');
  mkdirSync(plugins, { recursive: true });
  if (installed !== undefined) {
    const body = typeof installed === 'string' ? installed : JSON.stringify(installed);
    writeFileSync(path.join(plugins, 'installed_plugins.json'), body);
  }
  if (marketplaces !== undefined) {
    const body = typeof marketplaces === 'string' ? marketplaces : JSON.stringify(marketplaces);
    writeFileSync(path.join(plugins, 'known_marketplaces.json'), body);
  }
  return dir;
}

/** A stub `claude` executable that RECORDS the argv it was handed.
 *
 * `install`, `update` and `init` all probe for `claude`, so any test of those
 * commands is partly answering "is claude on this machine?" unless a stub is
 * supplied. With one, a real `claude` is never invoked and the result is the
 * same on a developer's machine and on a bare runner.
 *
 * Recording argv is the point. The previous stub discarded its arguments and
 * only reported an exit code, so every assertion in this file was about exit
 * codes and stdout - which means `install` could have run
 * `claude plugin install --scope` with the name missing, or dropped `--scope`
 * entirely, or pointed `marketplace add` at the wrong URL, and the whole suite
 * would still have been green. The argv is the entire product of these three
 * commands; nothing else about them is observable.
 *
 * The recorder is a Node script rather than shell text so the log holds a real
 * argv array, one JSON line per invocation. On Windows that also puts the
 * assertion on the far side of cmd.exe's re-parse, which is the layer the
 * `init here` quoting defect lived in: `run` quotes an argument containing a
 * space, cmd.exe unquotes it, and only a stub that reports what it actually
 * received can tell one argument from two.
 *
 * `status: 1` makes every call fail, including the `--version` probe, which is
 * what `requireClaude` sees when the binary is absent. A stub that fails is
 * used rather than an emptied PATH because emptying PATH also takes cmd.exe
 * away from the Windows `shell: true` spawn, and would test the harness instead
 * of the CLI. `probeStatus` splits the two apart, for the case that matters
 * most in practice: claude is installed and working, and the subcommand fails.
 *
 * Returns `{ dir, calls() }` - `dir` for `pathPrefix`, `calls()` for the argv
 * arrays in invocation order.
 */
function claudeStub({ status = 0, probeStatus = status } = {}) {
  const dir = tempDir();
  const log = path.join(dir, 'argv.jsonl');
  const recorder = path.join(dir, 'claude-stub.mjs');
  writeFileSync(
    recorder,
    `import { appendFileSync } from 'node:fs';\n` +
      `const argv = process.argv.slice(2);\n` +
      `appendFileSync(${JSON.stringify(log)}, JSON.stringify(argv) + '\\n');\n` +
      `process.stdout.write('1.0.0-stub\\n');\n` +
      `const probe = argv.length === 1 && argv[0] === '--version';\n` +
      `process.exit(probe ? ${probeStatus} : ${status});\n`,
  );
  if (process.platform === 'win32') {
    // .cmd, because that is the form Claude Code ships on Windows and the form
    // cmd.exe will find on PATH. `exit /b %ERRORLEVEL%` on its own line, so the
    // stub's exit code is the recorder's rather than cmd's own.
    writeFileSync(
      path.join(dir, 'claude.cmd'),
      `@echo off\r\n"${process.execPath}" "${recorder}" %*\r\nexit /b %ERRORLEVEL%\r\n`,
    );
  } else {
    const file = path.join(dir, 'claude');
    writeFileSync(
      file,
      `#!/bin/sh\nexec ${JSON.stringify(process.execPath)} ${JSON.stringify(recorder)} "$@"\n`,
    );
    chmodSync(file, 0o755);
  }
  return {
    dir,
    /** Every argv the stub was handed, in order. Empty if it was never run. */
    calls() {
      let text;
      try {
        text = readFileSync(log, 'utf8');
      } catch {
        return [];
      }
      return text
        .split('\n')
        .filter((line) => line.trim())
        .map((line) => JSON.parse(line));
    },
  };
}

/** Spawn the CLI the way a user runs it, and report exit code and streams. */
function runCli(entry, args, { configDir, pathPrefix } = {}) {
  const env = { ...process.env, CLAUDE_CONFIG_DIR: configDir ?? tempDir() };
  if (pathPrefix) {
    // Windows spells it `Path`; spreading process.env preserves that spelling,
    // and adding a second `PATH` key would leave the child picking either one.
    const key = Object.keys(env).find((name) => name.toUpperCase() === 'PATH') ?? 'PATH';
    env[key] = `${pathPrefix}${path.delimiter}${env[key] ?? ''}`;
  }
  const result = spawnSync(process.execPath, [entry, ...args], { encoding: 'utf8', env });
  assert.equal(result.error, undefined, `spawn failed: ${result.error?.message}`);
  return { code: result.status, out: result.stdout ?? '', err: result.stderr ?? '' };
}

// ---------------------------------------------------------------------------
// parseArgs
// ---------------------------------------------------------------------------

describe('parseArgs', () => {
  it('defaults to the user scope with no plugins', () => {
    assert.deepEqual(parse([]), { scope: 'user', plugins: [] });
  });

  it('consumes the --scope value by index instead of leaving it as a plugin', () => {
    // Defect 1, half one: the old parser dropped arguments equal to the scope
    // value, so `--scope project` left `project` in the list and the CLI tried
    // to install a plugin by that name. The value must vanish because it sat at
    // i+1, not because of what it says.
    assert.deepEqual(parse(['--scope', 'project']), { scope: 'project', plugins: [] });
    assert.deepEqual(parse(['--scope', 'local', 'ai-utilities']), {
      scope: 'local',
      plugins: ['ai-utilities'],
    });
  });

  it('keeps a plugin literally named after a scope', () => {
    // Defect 1, half two: with the default scope of `user`, filtering on value
    // identity silently deleted a plugin named `user` from the install list.
    // The command reported success having installed nothing.
    assert.deepEqual(parse(['user']), { scope: 'user', plugins: ['user'] });
    assert.deepEqual(parse(['--scope', 'local', 'user']), { scope: 'local', plugins: ['user'] });
    // The pathological case the old parser could not express at all: the scope
    // value and a positional plugin sharing a name.
    assert.deepEqual(parse(['--scope', 'project', 'project']), {
      scope: 'project',
      plugins: ['project'],
    });
  });

  it('rejects a trailing --scope rather than reading the string "undefined"', () => {
    // `args[i + 1]` is undefined here. Anything that stringified it before
    // checking would set scope to "undefined" and hand that to
    // `claude plugin install --scope undefined`.
    const stderr = parseRejects(['--scope']);
    assert.match(stderr, /--scope requires a value/);
    // The specific wrong answer this guards: `undefined` reaching the enum
    // check as a string, passing nothing, and being reported as the scope.
    assert.doesNotMatch(stderr, /undefined/);
    // Same when the flag trails a positional argument rather than standing alone.
    assert.match(parseRejects(['ai-utilities', '--scope']), /--scope requires a value/);
  });

  it('enum-checks the scope instead of passing it through', () => {
    for (const bad of ['bogus', 'User', 'global', '']) {
      const stderr = parseRejects(['--scope', bad]);
      assert.match(stderr, /Invalid --scope/);
    }
    for (const good of SCOPES) {
      assert.equal(parse(['--scope', good]).scope, good);
    }
  });

  it('rejects names that are not plugin directory names', () => {
    // A marketplace entry name has to be a directory name, and this value is
    // interpolated into a command line. Spaces, unicode, uppercase, underscores,
    // path separators and empty strings all have to be refused here rather than
    // downstream.
    //
    // Every case asserts the MESSAGE, not merely that something was rejected.
    // The previous version of this test looped `parseRejects(bad)` with no
    // message check and listed `-leading` among the bad names - which is not a
    // name rejection at all (see below). A bare "it exited 2" passes for any
    // reason at all, including the right rejection for the wrong argument.
    for (const bad of ['my plugin', 'café', 'Engineering', 'plugin/../etc', '', 'a_b', 'x.y']) {
      assert.match(
        parseRejects([bad]),
        /Invalid plugin name/,
        `${JSON.stringify(bad)} was not rejected as a name`,
      );
    }
    // The rejected value is echoed so the user can see which argument was bad;
    // asserted in-process to keep the child-process encoding boundary out of it.
    assert.match(parseRejects(['café']), /Invalid plugin name: "café"/);
  });

  it('rejects unknown options as options rather than as plugin names', () => {
    // Order of the two guards in parseArgs, pinned. `arg.startsWith('-')` is
    // tested first, so `-leading` never reaches PLUGIN_NAME - and a user who
    // typed `-scope` with one dash needs to be told they wrote an option, not
    // that they named a plugin badly. This test exists because the name-shape
    // test above used to claim `-leading` as one of its own cases and, asserting
    // only "it exited", could not have noticed which guard answered.
    for (const bad of ['--nonsense', '-leading', '-x', '--', '--scope=user', '-']) {
      const stderr = parseRejects([bad]);
      assert.equal(stderr, `Unknown option: ${bad}`);
      assert.doesNotMatch(stderr, /Invalid plugin name/);
    }
  });

  it('accepts the name shapes the marketplace actually uses', () => {
    assert.deepEqual(parse(['engineering-lifecycle']).plugins, ['engineering-lifecycle']);
    assert.deepEqual(parse(['a1']).plugins, ['a1']);
    assert.equal(PLUGIN_NAME.test('engineering-lifecycle'), true);
  });

  it('deduplicates repeated plugin names', () => {
    // `install foo foo` would otherwise run the install twice and double-count
    // any failure in the exit status.
    assert.deepEqual(parse(['ai-utilities', 'ai-utilities']).plugins, ['ai-utilities']);
  });

  it('rejects names absent from the marketplace when validation is on', () => {
    // Asserted on the prefix only: the list of available plugins is manifest
    // content and churns with every release.
    const stderr = parseRejects(['zzz-not-a-real-plugin'], {});
    assert.match(stderr, /Not in the johns-os marketplace/);
  });
});

// ---------------------------------------------------------------------------
// splitInstallKey
// ---------------------------------------------------------------------------

describe('splitInstallKey', () => {
  it('splits on the last @ so a name containing one is not truncated', () => {
    // Defect 2: splitting on the first `@` turned `@scope/pkg@johns-os` into a
    // plugin named `@scope`, which then matched nothing in `list`, `update` or
    // `doctor` - the plugin appeared uninstalled while plainly being installed.
    assert.deepEqual(splitInstallKey('engineering-lifecycle@johns-os'), {
      name: 'engineering-lifecycle',
      marketplace: 'johns-os',
    });
    assert.deepEqual(splitInstallKey('@scope/pkg@johns-os'), {
      name: '@scope/pkg',
      marketplace: 'johns-os',
    });
    assert.deepEqual(splitInstallKey('a@b@c@johns-os'), { name: 'a@b@c', marketplace: 'johns-os' });
  });

  it('returns null for keys with no name part', () => {
    // `at <= 0` rather than `at < 0`: a leading `@` would otherwise yield an
    // empty name that compares equal to nothing and reads as a valid record.
    assert.equal(splitInstallKey('@johns-os'), null);
    assert.equal(splitInstallKey('no-at-sign'), null);
    assert.equal(splitInstallKey(''), null);
  });
});

// ---------------------------------------------------------------------------
// installedRecords
// ---------------------------------------------------------------------------

describe('installedRecords', () => {
  it('matches the marketplace exactly rather than by suffix', () => {
    // Defect 2's other half. A suffix test would have claimed
    // `other@not-johns-os` and `other@x-johns-os` as ours, and `update` would
    // then have run `claude plugin update other@johns-os` against a plugin that
    // came from somewhere else entirely.
    const dir = fakeConfigDir({
      installed: {
        plugins: {
          'ai-utilities@johns-os': [{ version: '0.2.0', scope: 'user' }],
          'other@not-johns-os': [{ version: '1.0.0' }],
          'other@x-johns-os': [{ version: '1.0.0' }],
        },
      },
    });
    const names = withConfigDir(dir, () => installedRecords().map((r) => r.name));
    assert.deepEqual(names, ['ai-utilities']);
  });

  it('degrades to "nothing installed" on a file shape it does not own', () => {
    // Claude Code owns installed_plugins.json and may change its shape. Every
    // one of these used to be a TypeError that took down `list`, `update` and
    // `doctor` together - the three commands a user reaches for precisely when
    // something is already wrong.
    for (const installed of ['{not json', '', '[]', { plugins: [] }, { plugins: null }, {}]) {
      const dir = fakeConfigDir({ installed });
      assert.deepEqual(
        withConfigDir(dir, () => installedRecords()),
        [],
        `shape ${JSON.stringify(installed)} should read as nothing installed`,
      );
    }
  });

  it('does not let a field inside the record override the parsed install key', () => {
    // The derived fields were spread FIRST and the raw record over the top, so
    // a `name` or `key` in the file silently replaced the values taken from
    // `<name>@<marketplace>` - the values every other check in this file
    // assumes are authoritative. `update` builds its command line from
    // `record.name`, so a record that names something else is a
    // `claude plugin update <that>@johns-os` the user never asked for, and
    // `doctor` would print a key that does not exist.
    //
    // Claude Code owns this file's shape, so a future version adding a `name`
    // field of its own is not far-fetched; the parse has to win regardless.
    const dir = fakeConfigDir({
      installed: {
        plugins: {
          'ai-utilities@johns-os': [
            { version: '0.2.0', scope: 'user', name: 'something-else', key: 'something-else@elsewhere' },
          ],
        },
      },
    });
    const records = withConfigDir(dir, () => installedRecords());
    assert.equal(records.length, 1);
    assert.equal(records[0].name, 'ai-utilities');
    assert.equal(records[0].key, 'ai-utilities@johns-os');
    // Everything the record legitimately carries still comes through.
    assert.equal(records[0].version, '0.2.0');
    assert.equal(records[0].scope, 'user');
  });

  it('skips non-object entries inside an otherwise valid record list', () => {
    const dir = fakeConfigDir({
      installed: { plugins: { 'ai-utilities@johns-os': [null, 'string', { version: '0.2.0' }] } },
    });
    const records = withConfigDir(dir, () => installedRecords());
    assert.equal(records.length, 1);
    assert.equal(records[0].version, '0.2.0');
    assert.equal(records[0].name, 'ai-utilities');
  });
});

// ---------------------------------------------------------------------------
// marketplaceSource
// ---------------------------------------------------------------------------

describe('marketplaceSource', () => {
  const SOURCE = { source: 'git', url: 'https://github.com/johnoconnor0/johns-os' };

  it('reads the nested shape Claude Code writes today', () => {
    // `known.marketplaces[name]`. This is the shape on disk in ~/.claude, and
    // it is what `install` branches on to decide whether to run
    // `claude plugin marketplace add` - so reading it wrong means either
    // re-adding the marketplace on every install or, worse, never adding it.
    const dir = fakeConfigDir({ marketplaces: { marketplaces: { 'johns-os': { source: SOURCE } } } });
    assert.deepEqual(withConfigDir(dir, () => marketplaceSource()), SOURCE);
  });

  it('reads the flat shape the coercion also accepts', () => {
    // `known?.marketplaces ?? known ?? {}` supports a second shape with the
    // entries at the top level. Neither half of that expression was covered, so
    // either could have been deleted as dead code with the suite still green -
    // and the flat half is the one that keeps a file written by an older or
    // newer Claude Code from reading as "marketplace not configured".
    const dir = fakeConfigDir({ marketplaces: { 'johns-os': { source: SOURCE } } });
    assert.deepEqual(withConfigDir(dir, () => marketplaceSource()), SOURCE);
  });

  it('prefers the nested shape when a file somehow carries both', () => {
    // Pins the direction of the `??`. If it flipped, a stale top-level entry
    // would shadow the current nested one.
    const nested = { source: 'git', url: 'https://example.invalid/nested' };
    const dir = fakeConfigDir({
      marketplaces: {
        marketplaces: { 'johns-os': { source: nested } },
        'johns-os': { source: SOURCE },
      },
    });
    assert.deepEqual(withConfigDir(dir, () => marketplaceSource()), nested);
  });

  it('returns null rather than throwing for every shape that names nothing', () => {
    // `install` calls this before anything else and `doctor` prints from it, so
    // a throw here takes out both. `[]` and `"text"` are the ones that would
    // have: indexing them is fine, but only because of the `?.` chain.
    for (const marketplaces of [
      undefined, // no file at all
      '{not json',
      {},
      { marketplaces: {} },
      { marketplaces: { 'someone-else': { source: SOURCE } } },
      { 'johns-os': {} }, // present but with no source field
      [],
      '"a string"',
    ]) {
      const dir = fakeConfigDir({ marketplaces });
      assert.equal(
        withConfigDir(dir, () => marketplaceSource()),
        null,
        `shape ${JSON.stringify(marketplaces)} should read as not configured`,
      );
    }
  });
});

// ---------------------------------------------------------------------------
// readJson
// ---------------------------------------------------------------------------

describe('readJson', () => {
  it('returns null instead of throwing on unreadable or malformed input', () => {
    // Every caller uses `?? fallback` or optional chaining on the result, so a
    // throw here does not degrade a single command - it crashes it.
    const dir = tempDir();
    const malformed = path.join(dir, 'malformed.json');
    writeFileSync(malformed, '{"plugins": [');
    assert.equal(readJson(malformed), null);

    const empty = path.join(dir, 'empty.json');
    writeFileSync(empty, '');
    assert.equal(readJson(empty), null);

    assert.equal(readJson(path.join(dir, 'does-not-exist.json')), null);
    // A directory, which fails at read rather than at parse.
    assert.equal(readJson(dir), null);
  });

  it('parses well-formed JSON', () => {
    const file = path.join(tempDir(), 'ok.json');
    writeFileSync(file, JSON.stringify({ plugins: [{ name: 'x' }] }));
    assert.deepEqual(readJson(file), { plugins: [{ name: 'x' }] });
  });
});

// ---------------------------------------------------------------------------
// run: shell metacharacter rejection
// ---------------------------------------------------------------------------

describe('run', () => {
  it('refuses arguments containing shell metacharacters', () => {
    // `run` passes shell:true on Windows because Node will not spawn a .cmd
    // without it, which makes every argument shell syntax. The charset checks
    // upstream are the real defence; this assertion is the backstop for a
    // future caller that forgets one, so it has to actually bite.
    //
    // The command name is deliberately nonexistent: if the guard ever stopped
    // firing, the call would fall through to a spawn that fails rather than one
    // that runs something.
    const offenders = ['a&b', 'a|b', 'a;b', 'a`b', 'a$(b)', 'a>b', 'a<b', 'a\nb', 'a\rb', 'a!b'];
    for (const offender of offenders) {
      const result = captureFail(() => run('definitely-not-a-real-command', [offender]));
      assert.equal(result.exited, true, `${JSON.stringify(offender)} was not refused`);
      assert.equal(result.code, 2);
      assert.match(result.stderr, /Refusing to run a command containing shell metacharacters/);
      // The offending argument is named, so the message identifies which one.
      assert.ok(
        result.stderr.includes(JSON.stringify(offender)),
        `message did not name ${JSON.stringify(offender)}: ${result.stderr}`,
      );
    }
  });

  it('refuses an offender anywhere in the argument list', () => {
    // The check is a `find` over every argument, not just the last one.
    const result = captureFail(() =>
      run('definitely-not-a-real-command', ['plugin', 'install', 'x; rm -rf /', '--scope', 'user']),
    );
    assert.equal(result.exited, true);
    assert.match(result.stderr, /rm -rf/);
  });

  it('flags every character in the published set, not a convenient subset', () => {
    // This list is the whole character class in index.js, spelled out. The
    // previous version named nine of the twenty and was titled as though it
    // covered all of them: `^ " { } [ ] * ?` were never asserted, so any of
    // them could have been dropped from the regex - `^` is cmd.exe's escape
    // character and `*`/`?` are its globs, which is precisely the half that
    // matters on the platform that has to use `shell: true`.
    const offenders = [
      '&', '|', '<', '>', '^', '"', '`', '$', ';', '(',
      ')', '{', '}', '[', ']', '!', '*', '?', '\n', '\r',
    ];
    assert.equal(offenders.length, 20, 'update this list when the character class changes');
    for (const offender of offenders) {
      assert.equal(SHELL_METACHARACTERS.test(offender), true, `${JSON.stringify(offender)} unguarded`);
      // And embedded, not only as the whole string - the guard is a search.
      assert.equal(SHELL_METACHARACTERS.test(`ok${offender}ok`), true);
    }
  });

  it('passes the arguments this CLI actually builds', () => {
    // The other half, and the one that makes the guard usable rather than just
    // safe: every value the CLI hands to `run` has to survive it. A widened
    // class that rejected `@` or `/` or `:` or `\` would turn a normal install
    // into "Refusing to run a command containing shell metacharacters", which
    // is a total outage of install, update and init with no workaround.
    const real = [
      'plugin',
      'install',
      'engineering-lifecycle@johns-os',
      '--scope',
      'user',
      '-p',
      '/project-init',
      '/project-init here', // one argument, spaces and all
      '--version',
      REPO_URL, // has `:` and `//`
      'a1',
      // A Windows install path, which is what `doctor` reads and a future
      // caller might well pass through. Backslashes must not read as syntax.
      'C:\\Users\\john\\.claude\\plugins\\cache\\johns-os',
    ];
    for (const safe of real) {
      assert.equal(SHELL_METACHARACTERS.test(safe), false, `${JSON.stringify(safe)} wrongly flagged`);
    }
  });

  it('runs a clean command and captures its output', () => {
    const result = captureFail(() => run('node', ['--version'], { capture: true }));
    assert.equal(result.exited, false, `clean arguments were refused: ${result.stderr}`);
    assert.equal(result.value.code, 0);
    assert.match(result.value.out, /^v\d+\./);
  });

  it('delivers a space-containing argument as one argument', (t) => {
    // Under shell:true, spawnSync joins argv into a single command line without
    // quoting, so `init here` arrived as two arguments and the flag was
    // silently dropped - `/project-init here` ran as plain `/project-init`.
    const dir = tempDir();
    const script = path.join(dir, 'echo-argv.js');
    if (SHELL_METACHARACTERS.test(script)) {
      t.skip(`temp path contains shell metacharacters: ${script}`);
      return;
    }
    writeFileSync(script, 'process.stdout.write(String(process.argv[2]));\n');
    const result = captureFail(() => run('node', [script, 'project-init here'], { capture: true }));
    assert.equal(result.exited, false, `refused: ${result.stderr}`);
    assert.equal(result.value.code, 0);
    assert.equal(result.value.out, 'project-init here');
  });

  it('reports a missing executable as a code rather than throwing', () => {
    // `requireClaude` branches on `.code`, so a spawn that never started has to
    // arrive as a non-zero code rather than an exception or a zero.
    //
    // The two platforms reach that by different routes and the assertion has to
    // say which, because "non-zero" is also what a command that DID start and
    // failed returns - so a bare notEqual(code, 0) passes whether or not `run`
    // still maps `result.error` to a code at all. That mapping is the only
    // thing being tested here, and on POSIX it is the only thing that happens.
    const result = captureFail(() => run('definitely-not-a-real-command', ['--version'], { capture: true }));
    assert.equal(result.exited, false, 'a clean argument list was refused');
    if (process.platform === 'win32') {
      // shell:true is mandatory here (see `run`), so cmd.exe starts, fails to
      // find the name, and exits 1. spawnSync itself never errors, which means
      // the `result.error` branch is unreachable on Windows - the POSIX arm
      // below is the only place it is exercised.
      assert.equal(result.value.code, 1);
      assert.match(result.value.err, /not recognized as an internal or external command/);
    } else {
      // No shell, so nothing starts: ENOENT lands in `result.error` and `run`
      // has to turn it into 127 rather than letting it surface as `code: null`,
      // which `?? 1` would quietly have made a 1.
      assert.equal(result.value.code, 127);
      assert.match(result.value.err, /ENOENT/);
    }
  });
});

// ---------------------------------------------------------------------------
// marketplacePlugins and manifest precedence
// ---------------------------------------------------------------------------

describe('marketplacePlugins', () => {
  const PACKAGED = {
    plugins: [{ name: 'packaged-fixture', version: '1.2.3', description: 'from the packaged manifest' }],
  };
  const CHECKOUT = {
    plugins: [{ name: 'checkout-fixture', version: '4.5.6', description: 'from the checkout manifest' }],
  };

  it('reads this repository\'s own manifest, not the hardcoded fallback', () => {
    // The version this replaced asserted `plugins.length > 0` and that each
    // name was a string. The hardcoded fallback satisfies both, unconditionally
    // - so the test passed whether or not either manifest path resolved, which
    // is to say it could not fail. Defect 3 was exactly "the fallback is being
    // used and nobody noticed", and that assertion was blind to it.
    //
    // Read the manifest out of the checkout independently and demand the whole
    // projection back. This runs in-process, so HERE is cli/ and the resolution
    // under test is the `../.claude-plugin/` one. (If a prepack has been run
    // the packaged copy wins instead, but it is a byte copy of this same file,
    // so the expectation holds either way.)
    const manifestPath = path.resolve(HERE, '..', '..', '.claude-plugin', 'marketplace.json');
    const manifest = readJson(manifestPath);
    assert.ok(Array.isArray(manifest?.plugins), `no plugins array in ${manifestPath}`);
    const expected = manifest.plugins
      .filter((entry) => entry && typeof entry.name === 'string')
      .map((entry) => ({ name: entry.name, version: entry.version, description: entry.description }));
    assert.deepEqual(marketplacePlugins(), expected);

    // And the symptom that made defect 3 detectable in the first place: real
    // manifest entries carry versions, fallback entries do not. deepEqual above
    // already covers it, but stated separately because this is the property the
    // published smoke test looks for.
    assert.ok(expected.length > 0, 'the repository manifest declares no plugins');
    for (const plugin of expected) {
      assert.equal(typeof plugin.version, 'string', `${plugin.name} declares no version`);
    }
  });

  it('prefers the packaged manifest over the parent-directory checkout copy', () => {
    // Defect 3. `files` in package.json cannot reference `../`, so the checkout
    // path is never present in a published tarball; prepack copies the manifest
    // in beside index.js and this ordering is what makes the published package
    // read it. With both present the packaged copy must win, because that is
    // the one npm shipped.
    const entry = fakePackage({ packaged: PACKAGED, checkout: CHECKOUT });
    const { code, out } = runCli(entry, ['list']);
    assert.equal(code, 0);
    assert.match(out, /packaged-fixture/);
    assert.doesNotMatch(out, /checkout-fixture/);
    assert.match(out, /\(marketplace 1\.2\.3\)/);
  });

  it('falls back to the parent checkout copy when the packaged one is absent', () => {
    // The development case: a git checkout with no prepack run.
    const entry = fakePackage({ checkout: CHECKOUT });
    const { code, out } = runCli(entry, ['list']);
    assert.equal(code, 0);
    assert.match(out, /checkout-fixture/);
    assert.match(out, /\(marketplace 4\.5\.6\)/);
  });

  it('falls back to a versionless hardcoded table when no manifest exists', () => {
    // This is the state 0.3.0 shipped in, and the absence of the version column
    // is exactly the symptom that made it detectable. Asserting the column is
    // gone here is what stops the fallback being mistaken for a working list.
    const entry = fakePackage({});
    const { code, out } = runCli(entry, ['list']);
    assert.equal(code, 0);
    for (const name of ['engineering-lifecycle', 'business-development', 'ai-utilities']) {
      assert.match(out, new RegExp(name));
    }
    assert.doesNotMatch(out, /\(marketplace /);
  });

  it('ignores manifest entries with no usable name', () => {
    const entry = fakePackage({
      packaged: {
        plugins: [null, 'a-string', { version: '1.0.0' }, { name: 42 }, { name: 'packaged-fixture' }],
      },
    });
    const { code, out } = runCli(entry, ['list']);
    assert.equal(code, 0);
    assert.match(out, /packaged-fixture/);
    // The junk entries must not have tipped it into the hardcoded fallback.
    assert.doesNotMatch(out, /business-development/);
  });

  it('falls back when the packaged manifest is malformed', () => {
    // A truncated file from an interrupted prepack must not crash `list`.
    const root = tempDir();
    const cli = path.join(root, 'cli');
    mkdirSync(cli, { recursive: true });
    copyFileSync(CLI_ENTRY, path.join(cli, 'index.js'));
    writeFileSync(path.join(cli, 'package.json'), JSON.stringify({ type: 'module', version: '0.0.0-fixture' }));
    writeFileSync(path.join(cli, 'marketplace.json'), '{"plugins": [');
    const { code, out } = runCli(path.join(cli, 'index.js'), ['list']);
    assert.equal(code, 0);
    assert.match(out, /engineering-lifecycle/);
  });
});

// ---------------------------------------------------------------------------
// End-to-end argv behaviour
// ---------------------------------------------------------------------------

describe('argv dispatch', () => {
  // The negative half of `isEntrypoint` - "imported, so do not dispatch" - is
  // checked by the module-scope INERTNESS probe above, which has to run before
  // this file imports the CLI and throws rather than asserting. It was also
  // spelled here as a test that re-read the probe's result, but a test that
  // asserts a value the file has already refused to load without cannot fail;
  // it added one to the pass count and nothing else. Deleted. What follows is
  // the positive half, which had no coverage at all.

  it('dispatches when reached through a symlink, as the npm bin shim is', (t) => {
    // isEntrypoint() compares `process.argv[1]` against `import.meta.url`, and
    // npm's POSIX bin shim is a SYMLINK to index.js: argv[1] is the symlink in
    // node_modules/.bin while import.meta.url is already resolved. A plain
    // path.resolve on both sides compares unequal, so `npx johns-os list` would
    // exit 0 having printed nothing - a published binary that silently does
    // nothing, which is the worst failure this file can have. realpathSync on
    // both sides is the fix and this is the only thing that exercises it.
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const link = path.join(tempDir(), 'johns-os');
    try {
      symlinkSync(entry, link, 'file');
    } catch (error) {
      // Windows refuses symlinks without Developer Mode or elevation. Reported
      // as a skip rather than returning quietly, because a silent return reads
      // as a pass in the summary and this is the one test standing behind the
      // published binary. npm does not use symlinks on Windows either - it
      // writes .cmd shims that invoke the real path - so the case it guards
      // does not arise on a machine that cannot run it.
      if (error.code === 'EPERM' || error.code === 'ENOSYS') {
        t.skip(`this machine cannot create symlinks (${error.code})`);
        return;
      }
      throw error;
    }
    const { code, out } = runCli(link, ['list']);
    assert.equal(code, 0);
    assert.match(out, /packaged-fixture/, 'the symlinked entrypoint dispatched nothing');
  });

  it('does not dispatch when a different script is the entrypoint', () => {
    // The complement, at the level a test can observe: a wrapper that imports
    // the CLI and never calls main() must produce no output, even with an argv
    // that names a real command. Distinct from the INERTNESS probe in that it
    // runs a COPY in a temp tree with its own manifest, so a regression that
    // only showed up outside the checkout would still be caught here.
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const wrapper = path.join(path.dirname(entry), 'wrapper.mjs');
    writeFileSync(
      wrapper,
      `const mod = await import('./index.js');\n` +
        `process.stdout.write('exports:' + typeof mod.main);\n`,
    );
    const { code, out } = runCli(wrapper, ['list']);
    assert.equal(code, 0);
    assert.equal(out, 'exports:function', 'importing the CLI produced output of its own');
  });

  it('prints the version from the package.json beside it', () => {
    const entry = fakePackage({ version: '9.9.9-fixture' });
    for (const flag of ['--version', '-v']) {
      const { code, out } = runCli(entry, [flag]);
      assert.equal(code, 0);
      assert.equal(out.trim(), '9.9.9-fixture');
    }
  });

  it('prints usage and exits 0 for no command and for help flags', () => {
    const entry = fakePackage({});
    for (const args of [[], ['--help'], ['-h']]) {
      const { code, out, err } = runCli(entry, args);
      assert.equal(code, 0, `${JSON.stringify(args)} exited ${code}`);
      assert.equal(err, '');
      assert.match(out, /Usage:/);
      for (const command of ['install', 'list', 'update', 'init', 'doctor']) {
        assert.match(out, new RegExp(`\\b${command}\\b`));
      }
    }
  });

  it('exits non-zero on an unknown command, with usage on stdout and the error on stderr', () => {
    // Exit 1, not 0: a typo in a script must stop the script. And the
    // diagnostic goes to stderr while usage goes to stdout, so `johns-os list |
    // grep` is not polluted by error text.
    const entry = fakePackage({});
    const { code, out, err } = runCli(entry, ['instal']);
    assert.equal(code, 1);
    assert.match(err, /Unknown command: instal/);
    assert.match(out, /Usage:/);
  });

  it('treats an unrecognised flag in command position as an unknown command', () => {
    // `doctor` is a command; `--doctor` is not, and must not be resolved to one.
    // Commands are looked up with Object.hasOwn, so inherited Object properties
    // must not resolve either - `constructor` as a command name would otherwise
    // find Object.prototype.constructor and be called.
    const entry = fakePackage({});
    for (const bogus of ['--doctor', 'constructor', 'toString', '__proto__']) {
      const { code, err } = runCli(entry, [bogus]);
      assert.equal(code, 1, `${bogus} exited ${code}, expected 1`);
      assert.match(err, /Unknown command/);
    }
  });

  it('exits 2 on bad arguments rather than reporting a missing claude binary', () => {
    // With a working `claude` on PATH, so the exit code can only be about the
    // arguments. The companion test below removes that assumption.
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const stub = claudeStub();
    const cases = [
      [['install', '--nonsense'], /Unknown option/],
      [['install', 'my plugin'], /Invalid plugin name/],
      [['install', 'café'], /Invalid plugin name/],
      [['install', '--scope', 'bogus'], /Invalid --scope/],
      [['install', '--scope'], /--scope requires a value/],
      [['update', '--nonsense'], /Unknown option/],
      [['init', 'somewhere-else'], /Unknown argument for init/],
    ];
    for (const [args, expected] of cases) {
      const { code, err } = runCli(entry, args, { pathPrefix: stub.dir });
      assert.equal(code, 2, `${JSON.stringify(args)} exited ${code}, expected 2`);
      assert.match(err, expected);
    }
    // Nothing was spawned at all. Every one of these fails in parseArgs, which
    // now runs before requireClaude - so not even the `--version` probe should
    // have happened, let alone an install.
    assert.deepEqual(stub.calls(), []);
  });

  it('still names the bad argument when claude is not installed', () => {
    // `install`, `update` and `init` used to call requireClaude() BEFORE
    // parsing, so on a machine without Claude Code every argument mistake came
    // back as exit 127 "claude not found". That is the machine most likely to
    // be typing these commands for the first time, and the diagnostic it got
    // named the wrong problem - sending the user to install a CLI they may
    // already have decided against instead of fixing their typo.
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const absent = claudeStub({ status: 1 });
    const cases = [
      [['install', '--nonsense'], /Unknown option/],
      [['install', 'my plugin'], /Invalid plugin name/],
      [['install', '--scope', 'bogus'], /Invalid --scope/],
      [['install', '--scope'], /--scope requires a value/],
      [['install', 'no-such-plugin'], /Not in the johns-os marketplace/],
      [['update', '--nonsense'], /Unknown option/],
      [['init', 'somewhere-else'], /Unknown argument for init/],
    ];
    for (const [args, expected] of cases) {
      const { code, err } = runCli(entry, args, { pathPrefix: absent.dir });
      assert.equal(code, 2, `${JSON.stringify(args)} exited ${code}, expected 2`);
      assert.match(err, expected);
      assert.doesNotMatch(err, /was not found on PATH/, `${JSON.stringify(args)} blamed the claude binary`);
    }
    assert.deepEqual(absent.calls(), [], 'a rejected argument list still probed for claude');
  });

  it('still refuses to act when claude is missing and the arguments are fine', () => {
    // The other direction. Moving the probe after parsing must not weaken it:
    // a well-formed command on a machine with no `claude` has to stop at 127
    // rather than proceed to spawn something that is not there.
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const absent = claudeStub({ status: 1 });
    const commands = [['install', 'packaged-fixture'], ['update'], ['init']];
    for (const args of commands) {
      const { code, err } = runCli(entry, args, { pathPrefix: absent.dir });
      assert.equal(code, 127, `${JSON.stringify(args)} exited ${code}, expected 127`);
      assert.match(err, /was not found on PATH/);
    }
    // And each stopped AT the probe. Exit 127 with no further argv is what
    // distinguishes "refused to act" from "tried anyway and something failed".
    assert.deepEqual(
      absent.calls(),
      commands.map(() => ['--version']),
    );
  });

  it('reports an unknown plugin against the marketplace it actually loaded', () => {
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const { code, err } = runCli(entry, ['install', 'no-such-plugin'], { pathPrefix: claudeStub().dir });
    assert.equal(code, 2);
    assert.match(err, /Not in the johns-os marketplace: no-such-plugin/);
    assert.match(err, /packaged-fixture/);
  });
});

// ---------------------------------------------------------------------------
// The argv handed to `claude`
// ---------------------------------------------------------------------------

/* Why this section exists.
 *
 * `install`, `update` and `init` do exactly one thing: build an argv and spawn
 * `claude` with it. Everything else they print is commentary. Until the stub
 * recorded its arguments, no test in this file looked at that argv at all - so
 * the suite would have stayed green through a missing plugin name, a dropped
 * `--scope`, a marketplace added from the wrong URL, or `plugin install` sent
 * where `plugin update` was meant. Those are the defects that reach a user's
 * machine and change what is installed on it.
 *
 * The three fixture plugins are named by the packaged manifest, so `install`
 * with no arguments has a known full set to expand to.
 */
describe('the argv handed to claude', () => {
  const MANIFEST = {
    plugins: [
      { name: 'alpha-fixture', version: '1.0.0' },
      { name: 'beta-fixture', version: '2.0.0' },
    ],
  };
  /** A config dir where the marketplace is already registered. */
  const configured = () =>
    fakeConfigDir({ marketplaces: { marketplaces: { 'johns-os': { source: { source: 'git', url: REPO_URL } } } } });

  it('installs one named plugin at the requested scope', () => {
    const entry = fakePackage({ packaged: MANIFEST });
    const stub = claudeStub();
    const { code } = runCli(entry, ['install', 'beta-fixture', '--scope', 'project'], {
      configDir: configured(),
      pathPrefix: stub.dir,
    });
    assert.equal(code, 0);
    assert.deepEqual(stub.calls(), [
      ['--version'],
      ['plugin', 'install', 'beta-fixture@johns-os', '--scope', 'project'],
    ]);
  });

  it('adds the marketplace first, and only when it is not already configured', () => {
    // The URL is the whole security surface of this command: it is the address
    // a user's Claude Code is told to fetch and execute plugins from. Nothing
    // asserted it before.
    const entry = fakePackage({ packaged: MANIFEST });
    const fresh = claudeStub();
    runCli(entry, ['install', 'alpha-fixture'], { configDir: fakeConfigDir({}), pathPrefix: fresh.dir });
    assert.deepEqual(fresh.calls(), [
      ['--version'],
      ['plugin', 'marketplace', 'add', REPO_URL],
      ['plugin', 'install', 'alpha-fixture@johns-os', '--scope', 'user'],
    ]);

    // Already registered: the add must not be repeated. This is the only
    // consumer of marketplaceSource(), so it is also what proves that function
    // is wired to the command rather than merely correct in isolation.
    const known = claudeStub();
    runCli(entry, ['install', 'alpha-fixture'], { configDir: configured(), pathPrefix: known.dir });
    assert.deepEqual(known.calls(), [
      ['--version'],
      ['plugin', 'install', 'alpha-fixture@johns-os', '--scope', 'user'],
    ]);
  });

  it('expands a bare install to every plugin the manifest declares', () => {
    // `targets = plugins.length ? plugins : marketplacePlugins().map(p => p.name)`.
    // If that fell back to the hardcoded table, a bare `npx johns-os install`
    // would install names that are not in the manifest it just read.
    const entry = fakePackage({ packaged: MANIFEST });
    const stub = claudeStub();
    const { code } = runCli(entry, ['install'], { configDir: configured(), pathPrefix: stub.dir });
    assert.equal(code, 0);
    assert.deepEqual(stub.calls(), [
      ['--version'],
      ['plugin', 'install', 'alpha-fixture@johns-os', '--scope', 'user'],
      ['plugin', 'install', 'beta-fixture@johns-os', '--scope', 'user'],
    ]);
  });

  it('installs a plugin named after a scope under the scope that was asked for', () => {
    // Defect 1 end to end. The unit test above proves parseArgs keeps the name;
    // this proves the name survives all the way onto the command line, with the
    // scope still attached to `--scope` and not to the plugin.
    const entry = fakePackage({ packaged: { plugins: [{ name: 'user', version: '1.0.0' }] } });
    const stub = claudeStub();
    runCli(entry, ['install', 'user', '--scope', 'local'], {
      configDir: configured(),
      pathPrefix: stub.dir,
    });
    assert.deepEqual(stub.calls(), [
      ['--version'],
      ['plugin', 'install', 'user@johns-os', '--scope', 'local'],
    ]);
  });

  it('refreshes the marketplace and updates the installed set, without a scope', () => {
    // `claude plugin update` takes no --scope. Accepting one and then passing
    // it on would be an error from claude for every user who supplied it.
    const entry = fakePackage({ packaged: MANIFEST });
    const stub = claudeStub();
    const configDir = fakeConfigDir({
      marketplaces: { marketplaces: { 'johns-os': { source: { source: 'git', url: REPO_URL } } } },
      installed: {
        plugins: {
          'alpha-fixture@johns-os': [{ version: '0.9.0', scope: 'user' }],
          'elsewhere@another-marketplace': [{ version: '1.0.0' }],
        },
      },
    });
    const { code } = runCli(entry, ['update', '--scope', 'project'], { configDir, pathPrefix: stub.dir });
    assert.equal(code, 0);
    assert.deepEqual(stub.calls(), [
      ['--version'],
      ['plugin', 'marketplace', 'update', 'johns-os'],
      // Only ours, and no --scope on the end.
      ['plugin', 'update', 'alpha-fixture@johns-os'],
    ]);
  });

  it('updates the name parsed from the install key, not one the record supplies', () => {
    // The record-spread defect, at the level where it did damage: `update`
    // builds its command line from `record.name`, so a `name` field inside the
    // install record used to become a `claude plugin update <that>@johns-os`
    // nobody asked for. The unit test asserts the parse; this asserts the argv.
    const entry = fakePackage({ packaged: MANIFEST });
    const stub = claudeStub();
    const configDir = fakeConfigDir({
      marketplaces: { marketplaces: { 'johns-os': { source: { source: 'git', url: REPO_URL } } } },
      installed: {
        plugins: {
          'alpha-fixture@johns-os': [{ version: '0.9.0', name: 'beta-fixture', key: 'beta-fixture@johns-os' }],
        },
      },
    });
    runCli(entry, ['update'], { configDir, pathPrefix: stub.dir });
    assert.deepEqual(stub.calls().at(-1), ['plugin', 'update', 'alpha-fixture@johns-os']);
  });

  it('spawns nothing but the probe when nothing from this marketplace is installed', () => {
    const entry = fakePackage({ packaged: MANIFEST });
    const stub = claudeStub();
    const configDir = fakeConfigDir({
      marketplaces: { marketplaces: { 'johns-os': { source: { source: 'git', url: REPO_URL } } } },
      installed: { plugins: { 'elsewhere@another-marketplace': [{ version: '1.0.0' }] } },
    });
    const { code, out } = runCli(entry, ['update'], { configDir, pathPrefix: stub.dir });
    assert.equal(code, 0);
    assert.match(out, /Nothing installed from this marketplace yet/);
    assert.deepEqual(stub.calls(), [['--version'], ['plugin', 'marketplace', 'update', 'johns-os']]);
  });

  it('delivers `init here` as a single argument to -p', () => {
    // The quoting defect, asserted where it actually happened. Under
    // `shell: true` spawnSync joins argv into one unquoted command line, so
    // `/project-init here` arrived at claude as two arguments and the `here`
    // was dropped - `johns-os init here` silently did what `johns-os init`
    // does, in the wrong directory. Recording argv on the far side of cmd.exe's
    // re-parse is the only way to tell one argument from two; every earlier
    // test of this command could only see its exit code.
    const entry = fakePackage({ packaged: MANIFEST });
    for (const [args, expected] of [
      [['init'], '/project-init'],
      [['init', 'here'], '/project-init here'],
      [['init', '--here'], '/project-init here'],
    ]) {
      const stub = claudeStub();
      const { code } = runCli(entry, args, { pathPrefix: stub.dir });
      assert.equal(code, 0, `${JSON.stringify(args)} exited ${code}`);
      assert.deepEqual(stub.calls(), [['--version'], ['-p', expected]]);
    }
  });

  it('stops at the first failure instead of installing on top of a broken marketplace', () => {
    // `marketplace add` failing means there is nothing to install FROM, so the
    // installs must not be attempted and the add's own code must be returned.
    const entry = fakePackage({ packaged: MANIFEST });
    const failing = claudeStub({ status: 3, probeStatus: 0 });
    const { code } = runCli(entry, ['install'], { configDir: fakeConfigDir({}), pathPrefix: failing.dir });
    // 3, not 1: the exit code of whatever actually failed, so a caller can tell
    // "could not add the marketplace" from "a plugin failed to install".
    assert.equal(code, 3);
    assert.deepEqual(failing.calls(), [['--version'], ['plugin', 'marketplace', 'add', REPO_URL]]);
  });
});

// ---------------------------------------------------------------------------
// list and doctor against a fixture config directory
// ---------------------------------------------------------------------------

describe('install state reporting', () => {
  it('shows the installed version beside the marketplace version', () => {
    // The drift this CLI exists to surface: a pinned copy running an older
    // version than the marketplace declares. Both numbers have to appear, and
    // they have to be distinguishable.
    const entry = fakePackage({
      packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] },
    });
    const configDir = fakeConfigDir({
      installed: { plugins: { 'packaged-fixture@johns-os': [{ version: '1.0.0', scope: 'user' }] } },
    });
    const { code, out } = runCli(entry, ['list'], { configDir });
    assert.equal(code, 0);
    assert.match(out, /packaged-fixture\s+installed 1\.0\.0\s+\(marketplace 1\.2\.3\)/);
  });

  it('prints a placeholder rather than "installed undefined" for a versionless record', () => {
    // `installed ${record.version ?? '?'}`. Claude Code owns this file and a
    // record without a version is a shape it is free to write; the `??` is what
    // stops `list` reporting "installed undefined", which reads like a bug in
    // the plugin rather than a gap in the record. Nothing covered it, so the
    // fallback could have been dropped silently.
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const configDir = fakeConfigDir({
      installed: { plugins: { 'packaged-fixture@johns-os': [{ scope: 'user' }] } },
    });
    const { code, out } = runCli(entry, ['list'], { configDir });
    assert.equal(code, 0);
    assert.match(out, /packaged-fixture\s+installed \?\s+\(marketplace 1\.2\.3\)/);
    assert.doesNotMatch(out, /undefined/);
    // Still installed, not misreported as absent - the two states a user acts
    // on differently.
    assert.doesNotMatch(out, /not installed/);
  });

  it('omits the marketplace column for a plugin the manifest gives no version', () => {
    // The other half of the same line: `plugin.version ? ... : ''`. An entry
    // with no version must print nothing rather than "(marketplace undefined)".
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture' }] } });
    const { code, out } = runCli(entry, ['list']);
    assert.equal(code, 0);
    assert.match(out, /packaged-fixture\s+not installed/);
    assert.doesNotMatch(out, /\(marketplace/);
    assert.doesNotMatch(out, /undefined/);
  });

  it('reports a plugin from another marketplace as not installed', () => {
    const entry = fakePackage({
      packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] },
    });
    const configDir = fakeConfigDir({
      installed: { plugins: { 'packaged-fixture@someone-elses': [{ version: '1.0.0' }] } },
    });
    const { out } = runCli(entry, ['list'], { configDir });
    assert.match(out, /packaged-fixture\s+not installed/);
  });

  it('survives a malformed install record instead of crashing list', () => {
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const configDir = fakeConfigDir({ installed: '{"plugins": {' });
    const { code, out, err } = runCli(entry, ['list'], { configDir });
    assert.equal(code, 0, `list failed: ${err}`);
    assert.match(out, /packaged-fixture\s+not installed/);
  });

  it('exits non-zero from doctor when an install path has gone missing', () => {
    // doctor's exit code is the whole point of doctor: it is what a script or a
    // CI step branches on. A stale install that reports 0 is indistinguishable
    // from a healthy one.
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const missing = path.join(tempDir(), 'not-created');
    const configDir = fakeConfigDir({
      installed: {
        plugins: {
          'packaged-fixture@johns-os': [{ version: '1.0.0', scope: 'user', installPath: missing }],
        },
      },
    });
    const { code, out } = runCli(entry, ['doctor'], { configDir });
    assert.equal(code, 1);
    assert.match(out, /MISSING/);
  });

  it('exits non-zero from doctor when the manifest and the install record disagree', () => {
    // The MISMATCH branch, which is the drift this CLI exists to surface and
    // was the only untested exit path in doctor. Plugins execute from a
    // version-pinned copy under ~/.claude/plugins/cache; when that copy's own
    // plugin.json says one version and the install record says another, the
    // code running is not the code the record claims. There is no other
    // symptom - edits simply appear to do nothing.
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const installPath = path.join(tempDir(), 'cache-copy');
    mkdirSync(path.join(installPath, '.claude-plugin'), { recursive: true });
    writeFileSync(
      path.join(installPath, '.claude-plugin', 'plugin.json'),
      JSON.stringify({ name: 'packaged-fixture', version: '0.9.0' }),
    );
    const configDir = fakeConfigDir({
      installed: {
        plugins: { 'packaged-fixture@johns-os': [{ version: '1.0.0', scope: 'user', installPath }] },
      },
    });
    const { code, out } = runCli(entry, ['doctor'], { configDir });
    assert.equal(code, 1);
    // Both numbers, so the reader can tell which side is stale.
    assert.match(out, /MISMATCH\s+manifest says 0\.9\.0, install record says 1\.0\.0/);
    // The path exists, so this must not also be reported as missing.
    assert.doesNotMatch(out, /MISSING/);
  });

  it('exits 0 from doctor when the manifest and the install record agree', () => {
    // The control for the test above. Without it, a doctor that printed
    // MISMATCH unconditionally - or that compared something other than the two
    // versions - would still pass, and every healthy install would exit 1.
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const installPath = path.join(tempDir(), 'cache-copy');
    mkdirSync(path.join(installPath, '.claude-plugin'), { recursive: true });
    writeFileSync(
      path.join(installPath, '.claude-plugin', 'plugin.json'),
      JSON.stringify({ name: 'packaged-fixture', version: '1.0.0' }),
    );
    const configDir = fakeConfigDir({
      installed: {
        plugins: { 'packaged-fixture@johns-os': [{ version: '1.0.0', scope: 'user', installPath }] },
      },
    });
    const { code, out } = runCli(entry, ['doctor'], { configDir });
    assert.equal(code, 0);
    assert.doesNotMatch(out, /MISMATCH/);
    assert.doesNotMatch(out, /MISSING/);
  });

  it('does not report a mismatch when the installed copy declares no version', () => {
    // `if (declared && record.version && declared !== record.version)`. An
    // install directory with no plugin.json, or one that omits `version`, is
    // not evidence of drift - reporting it as MISMATCH would make doctor exit 1
    // on a healthy machine, and doctor's exit code is what CI branches on.
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const installPath = path.join(tempDir(), 'cache-copy');
    mkdirSync(path.join(installPath, '.claude-plugin'), { recursive: true });
    writeFileSync(
      path.join(installPath, '.claude-plugin', 'plugin.json'),
      JSON.stringify({ name: 'packaged-fixture' }),
    );
    const configDir = fakeConfigDir({
      installed: {
        plugins: { 'packaged-fixture@johns-os': [{ version: '1.0.0', scope: 'user', installPath }] },
      },
    });
    const { code, out } = runCli(entry, ['doctor'], { configDir });
    assert.equal(code, 0);
    assert.doesNotMatch(out, /MISMATCH/);
  });

  it('exits 0 from doctor when nothing from this marketplace is installed', () => {
    const entry = fakePackage({ packaged: { plugins: [{ name: 'packaged-fixture', version: '1.2.3' }] } });
    const configDir = fakeConfigDir({ installed: { plugins: {} } });
    const { code, out } = runCli(entry, ['doctor'], { configDir });
    assert.equal(code, 0);
    assert.match(out, /No plugins from this marketplace are installed/);
  });
});
