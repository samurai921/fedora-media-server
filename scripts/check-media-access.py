#!/usr/bin/env python3
"""Check app login gates locally or through the published HTTPS domains."""
import argparse
import sys
import urllib.error
import urllib.parse
import urllib.request

APPS = (
    ('Radarr', 'radarr', 7878, '/api/v3/system/status'),
    ('Sonarr', 'sonarr', 8989, '/api/v3/system/status'),
    ('Prowlarr', 'prowlarr', 9696, '/api/v1/system/status'),
    ('Jellyseerr', 'requests', 5055, '/api/v1/auth/me'),
)


def response(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as result:
            return result.status, result.url
    except urllib.error.HTTPError as error:
        return error.code, error.url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', action='store_true', help='Check DNS and TLS via the four domains')
    args = parser.parse_args()
    failures = 0
    for name, subdomain, port, api in APPS:
        base = f'https://{subdomain}.mediadima.ru' if args.public else f'http://127.0.0.1:{port}'
        try:
            status, final_url = response(base + '/')
            api_status, api_url = response(base + api)
            if urllib.parse.urlparse(final_url).netloc != urllib.parse.urlparse(base).netloc:
                raise ValueError('Unexpected cross-host redirect')
            if urllib.parse.urlparse(api_url).path != api or api_status != 401:
                raise ValueError(f'Protected API must return 401 without credentials (got {api_status})')
            if status != 200:
                raise ValueError(f'Login page is unavailable (HTTP {status})')
            if subdomain != 'requests' and urllib.parse.urlparse(final_url).path.rstrip('/') != '/login':
                raise ValueError('Expected redirect to /login')
            print(f'OK {name}: login page available; anonymous API denied; {base}')
        except (OSError, ValueError) as error:
            failures += 1
            print(f'FAIL {name}: {error}', file=sys.stderr)
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
