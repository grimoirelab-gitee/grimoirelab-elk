# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2019 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#     Alvaro del Castillo <acs@bitergia.com>
#     Valerio Cosentino <valcos@bitergia.com>
#
import logging
import unittest
import time

import requests
from base import TestBaseBackend
from grimoire_elk.raw.mattermost import MattermostOcean
from grimoire_elk.enriched.utils import REPO_LABELS
from grimoire_elk.enriched.enrich import logger, DEMOGRAPHICS_ALIAS


HEADER_JSON = {"Content-Type": "application/json"}


class TestMattermost(TestBaseBackend):
    """Test Mattermost backend"""

    connector = "mattermost"
    ocean_index = "test_" + connector
    enrich_index = "test_" + connector + "_enrich"

    def test_has_identites(self):
        """Test value of has_identities method"""

        enrich_backend = self.connectors[self.connector][2]()
        self.assertTrue(enrich_backend.has_identities())

    def test_items_to_raw(self):
        """Test whether JSON items are properly inserted into ES"""

        result = self._test_items_to_raw()
        self.assertEqual(result['items'], 89)
        self.assertEqual(result['raw'], 89)

    def test_raw_to_enrich(self):
        """Test whether the raw index is properly enriched"""

        result = self._test_raw_to_enrich()
        self.assertEqual(result['raw'], 89)
        self.assertEqual(result['enrich'], 89)

        enrich_backend = self.connectors[self.connector][2]()

        for item in self.items:
            eitem = enrich_backend.get_rich_item(item)
            self.assertEqual(eitem['channel_name'], "Eclipse Che")

    def test_enrich_repo_labels(self):
        """Test whether the field REPO_LABELS is present in the enriched items"""

        self._test_raw_to_enrich()
        enrich_backend = self.connectors[self.connector][2]()

        for item in self.items:
            eitem = enrich_backend.get_rich_item(item)
            self.assertIn(REPO_LABELS, eitem)

    def test_raw_to_enrich_sorting_hat(self):
        """Test enrich with SortingHat"""

        result = self._test_raw_to_enrich(sortinghat=True)
        self.assertEqual(result['raw'], 89)
        self.assertEqual(result['enrich'], 89)

        enrich_backend = self.connectors[self.connector][2]()

        url = self.es_con + "/" + self.enrich_index + "/_search"
        response = enrich_backend.requests.get(url, verify=False).json()
        for hit in response['hits']['hits']:
            source = hit['_source']
            if 'author_uuid' in source:
                self.assertIn('author_domain', source)
                self.assertIn('author_gender', source)
                self.assertIn('author_gender_acc', source)
                self.assertIn('author_org_name', source)
                self.assertIn('author_bot', source)
                self.assertIn('author_multi_org_names', source)

    def test_raw_to_enrich_projects(self):
        """Test enrich with Projects"""

        result = self._test_raw_to_enrich(projects=True)
        self.assertEqual(result['raw'], 89)
        self.assertEqual(result['enrich'], 89)

        res = requests.get(self.es_con + "/" + self.enrich_index + "/_search", verify=False)
        for eitem in res.json()['hits']['hits']:
            self.assertEqual(eitem['_source']['project'], "grimoire")

    def test_copy_raw_fields(self):
        """Test copied raw fields"""

        self._test_raw_to_enrich()
        enrich_backend = self.connectors[self.connector][2]()

        for item in self.items:
            eitem = enrich_backend.get_rich_item(item)
            for attribute in enrich_backend.RAW_FIELDS_COPY:
                if attribute in item:
                    self.assertEqual(item[attribute], eitem[attribute])
                else:
                    self.assertIsNone(eitem[attribute])

    def test_refresh_identities(self):
        """Test refresh identities"""

        result = self._test_refresh_identities()
        # ... ?

    def test_refresh_project(self):
        """Test refresh project field for all sources"""

        result = self._test_refresh_project()
        # ... ?

    def test_perceval_params_legacy_url(self):
        """Test the extraction of perceval params from an URL"""

        url = "https://chat.openshift.io 8j366ft5affy3p36987pcugaoa"
        expected_params = [
            'https://chat.openshift.io',
            '8j366ft5affy3p36987pcugaoa'
        ]
        self.assertListEqual(MattermostOcean.get_perceval_params_from_url(url), expected_params)

        url = "https://some-server-with-dashes.dev/ 993bte1an3dyjmqdgxsr8jr5kh"
        expected_params = [
            'https://some-server-with-dashes.dev',
            '993bte1an3dyjmqdgxsr8jr5kh'
        ]
        self.assertListEqual(MattermostOcean.get_perceval_params_from_url(url), expected_params)

        url = "hTtps://some-SERVER-with-dashes.dev/ 993bte1an3DYJMQDGXSR8JR5kh"
        expected_params = [
            'https://some-server-with-dashes.dev',
            '993bte1an3dyjmqdgxsr8jr5kh'
        ]
        self.assertListEqual(MattermostOcean.get_perceval_params_from_url(url), expected_params)

        # Should fail: wrong protocol
        url = "sftp://cool-mattermost.host/ 993bte1an3dyjmqdgxsr8jr5kh"
        with self.assertRaises(RuntimeError):
            MattermostOcean.get_perceval_params_from_url(url)

        # Should fail: wrong length of channel ID
        url = "https://cool-mattermost.host/ this0has0the0wrong0number0of0letters"
        with self.assertRaises(RuntimeError):
            MattermostOcean.get_perceval_params_from_url(url)

        # Should fail: bad characters in channel id
        url = "sftp://cool-mattermost.host/ 993bteεan3yjmqdgxsr8jr5kh"
        with self.assertRaises(RuntimeError):
            MattermostOcean.get_perceval_params_from_url(url)

        # Should fail: wrong number of parameters
        url = "https://cool-mattermost.host/ 993bte1an3dyjmqdgxsr8jr5kh extra_stuff"
        with self.assertRaises(RuntimeError):
            MattermostOcean.get_perceval_params_from_url(url)

    def test_perceval_params_standard_url(self):
        """Test the extraction of perceval params from an URL"""

        url = "https://my.mattermost.host/some_team/channels/some_channel"
        expected_params = [
            'https://my.mattermost.host',
            'some_channel',
            'some_team',
        ]
        self.assertListEqual(MattermostOcean.get_perceval_params_from_url(url), expected_params)

        url = "http://my-cooler-mattermost.host/team2/channels/channel2/"
        expected_params = [
            'http://my-cooler-mattermost.host',
            'channel2',
            'team2',
        ]
        self.assertListEqual(MattermostOcean.get_perceval_params_from_url(url), expected_params)

        url = "httP://my-cooler-maTTERMost.host/TRansFoRM/channels/CAPitALs/"
        expected_params = [
            'http://my-cooler-mattermost.host',
            'capitals',
            'transform',
        ]
        self.assertListEqual(MattermostOcean.get_perceval_params_from_url(url), expected_params)

        # Should fail:  Malformed host
        url = "https://malformed-host/some_team/channels/some_channel"
        with self.assertRaises(RuntimeError):
            MattermostOcean.get_perceval_params_from_url(url)

        # Should fail:  Wrong protocol
        url = "gemini://my.mattermost.host/some_team/channels/some_channel"
        with self.assertRaises(RuntimeError):
            MattermostOcean.get_perceval_params_from_url(url)

        # Should fail:  Wrong endpoint
        url = "https://my.mattermost.host/some_team/wrongnode/some_channel"
        with self.assertRaises(RuntimeError):
            MattermostOcean.get_perceval_params_from_url(url)

        # Should fail:  No channel name
        url = "https://my.mattermost.host/some_team/channels/"
        with self.assertRaises(RuntimeError):
            MattermostOcean.get_perceval_params_from_url(url)

        # Should fail:  No team name
        url = "https://my.mattermost.host/channels/some_channel"
        with self.assertRaises(RuntimeError):
            MattermostOcean.get_perceval_params_from_url(url)

        # Should fail:  Empty team name
        url = "https://my.mattermost.host//channels/some_channel"
        with self.assertRaises(RuntimeError):
            MattermostOcean.get_perceval_params_from_url(url)

        # Should fail:  Bad team name
        url = "https://my.mattermost.host/i put spaces/channels/some_channel"
        with self.assertRaises(RuntimeError):
            MattermostOcean.get_perceval_params_from_url(url)

    def test_demography_study(self):
        """ Test that the demography study works correctly """

        study, ocean_backend, enrich_backend = self._test_study('enrich_demography')

        with self.assertLogs(logger, level='INFO') as cm:
            if study.__name__ == "enrich_demography":
                study(ocean_backend, enrich_backend)
            self.assertEqual(cm.output[0], 'INFO:grimoire_elk.enriched.enrich:[mattermost] Demography '
                                           'starting study %s/test_mattermost_enrich'
                             % self.es_con)
            self.assertEqual(cm.output[-1], 'INFO:grimoire_elk.enriched.enrich:[mattermost] Demography '
                                            'end %s/test_mattermost_enrich'
                             % self.es_con)

        time.sleep(5)  # HACK: Wait until github enrich index has been written
        items = [item for item in enrich_backend.fetch()]
        self.assertEqual(len(items), 89)

        for item in items:
            if 'author_uuid' in item:
                self.assertTrue('demography_min_date' in item.keys())
                self.assertTrue('demography_max_date' in item.keys())

        r = enrich_backend.elastic.requests.get(enrich_backend.elastic.index_url + "/_alias",
                                                headers=HEADER_JSON, verify=False)
        self.assertIn(DEMOGRAPHICS_ALIAS, r.json()[enrich_backend.elastic.index]['aliases'])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    unittest.main(warnings='ignore')
