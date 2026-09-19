"""CR47: real pitch/graph with the saved revised-priority request; no providers."""
from __future__ import annotations
import asyncio
import copy
import json
import socket
import sys
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import schemas, store, runtime_graph as graph, runtime_state
from server.agents import pitch, voice

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/pitch_priority_revision.json').read_text())
BUNDLE = FIXTURE['published_bundle']
REQUEST = FIXTURE['actual_calls'][1]['request']['body']
REAR = next(s for s in BUNDLE['segments'] if s['id'] == 'seating-and-cargo')
RECLINE = next(l for l in REAR['deeper'] if l['id'] == 'seating-and-cargo-D2')

def selection():
    # Session-token selection under the actual prompt: one exact rear-passenger
    # proof, not another provider call or a product answer in production code.
    return schemas.PitchPlan(customer_state='stated_need',
        decision_frame='Focusing on your parents in the rear seats.', follow_up_question='',
        primary_outcome='Check rear-seat fit with your parents', focus_topics=['rear-seat comfort'],
        route=[{'segment_id':REAR['id']}], advance='Book a Test Drive', advance_cta='cta-test-drive',
        personalized_segments=[{'segment_id':REAR['id'], 'customer_quote':'my parents in the rear seats',
                                'lines':[RECLINE]}])

class PriorityRevision(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.prompts = []
        for name in ('socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex'):
            self.stack.enter_context(patch(name, side_effect=AssertionError('No network')))
        self.stack.enter_context(patch.object(store, 'read_json', side_effect=lambda d,n:copy.deepcopy(BUNDLE) if n=='bundle.json' else None))
        self.stack.enter_context(patch.object(store, 'log'))
        self.stack.enter_context(patch.object(store, 'write_json', side_effect=AssertionError('No application writes')))
        self.stack.enter_context(patch.object(voice, 'render_line', side_effect=AssertionError('No voice')))
        def model(system, *args, **kwargs):
            self.prompts.append((system, args[0])); return selection()
        self.stack.enter_context(patch.object(pitch.runtime, 'structured', side_effect=model))

    def run_pitch(self, refine=True, **overrides):
        kwargs = dict(voice_it=False, seen_segment_ids=REQUEST['seen_segments'],
                      expected_snapshot_id=BUNDLE['knowledge_snapshot_id'], expected_demo_version=8)
        kwargs.update(overrides)
        return pitch.plan_pitch('dm_41513908', REQUEST['profile'], refine, **kwargs)

    def test_actual_corrected_need_can_select_exact_seen_rear_proof(self):
        result = self.run_pitch()
        self.assertEqual([r['segment_id'] for r in result['route']], [REAR['id']])
        self.assertEqual(result['revisit_segment_ids'], [REAR['id']])
        pack = json.loads(self.prompts[0][0].split('SEGMENT SCRIPT (reviewed main/deeper lines, with immutable evidence and delivery):\n')[1].split('\n\nUSPS:')[0])
        self.assertIn(REAR['id'], [s['id'] for s in pack])
        selected = result['personalized_segments'][0]['lines']
        factual = next(l for l in selected if l['fact_ids'])
        for key in ('text','fact_ids','audio','visual','delivery'):
            self.assertEqual(factual[key], RECLINE[key])
        self.assertIn('selected trims', factual['text'])
        self.assertNotIn('ventilated', ' '.join(l['text'] for l in selected))
        self.assertIn('my parents in the rear seats', selected[0]['text'])
        self.assertEqual(result['custom_batches'], [])

    def test_normal_continuation_keeps_seen_excluded(self):
        result = self.run_pitch(False)
        self.assertNotIn(REAR['id'], [r['segment_id'] for r in result['route']])
        self.assertEqual(result['revisit_segment_ids'], [])

    def test_initial_refine_without_seen_does_not_authorize_revisits(self):
        self.assertEqual(self.run_pitch(seen_segment_ids=[])['revisit_segment_ids'], [])

    def test_forged_route_and_unreviewed_speech_gain_no_permission(self):
        bad = selection(); bad.route.append(schemas.RouteStep(segment_id='invented-segment'))
        bad.personalized_segments[0].lines[0].text = 'Your parents are guaranteed comfort.'
        with patch.object(pitch.runtime, 'structured', return_value=bad):
            result = self.run_pitch(seen_segment_ids=REQUEST['seen_segments']+['invented-segment'])
        self.assertNotIn('invented-segment', result['revisit_segment_ids'])
        speech = ' '.join(l['text'] for s in result['personalized_segments'] for l in s['lines'])
        self.assertNotIn('guaranteed', speech)

    def test_publication_change_and_cancellation_still_block(self):
        with self.assertRaises(pitch.PublishedDemoChanged): self.run_pitch(expected_demo_version=7)
        control = runtime_state.TurnControl(time.monotonic()+2); control.cancelled.set()
        with self.assertRaises(InterruptedError):
            asyncio.run(graph.explore({'demo_id':'dm_41513908','control':control}))

    def test_actual_graph_preserves_only_explicit_selected_revisit(self):
        state = {'demo_id':'dm_41513908','profile':REQUEST['profile'],'refine':True,
                 'seen_segments':REQUEST['seen_segments'],'snapshot_id':BUNDLE['knowledge_snapshot_id'],
                 'demo_version':8,'control':runtime_state.TurnControl(time.monotonic()+5)}
        result = asyncio.run(graph.explore(state))['result']
        self.assertEqual([r['segment_id'] for r in result['route']], [REAR['id']])
        for refine in (False, True):
            forged = {'route':[{'segment_id':REAR['id']}], 'revisit_segment_ids':['not-selected']}
            with patch.object(pitch,'plan_pitch',return_value=forged):
                output=asyncio.run(graph.explore({**state,'refine':refine}))['result']
            self.assertEqual(output['route'], [])

    def test_refine_flag_is_request_local_not_inherited_or_truthy(self):
        observed=[]
        async def invoke(state,*args): observed.append(state['refine']); return {'result':{}}
        with patch.object(graph,'previous_state',return_value={'refine':True}), \
             patch.object(graph,'checkpoint'), patch.object(graph.usage,'trace'), \
             patch.object(graph.graph,'ainvoke',side_effect=invoke):
            for kind,body in [('explore',{}),('explore',{'refine':'yes'}),('qa',{'refine':True}),('explore',{'refine':True})]:
                asyncio.run(graph.run_turn('dm_41513908',{'session_id':'priority-contract',**body},kind=kind))
        self.assertEqual(observed,[False,False,False,True])

if __name__ == '__main__': unittest.main()
