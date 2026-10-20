"""Periodically synchronize Plex library counts with Discord voice channel names."""
import json
import logging
import os
import signal
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LOG = logging.getLogger('plex-discord-stats')
STOP = False


def stop(_signum, _frame):
    global STOP
    STOP = True


def env(name, default=None):
    value = os.getenv(name, default)
    if value is None or str(value).strip() == '':
        raise ValueError(f'Missing required environment variable: {name}')
    return str(value).strip()


def request_json(url, *, headers=None, method='GET', body=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(url, data=data, method=method, headers=headers or {})
    with urlopen(req, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def tautulli_counts():
    base = env('TAUTULLI_URL').rstrip('/')
    api_key = env('TAUTULLI_API_KEY')
    url = base + '/api/v2?' + urlencode({'apikey': api_key, 'cmd': 'get_libraries'})
    result = request_json(url)
    response = result.get('response', {})
    if response.get('result') != 'success':
        raise RuntimeError('Tautulli get_libraries did not succeed')
    libraries = response.get('data')
    if not isinstance(libraries, list):
        raise RuntimeError('Unexpected Tautulli library response')
    counts = {'movies': 0, 'shows': 0, 'episodes': 0}
    seen = {'movie': 0, 'show': 0}
    for library in libraries:
        kind = library.get('section_type')
        if kind == 'movie':
            counts['movies'] += int(library['count'])
            seen['movie'] += 1
        elif kind == 'show':
            counts['shows'] += int(library['count'])
            counts['episodes'] += int(library['child_count'])
            seen['show'] += 1
    if not all(seen.values()):
        raise RuntimeError('Tautulli did not return both movie and show libraries; refusing to overwrite channel names')
    return counts


def discord_request(path, *, method='GET', body=None):
    headers = {'Authorization': 'Bot ' + env('DISCORD_BOT_TOKEN'), 'User-Agent': 'PlexDiscordStats/1.0'}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    return request_json('https://discord.com/api/v10' + path, headers=headers, method=method, body=body)


def sync(counts):
    guild = env('DISCORD_GUILD_ID')
    category = env('DISCORD_CATEGORY_ID')
    mapping = {
        'movies': ('DISCORD_MOVIES_CHANNEL_ID', 'Movies'),
        'shows': ('DISCORD_SHOWS_CHANNEL_ID', 'TV Shows'),
        'episodes': ('DISCORD_EPISODES_CHANNEL_ID', 'Episodes'),
    }
    for key, (variable, label) in mapping.items():
        channel_id = env(variable)
        try:
            channel = discord_request('/channels/' + channel_id)
            if str(channel.get('guild_id')) != guild or str(channel.get('parent_id')) != category or channel.get('type') != 2:
                raise RuntimeError(f'{label}: channel is not a voice channel in the configured server/category')
            target = f'{label}: {counts[key]}'
            if channel.get('name') == target:
                LOG.info('%s unchanged', target)
                continue
            discord_request('/channels/' + channel_id, method='PATCH', body={'name': target})
            LOG.info('Updated %s', target)
        except HTTPError as exc:
            if exc.code == 429:
                retry = min(float(exc.headers.get('Retry-After', '60')), 300)
                LOG.warning('Discord rate limit for %s; retrying next cycle (suggested wait %.0fs)', label, retry)
            else:
                LOG.error('Discord error updating %s: HTTP %s', label, exc.code)
        except (URLError, ValueError, RuntimeError, KeyError) as exc:
            LOG.error('Unable to update %s: %s', label, exc)


def main():
    logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO').upper(), format='%(asctime)s %(levelname)s %(message)s')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    interval = int(env('UPDATE_INTERVAL_SECONDS', '3600'))
    if interval < 900:
        raise ValueError('UPDATE_INTERVAL_SECONDS must be at least 900 to avoid excessive Discord channel renames')
    for variable in ('TAUTULLI_URL', 'TAUTULLI_API_KEY', 'DISCORD_BOT_TOKEN', 'DISCORD_GUILD_ID', 'DISCORD_CATEGORY_ID', 'DISCORD_MOVIES_CHANNEL_ID', 'DISCORD_SHOWS_CHANNEL_ID', 'DISCORD_EPISODES_CHANNEL_ID'):
        env(variable)
    LOG.info('Starting library stats sync (interval: %ds)', interval)
    while not STOP:
        try:
            counts = tautulli_counts()
            LOG.info('Library totals: %s', counts)
            sync(counts)
        except (HTTPError, URLError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            LOG.error('Sync failed; keeping existing channel names: %s', exc)
        for _ in range(interval):
            if STOP:
                break
            time.sleep(1)
    LOG.info('Stopped')


if __name__ == '__main__':
    main()
