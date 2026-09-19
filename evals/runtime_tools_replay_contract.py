"""No-network controls for actual Creta lookup and monthly-rate failures."""
import copy
import unittest
from unittest.mock import patch

from server.runtime_tools import calculate, source_lookup


class RuntimeToolsReplay(unittest.TestCase):
    def setUp(self):
        self.question = 'Use 1 percent monthly interest for my 10 lakh loan over 5 years; do not treat it as annual interest.'
        self.request = {'tool': 'calculator', 'operation': 'emi', 'inputs': [
            {'name': 'principal', 'value': 1000000, 'unit': 'INR', 'source_id': 'customer', 'quote': '10 lakh'},
            {'name': 'monthly_rate', 'value': 1, 'unit': 'percent', 'source_id': 'customer', 'quote': '1 percent monthly interest'},
            {'name': 'tenure', 'value': 5, 'unit': 'years', 'source_id': 'customer', 'quote': '5 years'},
        ]}

    def test_monthly_basis_is_calculated_without_invented_annual_input(self):
        result = calculate(self.request, [], self.question)
        self.assertEqual(result['value'], '22244.45 INR/month')
        self.assertIn('monthly percent/100', result['derivation']['formula'])
        self.assertEqual(result['derivation']['inputs'][1]['value'], 1)

    def test_monthly_rate_cannot_be_relabelled_annual(self):
        req = copy.deepcopy(self.request)
        req['inputs'][1]['name'] = 'annual_rate'
        with self.assertRaisesRegex(ValueError, 'unit must be explicit'):
            calculate(req, [], self.question)

    def test_annual_rate_cannot_be_relabelled_monthly(self):
        req = copy.deepcopy(self.request)
        req['inputs'][1]['quote'] = '1 percent annual interest'
        with self.assertRaisesRegex(ValueError, 'unit must be explicit'):
            calculate(req, [], self.question.replace('monthly', 'annual'))

    def test_two_competing_rate_bases_are_not_silently_chosen(self):
        req = copy.deepcopy(self.request)
        req['inputs'].append({**req['inputs'][1], 'name': 'annual_rate', 'quote': '1 percent annual interest'})
        with self.assertRaisesRegex(ValueError, 'Required inputs'):
            calculate(req, [], self.question + ' Also 1 percent annual interest.')

    def test_live_lookup_stays_with_selected_model_and_market(self):
        seed = 'https://www.hyundai.com/in/en/find-a-car/creta/highlights'
        allowed = 'https://www.hyundai.com/in/en/find-a-car/creta/features'
        rejected = [
            'https://www.hyundai.com/in/en/find-a-car/alcazar/highlights',
            'https://www.hyundai.com/uk/en/find-a-car/creta/highlights',
            'https://www.hyundai.com/in/en/connect-to-service/road-side-assistance',
        ]
        calls = []
        def fetch(url, **kwargs):
            calls.append(url)
            return {'final_url': url, 'sections': [{'text': 'CRETA safety feature table preserves its exact variant conditions.', 'locator': 'Safety'}],
                    'links': [{'url': child, 'label': 'CRETA safety highlights'} for child in [*rejected, allowed]]}
        with patch('server.crawl.fetch_public', side_effect=fetch), patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
            result = source_lookup({'tool': 'source_lookup', 'url': seed, 'query': 'Creta safety highlights'}, 'Check ' + seed, [])
        self.assertEqual(calls, [seed, allowed])
        self.assertEqual(result['scope']['model_tokens'], ['creta'])
        self.assertTrue(all('/creta/' in item['source']['ref'] for item in result['evidence']))

    def test_redirect_cannot_change_the_model(self):
        seed = 'https://www.hyundai.com/in/en/find-a-car/creta/highlights'
        with patch('server.crawl.fetch_public', return_value={'final_url': seed.replace('/creta/', '/alcazar/'), 'text': 'Safety information about a different vehicle.'}):
            with self.assertRaisesRegex(ValueError, 'No readable section'):
                source_lookup({'tool': 'source_lookup', 'url': seed, 'query': 'safety'}, 'Check ' + seed, [])

    def test_generic_homepage_does_not_authorize_arbitrary_product_links(self):
        seed = 'https://example.com/'
        page = {'final_url': seed, 'text': 'The company offers product information and general safety resources.',
                'links': [{'url': 'https://example.com/other-car/safety', 'label': 'Safety'}]}
        with patch('server.crawl.fetch_public', return_value=page) as fetch:
            result = source_lookup({'tool': 'source_lookup', 'url': seed, 'query': 'safety'}, 'Check ' + seed, [])
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(len(result['pages']), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
