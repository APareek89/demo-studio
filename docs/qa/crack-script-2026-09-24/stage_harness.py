#!/usr/bin/env python3
"""Capture/replay exact in-app prompts, safely isolated; never a provider call.

Usage:
  python stage_harness.py --run-dir /tmp/.../iteration-01 init --fixture understanding.json [--demo-spec demo-spec.json]
  python stage_harness.py --run-dir /tmp/.../iteration-01 run coach
  # Fill calls/coach-01.response.json with the model JSON matching captured schema.
  python stage_harness.py --run-dir /tmp/.../iteration-01 run coach
  python stage_harness.py --run-dir /tmp/.../iteration-01 run planner
  python stage_harness.py --run-dir /tmp/.../iteration-01 run author

Missing responses exit75 after capture. Reruns restore the stage's original temp
snapshot, replay earlier calls, and capture the next repair/completion unchanged.
Use a new run directory for a new prompt iteration. Never use a production root.
Demo-spec may contain settings/product/sources metadata and assets, a list of
{from: absolute existing file, to: relative path inside this isolated demo}.
No schema, validator, visual-audit or duration policy is overridden.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import socket
import sys

BASE = Path('/tmp/demo-crack-script-20260924').resolve()
DEFAULT_REPO = Path('/Users/macbook/Documents/demo-studio-crack-script')

class PendingResponse(BaseException):
    pass


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=DEFAULT_REPO)
    parser.add_argument('--run-dir', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--fixture', type=Path, required=True)
    init.add_argument('--demo-spec', type=Path)
    run = sub.add_parser('run')
    run.add_argument('stage', choices=['coach', 'planner', 'author'])
    run.add_argument('--instruction', default='')
    args = parser.parse_args()
    root = args.run_dir.resolve()
    if not root.is_relative_to(BASE) or root == BASE:
        parser.error('run-dir must be a child of the dedicated /tmp audit root')
    root.mkdir(parents=True, exist_ok=True)
    os.environ.update(MOCK_LLM='1', CLOUD_SYNC='0', STORAGE_BACKEND='local',
                      DEMO_STUDIO_DATA=str(root/'data'), DEMO_STUDIO_GRAPH_DB=str(root/'graph.sqlite'),
                      TTS_PROVIDER='gemini', STT_PROVIDER='browser')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.repo.resolve()))
    outbound = []
    def denied(*a, **kw):
        outbound.append(repr(a[:1]))
        raise AssertionError('Sockets blocked in isolated prompt simulation')
    original_socket = socket.socket
    class BlockedSocket(original_socket):
        def connect(self, *a, **kw): return denied(*a, **kw)
        def connect_ex(self, *a, **kw): return denied(*a, **kw)
        def sendto(self, *a, **kw): return denied(*a, **kw)
    socket.socket = BlockedSocket
    socket.create_connection = denied
    socket.getaddrinfo = denied
    from server import config, store, schemas
    from server.agents import coach, plan, author
    from server.llm import claude
    assert config.MOCK_LLM and config.DATA_DIR == root/'data' and config.GRAPH_DB == root/'graph.sqlite'
    metadata_path = root/'run.json'
    if args.command == 'init':
        if metadata_path.exists():
            parser.error('already initialized; use a new iteration directory')
        fixture = json.loads(args.fixture.read_text())
        for key in ('product', 'brand', 'facts', 'unknowns', 'images', 'shots'):
            if key not in fixture: parser.error(f'fixture missing {key}')
        spec = json.loads(args.demo_spec.read_text()) if args.demo_spec else {}
        demo = store.new_demo('Creta prompt simulation — no provider calls')
        demo['product'].update(fixture.get('product', {}))
        demo['product'].update(spec.get('product', {}))
        demo['settings'].update(spec.get('settings', {}))
        demo['sources'] = copy.deepcopy(spec.get('sources', []))
        store.save(demo['id'], demo)
        store.write_json(demo['id'], 'understanding.json', fixture)
        for asset in spec.get('assets', []):
            dest = (store.demo_dir(demo['id'])/asset['to']).resolve()
            if not dest.is_relative_to(store.demo_dir(demo['id']).resolve()):
                raise ValueError('asset destination escapes isolated demo')
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(asset['from']), dest)
        dump(metadata_path, {'demo_id': demo['id'], 'repo': str(args.repo.resolve()),
                             'fixture': str(args.fixture.resolve()), 'fixture_sha256': hashlib.sha256(args.fixture.read_bytes()).hexdigest(),
                             'mode': 'in-session reasoning replay; real app prompts and validators, no model or voice provider',
                             'completed': []})
        print(json.dumps({'status': 'initialized', 'demo_id': demo['id'], 'run_dir': str(root)}))
        return 0
    meta = json.loads(metadata_path.read_text())
    if str(args.repo.resolve()) != meta['repo']:
        raise ValueError('repository differs from initialized iteration')
    stage = args.stage
    if stage in meta['completed']:
        print(json.dumps({'status': 'already_complete', 'stage': stage, 'artifact': str(root/'artifacts'/f'{stage}.json')}))
        return 0
    dependency = {'planner': 'coach', 'author': 'planner'}.get(stage)
    if dependency and dependency not in meta['completed']:
        raise ValueError(f'{dependency} must complete first')
    demo_id = meta['demo_id']
    demo_dir = store.demo_dir(demo_id)
    baseline = root/'stage-inputs'/stage
    if not baseline.exists():
        shutil.copytree(demo_dir, baseline)
    else:
        # Only this specifically validated throwaway demo is replaced.
        assert demo_dir.resolve().is_relative_to(root/'data')
        shutil.rmtree(demo_dir)
        shutil.copytree(baseline, demo_dir)
    events = []
    counter = 0
    calls = root/'calls'
    def replay(system, content, schema, **kwargs):
        nonlocal counter
        counter += 1
        stem = f'{stage}-{counter:02d}'
        request_path = calls/f'{stem}.request.json'
        response_path = calls/f'{stem}.response.json'
        request = {'stage': stage, 'call': counter, 'system': system, 'content': content,
                   'schema_name': schema.__name__, 'schema': schema.model_json_schema(), 'kwargs': kwargs}
        fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if response_path.exists() and request_path.exists():
            old = json.loads(request_path.read_text())
            if old['request_sha256'] != fingerprint:
                raise ValueError(f'{stem} changed since its response was requested; use a new iteration')
        request['request_sha256'] = fingerprint
        dump(request_path, request)
        (calls/f'{stem}.system.txt').write_text(system)
        (calls/f'{stem}.content.txt').write_text(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2))
        dump(calls/f'{stem}.schema.json', schema.model_json_schema())
        if not response_path.exists():
            raise PendingResponse(str(response_path))
        response = json.loads(response_path.read_text())
        # Pydantic validates precisely the schema used by the actual call.
        result = schema.model_validate(response)
        events.append({'event': 'replayed', 'call': stem, 'request_sha256': fingerprint,
                       'response_sha256': hashlib.sha256(response_path.read_bytes()).hexdigest()})
        return result
    claude.structured = replay
    def replay_coach(und, entry):
        frame = inspect.currentframe().f_back
        if frame.f_code is not coach.run.__code__:
            raise AssertionError('Coach hook called outside actual coach.run')
        local = frame.f_locals
        return replay(coach.COACH_SYSTEM.format(category=local['category']), local['content'],
                      schemas.Playbook, max_tokens=12000).model_dump()
    coach.mock_playbook = replay_coach
    def emit(message): events.append({'event': 'stage', 'message': str(message)})
    status = 'failed'
    try:
        runner = {'coach': coach.run, 'planner': plan.run, 'author': author.run}[stage]
        result = runner(demo_id, emit, instruction=args.instruction)
        dump(root/'artifacts'/f'{stage}.json', result)
        meta['completed'].append(stage)
        dump(metadata_path, meta)
        status = 'complete'
        print(json.dumps({'status': status, 'stage': stage, 'calls': counter,
                          'artifact': str(root/'artifacts'/f'{stage}.json'), 'issues': result.get('issues', [])}, ensure_ascii=False))
        return 0
    except PendingResponse as pending:
        status = 'response_required'
        print(json.dumps({'status': status, 'stage': stage, 'calls': counter, 'response_file': str(pending)}))
        return 75
    finally:
        dump(root/'events'/f'{stage}.json', {'status': status, 'events': events, 'socket_attempts': outbound})
        if outbound: raise AssertionError('Unexpected network attempt; see events')

if __name__ == '__main__':
    raise SystemExit(main())
