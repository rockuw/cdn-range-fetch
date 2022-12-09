import requests
import random
from urllib.parse import unquote

OLD_URL = 'https://downloadapk02.sdk.mobileztgame.com/packages/5174/ztgame-v1.0.4.apk?fcl=91355108&fal=22'
FC_URL = 'https://fetch-cdn-range-fetch-vxurwcvmkn.cn-hangzhou.fcapp.run/packages/5174/ztgame-v1.0.4.apk?fcl=91355108&fal=22'

def req(url, pos, remove, append, begin, end):
    if end == -1:
        end = ''
    req_url = '{}&remove={}&append={}&pos={}'.format(url, remove, append, pos)
    resp = requests.get(req_url, headers={'Range': 'bytes={}-{}'.format(begin, end)})
    resp.raise_for_status()
    return resp, req_url

def random_input():
    pos = random.randint(1, 290816520)
    remove = random.randint(1, 1024*1024)
    append = ''
    append_size = random.randint(1, 1024)
    for i in range(append_size):
        append += '%%%02X' % random.randint(0, 255)
    begin = random.randint(pos-remove-256, pos-remove+append_size+256)
    end = begin + random.randint(1, 512*1024)
    return [pos, remove, append, begin, end]

def test():
    cases = [
        [2, 2, '12345', 0, 99],
        [2, 2, '12345', 290816520-1024, -1]
    ]
    print('generating cases ...')
    for x in range(20):
        cases.append(random_input())

    print('testing cases ...')
    for i, cs in enumerate(cases):
        pos, remove, append, begin, end = cs
        append_size = len(unquote(append))
        print('testing case {}, pos={}, remove={}, append={} ...'.format(i, pos, remove, append_size))
        print(dict(sorted({'begin': begin,
        'end': end,
        'left': pos-remove,
        'right': pos-remove+append_size}.items(), key=lambda item: item[1])))
        resp_old, url_old = req(OLD_URL, pos, remove, append, begin, end)
        resp_fc, url_fc = req(FC_URL, pos, remove, append, begin, end)

        if resp_old.status_code != resp_fc.status_code:
            raise Exception('status code not match: {}'.format([resp_old.status_code, resp_fc.status_code]))

        if resp_old.headers.get('content-type') != resp_fc.headers.get('content-type'):
            raise Exception('content-type not match: {}'.format([resp_old.headers.get('content-type'), resp_fc.headers.get('content-type')]))

        cr_old = resp_old.headers.get('content-range')
        cr_fc = resp_fc.headers.get('content-range')
        if cr_old != cr_fc:
            raise Exception('content-range not match: {}'.format([begin, end, cr_old, cr_fc, url_old, url_fc]))

        if resp_old.content != resp_fc.content:
            raise Exception('content not match: {}'.format([begin, end, url_old, url_fc]))
        print('PASS. Content-Range: {}'.format(cr_fc))
        print('')

if __name__ == '__main__':
    test()