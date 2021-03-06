from aiohttp import (
    ClientTimeout,
    ClientSession,
    ClientResponseError
)
from play_scraper import (
    utils,
    lists,
    settings
)
from urllib.parse import quote_plus
from bs4 import BeautifulSoup, SoupStrainer
from pydash import omit as omit_
import logging as log

UNWANTED_KEYS = [
    'description_html',
    'screenshots',
    'video'
]

MAX_PAGE_SIZE_FOR_SEARCH = len(settings.PAGE_TOKENS) - 1

def prune_data(data):
    if isinstance(data, dict):
        return omit_(data, *UNWANTED_KEYS)
    elif isinstance(data, list):
        return list(map(prune_data, data))
    else:
        return data

class PlayFetch():

    def __init__(self, persist=False, headers=utils.default_headers(), timeout=30, hl='en', gl='us'):
        log.info('*** inside PlayFetch.__init__ ***')
        self._headers = headers
        self._timeout = ClientTimeout(total=timeout)
        self._params = dict(
            hl=hl,
            gl=gl
        )
        self._persist = persist

    async def __aenter__(self):
        log.info('*** inside PlayFetch.__aenter__ ***')
        self._session = ClientSession(
            headers=self._headers,
            timeout=self._timeout
        )
        return self

    async def __aexit__(self, *err):
        log.info('*** inside PlayFetch.__aexit__ ***')
        if not self._persist:
            await self._session.close()
            self._session = None

    async def force_close(self):
        log.info('*** forcefully closing session ***')
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except:
                log.warning('### session already closed ###')
            finally:
                self._session = None

    async def send_request(self, method, url, data=None, params={}, allow_redirects=False):
        req_args = dict(
            method=method,
            url=url,
            params=params,
            data=utils.generate_post_data() if not data and method == 'POST' else data,
            allow_redirects=allow_redirects
        )

        async with self._session.request(**req_args) as response:
            response.raise_for_status()
            return await response.text()
    
    async def details(self, app_id):
        url = utils.build_url('details', app_id)
        try:
            response = await self.send_request('GET', url, params=self._params)
            soup = BeautifulSoup(response, 'lxml')
        except ClientResponseError as e:
            raise ValueError('INVALID_APPLICATION_ID: {app}. {error}'.format(
                app=app_id,
                error=e
            ))
        app_json = utils.parse_app_details(soup)
        app_json.update({
            'app_id': app_id,
            'url': url
        })
        return prune_data(app_json)

    async def collection(self, coln_id, catg_id=None, results=None, page=None):
        coln_name = coln_id if coln_id.startswith('promotion') else lists.COLLECTIONS.get(coln_id)
        if coln_name is None:
            raise ValueError('INVALID_COLLECTION_ID: {coln}'.format(
                coln=coln_id
            ))

        catg_name = '' if catg_id is None else lists.CATEGORIES.get(catg_id)
        if catg_name is None:
            raise ValueError('INVALID_CATEGORY_ID: {catg}'.format(
                catg=catg_id
            ))
        results = settings.NUM_RESULTS if results is None else results
        if results > 120:
            raise ValueError('Number of results cannot be more than 120.')

        page = 0 if page is None else page
        if page * results > 500:
            raise ValueError('Start (page * results) cannot be greater than 500.')

        url = utils.build_collection_url(catg_name, coln_name)
        data = utils.generate_post_data(results, page)
        try:
            response = await self.send_request('POST', url, data, params=self._params)
            soup = BeautifulSoup(response, 'lxml')
        except ClientResponseError as e:
            raise ValueError('INVALID_COLLECTION_OR_CATEGORY_ID: {coln}; {catg} {error}'.format(
                coln=coln_id,
                catg=catg_id,
                error=e
            ))
        apps = list(map(
            utils.parse_card_info, 
            soup.select('div[data-uitype="500"]')
        ))
        # TODO: soup parsing failing for certain scenarios
        # $ref: Exception #1 @ observed_error.log
        return prune_data(apps)

    async def similar(self, app_id):
        url = utils.build_url('similar', app_id)
        try:
            response = await self.send_request('GET', url, params=self._params, allow_redirects=True)
            soup = BeautifulSoup(response, 'lxml')
        except ClientResponseError as e:
            raise ValueError('INVALID_APPLICATION_ID: {app}. {error}'.format(
                app=app_id,
                error=e
            ))
        apps = list(map(
            utils.parse_card_info, 
            soup.select('div[data-uitype="500"]')
        ))
        return prune_data(apps)

    async def search(self, token, results=None, page=0):
        if page > MAX_PAGE_SIZE_FOR_SEARCH:
            raise ValueError('Page value [{page}] must be between 0 and {page_limit}'.format(
                page=page,
                page_limit=MAX_PAGE_SIZE_FOR_SEARCH
            ))
        url = settings.SEARCH_URL
        params = dict(
            self._params,
            q=quote_plus(token),
            c='apps'
        )
        data = utils.generate_post_data(0, 0, pagtok=settings.PAGE_TOKENS[page])
        try:
            response = await self.send_request('POST', url, data, params=params)
            soup = BeautifulSoup(response, 'lxml')
        except ClientResponseError as e:
            raise ValueError('INVALID_TOKEN: {app}. {error}'.format(
                token=token,
                error=e
            ))
        apps = list(map(
            utils.parse_card_info, 
            soup.select('div[data-uitype="500"]')
        ))
        return prune_data(apps)