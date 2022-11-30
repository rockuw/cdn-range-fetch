# -*- coding: utf-8 -*-

import logging
import traceback
import bottle
import oss2
import os

def oss_client(context, bucket):
    creds = context.credentials
    auth = oss2.StsAuth(creds.accessKeyId,
                        creds.accessKeySecret, creds.securityToken)
    internal = '-internal'
    if os.getenv('LOCAL_DEBUG') != "":
        internal = ''
    endpoint = 'oss-{}{}.aliyuncs.com'.format(context.region, internal)
    client = oss2.Bucket(auth, endpoint, bucket)
    return client

def oss_get_range(client, object, size, begin, end):
    logging.getLogger().info('oss get {}, size: {}, range: [{}, {})'.format(object, size, begin, end))
    if end > size:
        end = size
    return client.get_object(object, byte_range=[begin, end-1]).read()

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
    logger.info('range: {}, pos: {}, remove: {}, append: {}, append size: {}'.format(rg, pos, remove, append, len(append)))

    if remove is None:
        remove = 0
    else:
        remove = int(remove)
    if append is None:
        append = b''
    else:
        append = bytes(append, 'ascii')

    begin, end = parse_range(rg) # [0, 10) not include 10
    context = request.environ.get('fc.context')
    path = request.path
    bucket, object = parse_path(path)
    client = oss_client(context, bucket)
    meta = client.get_object_meta(object)
    size = meta.content_length
    new_size = size - remove + len(append)
    if end is None or end > new_size:
        end = new_size
    bottle.response.set_header('Content-Range', 'bytes {}-{}/{}'.format(begin, end-1, new_size))
    bottle.response.set_header('Content-Lengh', end-begin)

    if pos is None:
        pos = size - remove
    else:
        pos = int(pos)
    if pos < 0 or pos > size:
        raise Exception('invalid pos: {}'.format(pos))

    res = b''
    pa = pos + len(append)

    delta = len(append) - remove
    if begin < pos: # part left
        res += oss_get_range(client, object, size, begin, min(end, pos))
    if end > pos: # part middle
        start = max(begin, pos)-pos
        endx = min(end, pa)-pos
        if start < len(append):
            logger.info('append size: {}, get range [{}, {})'.format(len(append), start, endx))
            res += append[start : endx]
    if end > pa: # part right
        res += oss_get_range(client, object, size, max(begin, pa)-delta, end-delta)

    return res

@bottle.route('/<mypath:path>', method='GET')
def index(mypath):
    try:
        return get_range_part(bottle.request)
    except Exception as ex:
        bottle.response.content_type = 'text/plain'
        logging.getLogger().error('ERROR: ' + traceback.format_exc())
        return 'ERROR: ' + traceback.format_exc()
        return str(ex)

handler = bottle.default_app()

if __name__ == "__main__":
    bottle.run(host='0.0.0.0', port=8080)
