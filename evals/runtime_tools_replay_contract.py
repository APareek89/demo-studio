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

    def city_price_lookup(self, question, *, seed=None, query='CRETA price', history=None):
        root = 'https://www.hyundai.com/in/en/find-a-car/creta/'
        seed = seed or root + 'highlights'
        links = [root + suffix for suffix in ['price-in-ahmedabad', 'price', 'price-in-mumbai', 'price-in-new-delhi']]
        calls = []
        def fetch(url, **kwargs):
            calls.append(url)
            return {'final_url': url, 'sections': [{'text': 'CRETA price depends on the selected configuration and applicable charges.', 'locator': 'Price'}],
                    'links': [{'url': child, 'label': 'CRETA price in ' + child.rsplit('/', 1)[-1]} for child in links]}
        with patch('server.crawl.fetch_public', side_effect=fetch), patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
            result = source_lookup({'tool': 'source_lookup', 'url': seed, 'query': query}, question + ' ' + seed, history or [])
        return calls, result

    def test_model_wide_price_lookup_cannot_choose_a_city_from_menu_or_model_query(self):
        for query in ['CRETA on road price', 'CRETA price Ahmedabad']:
            with self.subTest(query=query):
                calls, result = self.city_price_lookup('Verify the exact on-road price in my city.', query=query)
                self.assertEqual([url.rsplit('/', 1)[-1] for url in calls], ['highlights', 'price'])
                self.assertTrue(all('/price-in-' not in f['source']['ref'] for f in result['evidence']))

    def test_customer_named_city_keeps_its_page_and_excludes_other_cities(self):
        calls, result = self.city_price_lookup('Check the CRETA price in Mumbai.')
        self.assertEqual([url.rsplit('/', 1)[-1] for url in calls], ['highlights', 'price', 'price-in-mumbai'])
        self.assertEqual([p['url'] for p in result['pages']], calls)

    def test_customer_history_can_name_a_multiword_city_but_assistant_history_cannot_add_one(self):
        calls, _ = self.city_price_lookup('Check the price for my city.', history=[
            {'role': 'user', 'text': 'I live in New Delhi.'},
            {'role': 'agent', 'text': 'Let us use Ahmedabad as an example.'},
        ])
        self.assertEqual([url.rsplit('/', 1)[-1] for url in calls], ['highlights', 'price', 'price-in-new-delhi'])

    def test_assistant_city_and_partial_word_are_not_customer_locality(self):
        calls, _ = self.city_price_lookup('The Mumbaikar magazine mentioned this price.', history=[{'role': 'assistant', 'text': 'Check Mumbai.'}])
        self.assertEqual([url.rsplit('/', 1)[-1] for url in calls], ['highlights', 'price'])

    def test_directly_supplied_city_price_url_does_not_require_repeating_the_city(self):
        seed = 'https://www.hyundai.com/in/en/find-a-car/creta/price-in-mumbai'
        calls, result = self.city_price_lookup('Check the price at this exact page.', seed=seed)
        self.assertEqual(calls[0], seed)
        self.assertEqual(result['url'], seed)
        self.assertFalse(any('ahmedabad' in url or 'new-delhi' in url for url in calls))

    def test_model_wide_redirect_cannot_select_an_unsupplied_city(self):
        seed = 'https://www.hyundai.com/in/en/find-a-car/creta/highlights'
        with patch('server.crawl.fetch_public', return_value={'final_url': seed.rsplit('/', 1)[0] + '/price-in-ahmedabad', 'text': 'CRETA price in Ahmedabad is a city-specific price.'}):
            with self.assertRaisesRegex(ValueError, 'No readable section'):
                source_lookup({'tool': 'source_lookup', 'url': seed, 'query': 'price'}, 'Check the price in my city at ' + seed, [])

    def test_explicit_city_redirect_cannot_switch_to_another_city(self):
        seed = 'https://www.hyundai.com/in/en/find-a-car/creta/price-in-mumbai'
        with patch('server.crawl.fetch_public', return_value={'final_url': seed.replace('mumbai', 'ahmedabad'), 'text': 'CRETA price in Ahmedabad is a city-specific price.'}):
            with self.assertRaisesRegex(ValueError, 'No readable section'):
                source_lookup({'tool': 'source_lookup', 'url': seed, 'query': 'price'}, 'Check this exact page ' + seed, [])

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

    def test_lookup_prefers_answer_body_over_titles_questions_and_contact_forms(self):
        seed = 'https://www.hyundai.com/in/en/find-a-car/creta/specification'
        sections = [{'heading': 'CRETA engine specification', 'text': 'CRETA engine specification', 'locator': 'title'},
                    {'heading': 'CRETA engine specification', 'text': 'Interested in a Hyundai? Share number to know more from us.', 'locator': 'contact'},
                    {'heading': 'Engine options', 'text': 'What engine options does the CRETA provide?', 'locator': 'question'},
                    {'heading': 'Engine options', 'text': 'A 1.5-litre petrol and a 1.5-litre turbo petrol are listed for this model.', 'locator': 'answer'}]
        with patch('server.crawl.fetch_public', return_value={'final_url': seed, 'sections': sections}):
            result = source_lookup({'tool': 'source_lookup', 'url': seed, 'query': 'Using this page tell me what engine information it actually provides for Creta'}, 'Check ' + seed, [])
        self.assertEqual([f['source']['locator'] for f in result['evidence']], ['answer', 'title'])

    def test_model_name_alone_does_not_displace_topic_evidence(self):
        seed = 'https://www.hyundai.com/in/en/find-a-car/creta/highlights'
        sections = [{'heading': 'CRETA', 'text': 'The CRETA name appears across the model family.', 'locator': f'generic{i}'} for i in range(8)]
        sections.append({'heading': 'Cabin', 'text': 'A panoramic sunroof is available on selected trims.', 'locator': 'sunroof'})
        with patch('server.crawl.fetch_public', return_value={'final_url': seed, 'sections': sections}):
            result = source_lookup({'tool': 'source_lookup', 'url': seed, 'query': 'Can you verify whether the Creta page mentions a panoramic sunroof?'}, 'Check ' + seed, [])
        self.assertEqual([f['source']['locator'] for f in result['evidence']], ['sunroof'])

    def test_feature_heading_remains_evidence_that_page_mentions_feature(self):
        seed = 'https://www.hyundai.com/in/en/find-a-car/creta/highlights'
        heading = 'Voice enabled smart panoramic sunroof'
        with patch('server.crawl.fetch_public', return_value={'final_url': seed, 'sections': [{'heading': heading, 'text': heading, 'locator': 'feature'}]}):
            result = source_lookup({'tool': 'source_lookup', 'url': seed, 'query': 'Does the page mention a panoramic sunroof?'}, 'Check ' + seed, [])
        self.assertEqual(result['evidence'][0]['value'], heading)
        self.assertTrue(result['evidence'][0]['scope_unverified'])

    def test_answer_paragraph_with_trailing_question_is_not_dropped(self):
        seed = 'https://example.com/car/specification'
        passage = 'Fuel tank capacity is 50 litres. Want to know about fuel tank care?'
        with patch('server.crawl.fetch_public', return_value={'final_url': seed, 'sections': [{'heading': 'Fuel tank', 'text': passage, 'locator': 'answer'}]}):
            result = source_lookup({'tool': 'source_lookup', 'url': seed, 'query': 'fuel tank capacity'}, 'Check ' + seed, [])
        self.assertEqual(result['evidence'][0]['value'], passage)

    def test_hyphenated_model_slug_is_tokenized_like_the_question(self):
        seed = 'https://example.com/grand-vitara/highlights'
        sections = [{'heading': 'Grand Vitara', 'text': 'The Grand Vitara name appears across this model family.', 'locator': f'generic{i}'} for i in range(8)]
        sections.append({'heading': 'Cabin', 'text': 'A panoramic sunroof is available on selected trims.', 'locator': 'sunroof'})
        with patch('server.crawl._model_tokens', return_value=['grand-vitara']), patch('server.crawl.fetch_public', return_value={'final_url': seed, 'sections': sections}):
            result = source_lookup({'tool': 'source_lookup', 'url': seed, 'query': 'Grand Vitara panoramic sunroof'}, 'Check ' + seed, [])
        self.assertEqual([f['source']['locator'] for f in result['evidence']], ['sunroof'])

    def test_relevant_answer_with_contact_footer_keeps_its_full_quote(self):
        seed = 'https://example.com/car/specification'
        passage = 'Fuel tank capacity is 50 litres. Share your number to request a test drive.'
        with patch('server.crawl.fetch_public', return_value={'final_url': seed, 'sections': [{'heading': 'Fuel tank', 'text': passage, 'locator': 'answer'}]}):
            result = source_lookup({'tool': 'source_lookup', 'url': seed, 'query': 'fuel tank capacity'}, 'Check ' + seed, [])
        self.assertEqual(result['evidence'][0]['source']['quote'], passage)


if __name__ == '__main__':
    unittest.main(verbosity=2)
