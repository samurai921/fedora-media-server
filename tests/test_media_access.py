import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'scripts/prepare-media-access.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class MediaAccessTests(unittest.TestCase):
    def fixture(self, side):
        return json.loads((ROOT / f'deploy/xray-jellyfin/{side}/config.example.json').read_text())

    def test_fedora_keeps_transport_and_jellyfin_unchanged(self):
        original = self.fixture('fedora')
        snapshot = copy.deepcopy(original)
        result = prepare.prepare_config(original, 'fedora')
        self.assertEqual(original, snapshot)
        self.assertEqual(result['outbounds'][:len(original['outbounds'])], original['outbounds'])
        rules = result['routing']['rules']
        self.assertEqual({r['port'] for r in rules[:-1]}, {'8096,18096', '7878,17878', '8989,18989', '9696,19696', '5055,15055'})
        for r in rules[:-1]:
            self.assertEqual(r['ip'], ['127.0.0.1/32'])
            self.assertEqual(r['network'], 'tcp')
        self.assertEqual(rules[-1]['outboundTag'], 'block-default')
        # Unlisted ports, non-loopback targets and UDP must reach the deny rule.
        for address, port, network in [('127.0.0.1', 22, 'tcp'), ('192.0.2.1', 7878, 'tcp'), ('127.0.0.1', 7878, 'udp')]:
            matched = next((r for r in rules[:-1] if address == '127.0.0.1'
                            and str(port) in r['port'].split(',') and network == r['network']), rules[-1])
            self.assertEqual(matched['outboundTag'], 'block-default')

    def test_vps_keeps_existing_listeners_and_credentials(self):
        original = self.fixture('vps')
        result = prepare.prepare_config(original, 'vps')
        self.assertEqual(result['inbounds'][:len(original['inbounds'])], original['inbounds'])
        for inbound, (_, target, listen) in zip(result['inbounds'][len(original['inbounds']):], prepare.APPS):
            self.assertEqual(inbound['listen'], '127.0.0.1')
            self.assertEqual(inbound['port'], listen)
            self.assertEqual(inbound['settings']['address'], '127.0.0.1')
            self.assertEqual(inbound['settings']['port'], target)

    def test_conflicting_listener_is_rejected(self):
        original = self.fixture('vps')
        original['inbounds'].append({'tag': 'other', 'port': 17878})
        with self.assertRaises(ValueError):
            prepare.prepare_config(original, 'vps')

    def test_changed_routing_is_not_overwritten(self):
        for side in ['fedora', 'vps']:
            original = self.fixture(side)
            original['routing']['rules'].append({'outboundTag': 'custom'})
            with self.assertRaises(ValueError):
                prepare.prepare_config(original, side)

    def test_live_config_without_default_blocker(self):
        for side in ['fedora', 'vps']:
            original = self.fixture(side)
            original['outbounds'] = [x for x in original['outbounds'] if x.get('tag') != 'block-default']
            snapshot = copy.deepcopy(original)
            result = prepare.prepare_config(original, side)
            self.assertEqual(original, snapshot)
            self.assertEqual(result['outbounds'][0]['protocol'], 'blackhole')
            for outbound in original['outbounds']:
                self.assertIn(outbound, result['outbounds'])

    def test_original_jellyfin_wire_port_is_preserved(self):
        original = self.fixture('vps')
        original['inbounds'][1]['settings']['port'] = 18096
        result = prepare.prepare_config(original, 'vps')
        self.assertEqual(result['inbounds'][1], original['inbounds'][1])
        client = prepare.prepare_config(self.fixture('fedora'), 'fedora')
        self.assertIn('18096', client['routing']['rules'][0]['port'].split(','))

    def test_legacy_jellyfin_entry_without_destination_is_preserved(self):
        original = self.fixture('vps')
        original['inbounds'][1]['tag'] = 'jellyfin-entry'
        original['inbounds'][1]['settings'] = {'network': 'tcp'}
        original['routing']['rules'][0]['inboundTag'] = ['jellyfin-entry']
        result = prepare.prepare_config(original, 'vps')
        self.assertEqual(result['inbounds'][1], original['inbounds'][1])

    def test_rerun_requires_review(self):
        for side in ['fedora', 'vps']:
            result = prepare.prepare_config(self.fixture(side), side)
            with self.assertRaises(ValueError):
                prepare.prepare_config(result, side)


if __name__ == '__main__':
    unittest.main()
