# -*- coding: utf-8 -*-

import logging
import traceback
import bottle
import requests
import urllib

ORIGIN = 'http://ali2upyunmaster.r.aicdn.com'
HOST = 'downloadapk02.sdk.mobileztgame.com'

def file_get_size(path):
    resp = requests.head(ORIGIN + path, headers={'Host': HOST})
    resp.raise_for_status()
    bottle.response.content_type = resp.headers.get('content-type')
    bottle.response.set_header('cache-control', resp.headers.get('cache-control'))
    return resp, int(resp.headers.get('content-length'))

def file_get_range(path, size, begin, end):
    logging.getLogger().info('file get {}, size: {}, range: [{}, {})'.format(path, size, begin, end))
    if end > size:
        end = size
    resp = requests.get(ORIGIN + path, headers={
        'Host': HOST,
        'Range': 'bytes={}-{}'.format(begin, end-1)})
    resp.raise_for_status()
    return resp.content

def parse_range(r):
    parts = r.split('=')
    if len(parts) != 2:
        raise Exception('invalid range: {}'.format(r))
    rg = parts[1].split('-')
    if len(rg) != 2:
        raise Exception('invalid range: {}'.format(r))
    if rg[1] == '' and rg[0] != '':
        return int(rg[0]), None

    return int(rg[0]), int(rg[1]) + 1

def parse_path(path):
    parts = path.split('/')
    bucket = parts[1]
    object = '/'.join(parts[2:])
    return bucket, object

def get_range_part(request):
    logger = logging.getLogger()

    rg = request.get_header('range')
    pos = request.query.get('pos')
    remove = request.query.get('remove')
    append = request.query.get('append')

    if remove is None:
        remove = 0
    else:
        remove = int(remove)
    if append is None:
        append = b''
    else:
        append = bytes(append, 'latin1')

    logger.info('range: {}, pos: {}, remove: {}, append: {}, append size: {}'.format(rg, pos, remove, append, len(append)))

    begin, end = parse_range(rg) # [0, 10) not include 10
    context = request.environ.get('fc.context')
    q = dict(request.query).copy()
    for k in ['pos', 'remove', 'append']:
        q.pop(k, None)
    path = request.path+'?'+urllib.parse.urlencode(q)
    resp, size = file_get_size(path)
    if resp.status_code >= 300:
        bottle.response.status = resp.status_code
        for k, v in resp.headers.items():
            bottle.response.set_header(k, v)
        return
    new_size = size - remove + len(append)
    if end is None or end > new_size:
        end = new_size
    bottle.response.set_header('Content-Range', 'bytes {}-{}/{}'.format(begin, end-1, new_size))
    bottle.response.set_header('Content-Length', end-begin)

    if pos is None:
        pos = size - remove
    else:
        pos = int(pos) - remove
    if pos < 0 or pos > size:
        raise Exception('invalid pos: {}'.format(pos))

    res = b''
    pa = pos + len(append)
    delta = len(append) - remove
    logger.info('pos: {}, remove: {}, append size: {}, delta: {}'.format(pos, remove, len(append), delta))

    if begin < pos: # part left
        res += file_get_range(path, size, begin, min(end, pos))
    if end > pos: # part middle
        start = max(begin, pos)-pos
        endx = min(end, pa)-pos
        if start < len(append):
            logger.info('append size: {}, get range [{}, {})'.format(len(append), start, endx))
            res += append[start : endx]
    if end > pa: # part right
        res += file_get_range(path, size, max(begin, pa)-delta, end-delta)

    return res

@bottle.route('/<mypath:path>', method='GET')
def index(mypath):
    try:
        bottle.response.status = 206
        return get_range_part(bottle.request)
    except Exception as ex:
        bottle.response.content_type = 'text/plain'
        logging.getLogger().error('ERROR: ' + traceback.format_exc())
        return 'ERROR: ' + traceback.format_exc()
        return str(ex)

handler = bottle.default_app()

if __name__ == "__main__":
    bottle.run(host='0.0.0.0', port=8080)
