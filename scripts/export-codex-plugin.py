#!/usr/bin/env python3
"""Export selected skills as a verified local Codex plugin; never install it."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('awt_installer', SOURCE / 'scripts/install-codex-skills.py')
installer = importlib.util.module_from_spec(SPEC)
sys.dont_write_bytecode = True
SPEC.loader.exec_module(installer)
PLUGIN = 'academic-writing-toolkit'
POLICY_KEYS = ('disable-model-invocation', 'user-invocable', 'allowed-tools')


def preserve_ui_assets(folder, previous, metadata):
    interface = metadata.get('interface', {})
    if not isinstance(interface, dict):
        raise installer.InstallError('Invalid UI metadata: ' + previous.name)
    for key in ('icon_small', 'icon_large'):
        if key not in interface:
            continue
        value = interface[key]
        if (not isinstance(value, str) or not value or '\\' in value
                or Path(value).is_absolute() or PureWindowsPath(value).drive
                or '..' in Path(value).parts
                or Path(value).suffix.lower() not in ('.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp')):
            raise installer.InstallError('UI asset must be a relative file within the skill: ' + key)
        source = previous / value
        if not source.is_file() or previous.resolve() not in source.resolve().parents:
            raise installer.InstallError('UI asset is missing or outside the skill: ' + value)
        installer.plain_path(source, stop=previous)
        installer.copy_resource(source, folder / value)


def preserve_policy(folder, previous, name):
    import yaml

    old_skill = previous / name / 'SKILL.md'
    if not old_skill.is_file():
        return
    parts = old_skill.read_text(encoding='utf-8').split('---', 2)
    if len(parts) != 3 or parts[0].strip():
        raise installer.InstallError('Invalid policy-source frontmatter: ' + name)
    old = yaml.safe_load(parts[1])
    if not isinstance(old, dict):
        raise installer.InstallError('Invalid policy-source frontmatter: ' + name)
    if old.get('name') != name:
        raise installer.InstallError('Policy source names a different skill: ' + name)
    path = folder / 'SKILL.md'
    _, header, body = path.read_text(encoding='utf-8').split('---', 2)
    current = yaml.safe_load(header)
    for key in POLICY_KEYS:
        if key in old:
            if key != 'allowed-tools' and not isinstance(old[key], bool):
                raise installer.InstallError('Invocation flags must be boolean: ' + name)
            current[key] = old[key]
        else:
            current.pop(key, None)
    installer.write_text(path, '---\n' + yaml.safe_dump(current, sort_keys=False, allow_unicode=True, width=1000) + '---' + body)
    metadata = previous / name / 'agents/openai.yaml'
    if metadata.is_file():
        data = yaml.safe_load(metadata.read_text(encoding='utf-8')) or {}
        if not isinstance(data, dict) or not isinstance(data.get('policy', {}), dict):
            raise installer.InstallError('Invalid invocation metadata: ' + name)
        implicit = data.get('policy', {}).get('allow_implicit_invocation', True)
        if not isinstance(implicit, bool):
            raise installer.InstallError('Codex invocation policy must be boolean: ' + name)
        preserve_ui_assets(folder, previous / name, data)
        installer.copy_resource(metadata, folder / 'agents/openai.yaml')


def validate_output(output):
    resolved = output.resolve()
    for path in (SOURCE, SOURCE / '.claude/skills', SOURCE / '.agents/skills', SOURCE / 'scripts', SOURCE / 'references'):
        path = path.resolve()
        if resolved == path or resolved in path.parents or path in resolved.parents and path != SOURCE.resolve():
            raise installer.InstallError('Output must not replace source directories')
    if installer.linked(output):
        raise installer.InstallError('Output must not be a symlink or junction')
    if output.exists() and (not output.is_dir() or
                            any(output.iterdir()) and not (output / '.codex-plugin/upstream.json').is_file()):
        raise installer.InstallError('Output exists and is not a generated plugin; choose a new directory')


def export(output, names, python, previous=None):
    installer.check_runtime(python)
    installer.check_node()
    validate_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.awt-plugin-', dir=output.parent) as temporary:
        temporary = Path(temporary)
        prepared = temporary / 'prepared'
        prepared.mkdir()
        installer.prepare(SOURCE, prepared, temporary / 'empty', python)
        stage = temporary / 'package'
        (stage / 'skills').mkdir(parents=True)
        for name in names:
            installer.copy_resource(prepared / name, stage / 'skills' / name)
            if previous is not None:
                preserve_policy(stage / 'skills' / name, previous, name)
        helper_checks = 'not applicable to this selection'
        if {'audit', 'export', 'map', 'verify-refs'}.issubset(names):
            installer.smoke(stage / 'skills', python)
            helper_checks = 'passed'
        for path in (stage / 'skills').glob('*/SKILL.md'):
            for relative in re.findall(r'\{skill_dir\}/([A-Za-z0-9/._-]+)', path.read_text(encoding='utf-8')):
                if not (path.parent / relative).is_file():
                    raise installer.InstallError('Missing selected helper: ' + relative)
        commit = installer.run(['git', '-C', SOURCE, 'rev-parse', 'HEAD']).strip()
        dirty = bool(installer.run(['git', '-C', SOURCE, 'status', '--porcelain', '--',
                                    '.claude/skills', 'scripts', 'references',
                                    'experimental/writing-loop/engine', 'LICENSE']).strip())
        content_hashes = installer.manifest(stage)
        digest = hashlib.sha256(json.dumps(content_hashes, sort_keys=True).encode()).hexdigest()
        version = '0.1.0+source.' + commit[:12] + '.' + digest[:12]
        manifest = {
            'name': PLUGIN, 'version': version,
            'description': 'Selected Academic Writing Toolkit skills prepared for local Codex use.',
            'author': {'name': 'yha9806'},
            'repository': 'https://github.com/yha9806/academic-writing-toolkit',
            'skills': './skills/',
            'interface': {'displayName': 'Academic Writing Toolkit',
                          'shortDescription': 'Academic writing workflows',
                          'developerName': 'yha9806', 'category': 'Productivity'},
        }
        installer.write_json(stage / '.codex-plugin/plugin.json', manifest)
        installer.copy_resource(SOURCE / 'LICENSE', stage / 'LICENSE')
        receipt = {'schemaVersion': 1, 'repository': manifest['repository'],
                   'commit': commit, 'sourceDirty': dirty, 'version': version,
                   'selectedSkills': list(names), 'python': str(python),
                   'preparedFileHashes': content_hashes,
                   'preservedPolicyFrom': str(previous) if previous else None,
                   'helperChecks': helper_checks}
        installer.write_json(stage / '.codex-plugin/upstream.json', receipt)
        if output.exists() and any(output.iterdir()):
            if installer.manifest(output) != installer.manifest(stage):
                raise installer.InstallError('Output exists with different content; keep it and choose a new directory')
            return {'status': 'unchanged', 'output': str(output), 'skills': list(names), 'helperChecks': helper_checks}
        if output.exists():
            output.rmdir()
        stage.rename(output)
    return {'status': 'exported', 'output': str(output), 'skills': list(names),
            'version': version, 'commit': commit, 'helperChecks': helper_checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--skill', action='append', choices=installer.NAMES)
    parser.add_argument('--python', type=Path)
    parser.add_argument('--install-deps', action='store_true')
    parser.add_argument('--preserve-policy-from', type=Path)
    args = parser.parse_args()
    if args.python and args.install_deps:
        parser.error('Choose --python or --install-deps')
    output = Path(os.path.abspath(args.out.expanduser()))
    names = tuple(sorted(set(args.skill or installer.NAMES)))
    previous = Path(os.path.abspath(args.preserve_policy_from.expanduser())) if args.preserve_policy_from else None
    if previous is not None and not previous.is_dir():
        parser.error('--preserve-policy-from must name an existing skill directory')
    validate_output(output)
    python = Path(os.path.abspath(args.python.expanduser())) if args.python else Path(sys.executable).absolute()
    if args.install_deps:
        state = output.parent / '.awt-plugin-runtimes'
        installer._MANAGED_ROOTS = (state,)
        installer.plain_path(state, stop=state.parent)
        with installer.install_lock(state):
            python = installer.private_runtime(SOURCE, state)
    if python != Path(sys.executable).absolute():
        command = [str(python), str(Path(__file__).resolve()), '--out', str(output)]
        for name in names:
            command.extend(['--skill', name])
        if previous is not None:
            command.extend(['--preserve-policy-from', str(previous)])
        return subprocess.call(command)
    print(json.dumps(export(output, names, python, previous), indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (installer.InstallError, OSError, ValueError) as error:
        print('AWT_PLUGIN_EXPORT: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
