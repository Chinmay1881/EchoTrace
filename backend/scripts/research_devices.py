"""Read-only PortAudio enumeration/settings checks. Never opens a recording stream."""
import json
import sounddevice as sd


def capabilities():
    devices, apis = list(sd.query_devices()), list(sd.query_hostapis())
    rows = []
    for index, device in enumerate(devices):
        if device['max_input_channels'] <= 0:
            continue
        row = {'index': index, 'name': device['name'],
               'host_api': apis[device['hostapi']]['name'],
               'max_input_channels': device['max_input_channels'],
               'default_sample_rate': device['default_samplerate'], 'stereo_rate_checks': {}}
        for rate in (16000, 32000, 44100, 48000, 96000):
            try:
                sd.check_input_settings(device=index, channels=2, samplerate=rate, dtype='float32')
                row['stereo_rate_checks'][str(rate)] = 'accepted settings (capture unverified)'
            except Exception as exc:
                row['stereo_rate_checks'][str(rate)] = f'rejected: {exc}'
        rows.append(row)
    return {'portaudio': list(sd.get_portaudio_version()), 'host_apis': apis,
            'default_device': list(sd.default.device), 'input_devices': rows,
            'physical_stereo': 'unverified; settings support does not establish separate microphones',
            'capture_performed': False}


if __name__ == '__main__':
    print(json.dumps(capabilities(), indent=2))
