# coding=utf-8
# Author: Ludovic Reenaers <ludovic.reenaers@gmail.com>
#
# URL: https://sickrage.ca
#
# This file is part of SickRage.
#
# SickRage is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickRage is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickRage. If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function, unicode_literals

import re
from urlparse import urljoin

import sickrage
from sickrage.core.caches.tv_cache import TVCache
from sickrage.core.helpers import bs4_parser, try_int, convert_size, validate_url
from sickrage.providers import TorrentProvider


class Torrent9Provider(TorrentProvider):
    def __init__(self):
        super(Torrent9Provider, self).__init__('Torrent9', 'ww1.torrent9.ph', False)

        self.urls.update({
            'search': '{base_url}/search_torrent/'.format(**self.urls),
            'rss': '{base_url}/torrents_series.html,trie-date-d'.format(**self.urls),
            'download': '{base_url}get_torrent/%s.torrent'.format(**self.urls)
        })

        self.minseed = None
        self.minleech = None

        self.custom_url = ""

        self.proper_strings = ['PROPER', 'REPACK']

        self.cache = TVCache(self, min_time=20)

    def search(self, search_strings, age=0, ep_obj=None, **kwargs):  # pylint: disable=too-many-locals
        results = []

        for mode in search_strings:
            sickrage.app.log.debug("Search Mode: {0}".format(mode))
            for search_string in search_strings[mode]:
                if mode == 'Season':
                    search_string = re.sub(r'(.*)S0?', r'\1Saison ', search_string)

                if mode != 'RSS':
                    sickrage.app.log.debug("Search string: {}".format(search_string))
                    search_query = re.sub(r'\W', '-', search_string)
                    search_url = urljoin(self.urls['search'], "{search_query}.html".format(search_query=search_query))
                else:
                    search_url = self.urls['rss']

                if self.custom_url:
                    if not validate_url(self.custom_url):
                        sickrage.app.log.warning("Invalid custom url: {}".format(self.custom_url))
                        return results
                    search_url = urljoin(self.custom_url, search_url.split(self.urls['base_url'])[1])

                try:
                    data = self.session.get(search_url).text
                    results += self.parse(data, mode)
                except Exception:
                    sickrage.app.log.debug("No data returned from provider")

        return results

    def parse(self, data, mode, **kwargs):
        """
        Parse search results from data
        :param data: response data
        :param mode: search mode
        :return: search results
        """

        results = []

        with bs4_parser(data) as html:
            table_body = html.find('tbody')

            # Continue only if at least one release is found
            if not table_body:
                sickrage.app.log.debug('Data returned from provider does not contain any torrents')
                return results

            for row in table_body('tr'):
                cells = row('td')
                if len(cells) < 4:
                    continue

                try:
                    info_cell = cells[0].a
                    title = info_cell.get_text()
                    download_url = info_cell.get('href')
                    if not all([title, download_url]):
                        continue

                    title = '{name} {codec}'.format(name=title, codec='x264')

                    download_name = download_url.rsplit('/', 1)[1]
                    download_url = self.urls['download'] % download_name
                    if self.custom_url:
                        if not validate_url(self.custom_url):
                            sickrage.app.log.warning("Invalid custom url: {}".format(self.custom_url))
                            return results
                        download_url = urljoin(self.custom_url, download_url.split(self.urls['base_url'])[1])

                    seeders = try_int(cells[2].get_text(strip=True))
                    leechers = try_int(cells[3].get_text(strip=True))

                    torrent_size = cells[1].get_text()
                    size = convert_size(torrent_size, -1, ['O', 'KO', 'MO', 'GO', 'TO', 'PO'])

                    results += [{
                        'title': title,
                        'link': download_url,
                        'size': size,
                        'seeders': seeders,
                        'leechers': leechers
                    }]

                    if mode != 'RSS':
                        sickrage.app.log.debug("Found result: {}".format(title))
                except Exception:
                    sickrage.app.log.error("Failed parsing provider")

        return results
