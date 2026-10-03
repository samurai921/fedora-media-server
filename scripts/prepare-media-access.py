#!/usr/bin/env python3
"""Prepare an offline candidate for the isolated media Xray; never deploy it."""
import argparse
import copy
import json
import os
from pathlib import Path

APPS = (('radarr', 7878, 17878), ('sonarr', 8989, 18989),
        ('prowlarr', 9696, 19696), ('requests', 5055, 15055))


def prepare_config(original, side):
    config = copy.deepcopy(original)
    outbounds = config.setdefault('outbounds', [])
    blockers = [x for x in outbounds if x.get('tag') == 'block-default']
    if blockers and (len(blockers) != 1 or blockers[0].get('protocol') != 'blackhole'):
        raise ValueError('Conflicting block-default outbound; review manually')
    if blockers:
        outbounds.remove(blockers[0])
    outbounds.insert(0, blockers[0] if blockers else {'tag': 'block-default', 'protocol': 'blackhole', 'settings': {}})
    rules = config.get('routing', {}).get('rules', [])
    if side == 'fedora':
        expected = {'type': 'field', 'inboundTag': ['reverse-in'], 'outboundTag': 'jellyfin-local'}
        if rules != [expected]:
            raise ValueError('Fedora routing differs from the Jellyfin-only template; review manually')
        reverse = next((x for x in outbounds if x.get('protocol') == 'vless' and x.get('settings', {}).get('reverse', {}).get('tag') == 'reverse-in'), {})
        jellyfin = next((x for x in outbounds if x.get('tag') == 'jellyfin-local'), {})
        if reverse.get('settings', {}).get('reverse', {}).get('tag') != 'reverse-in':
            raise ValueError('Expected the dedicated reverse-in client')
        if jellyfin.get('settings', {}).get('redirect') != '127.0.0.1:8096':
            raise ValueError('Unexpected Jellyfin destination; review manually')
        tags = {x.get('tag') for x in outbounds}
        new_rules = []
        for name, port, wire_port in (('jellyfin', 8096, 18096), *APPS):
            new_rules.append({'type': 'field', 'inboundTag': ['reverse-in'],
                              'network': 'tcp', 'ip': ['127.0.0.1/32'],
                              'port': f'{port},{wire_port}', 'outboundTag': name + '-local'})
            if name == 'jellyfin':
                continue
            if name + '-local' in tags:
                raise ValueError('An application outbound already exists; review manually')
            outbounds.append({'tag': name + '-local', 'protocol': 'freedom', 'settings': {
                'redirect': f'127.0.0.1:{port}',
                'finalRules': [{'action': 'allow', 'network': 'tcp', 'ip': '127.0.0.1', 'port': str(port)}]}})
        new_rules.append({'type': 'field', 'inboundTag': ['reverse-in'], 'outboundTag': 'block-default'})
        config['routing']['rules'] = new_rules
    elif side == 'vps':
        inbounds = config.get('inbounds', [])
        jellyfin = next((x for x in inbounds if x.get('listen') == '127.0.0.1' and x.get('port') == 18096), {})
        expected = {'type': 'field', 'inboundTag': [jellyfin.get('tag')], 'outboundTag': 'reverse-out'}
        if rules != [expected]:
            raise ValueError('VPS routing differs from the Jellyfin-only template; review manually')
        inbounds = config.get('inbounds', [])
        # Preserve the existing, health-checked Jellyfin listener verbatim.
        # Its legacy settings may omit a destination and use the entry port.
        if jellyfin.get('listen') != '127.0.0.1' or jellyfin.get('port') != 18096:
            raise ValueError('Expected the private Jellyfin listener')
        if not any(c.get('reverse', {}).get('tag') == 'reverse-out'
                   for x in inbounds for c in x.get('settings', {}).get('clients', [])):
            raise ValueError('Expected the dedicated reverse-out server')
        tags = {x.get('tag') for x in inbounds}
        ports = {str(x.get('port')) for x in inbounds}
        for name, target, listen_port in APPS:
            tag = name + '-tunnel'
            if tag in tags or str(listen_port) in ports:
                raise ValueError('An application listener or port already exists; review manually')
            inbounds.append({'tag': tag, 'listen': '127.0.0.1', 'port': listen_port,
                             'protocol': 'tunnel', 'settings': {
                                 'address': '127.0.0.1', 'port': target, 'network': 'tcp'}})
        rules.append({'type': 'field', 'inboundTag': [name + '-tunnel' for name, _, _ in APPS],
                      'outboundTag': 'reverse-out'})
    else:
        raise ValueError('Unknown side')
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--side', choices=['fedora', 'vps'], required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError('Input and output must be different files')
        candidate = prepare_config(json.loads(args.input.read_text()), args.side)
        encoded = (json.dumps(candidate, indent=2, ensure_ascii=False) + '\n').encode()
        # O_EXCL also refuses an existing symlink. Real credentials stay in a 0600 file.
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as output:
            output.write(encoded)
    except (OSError, ValueError) as error:
        # Do not print config contents or credentials.
        parser.exit(1, f'Candidate not created: {error}\n')
    print('Candidate created with mode 0600. Live configuration and services are unchanged.')


if __name__ == '__main__':
    main()
