# -*- coding: utf-8 -*-
"""
utils module

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

import sys
import simplejson as json

from pyramid import httpexceptions as hexc

def _json_error_map(o):
    result = list(o) if isinstance(o, set) else unicode(o)
    return result

def raise_json_error(request, factory, v, tb=None):
    """
    Attempts to raise an error during processing of a pyramid request.
    We expect the client to specify that they want JSON errors.

    :param v: The detail message. Can be a string or a dictionary. A dictionary
        may contain the keys `field`, `message` and `code`.
    :param factory: The factory (class) to produce an HTTP exception.
    :param tb: The traceback from `sys.exc_info`.
    """
    mts = (b'application/json', b'text/plain')
    accept_type = b'application/json'
    if getattr(request, 'accept', None):
        accept_type = request.accept.best_match(mts)

    if accept_type == b'application/json':
        try:
            v = json.dumps(v, ensure_ascii=False, default=_json_error_map)
        except TypeError:
            v = json.dumps({'UnrepresentableError': unicode(v) })
    else:
        v = unicode(v)

    result = factory()
    result.text = v
    result.content_type = accept_type
    raise result, None, tb

def raise_field_error(request, field, message):
    exc_info = sys.exc_info()
    data = {u'field':field, u'message': message}
    raise_json_error(request, hexc.HTTPUnprocessableEntity, data, exc_info[2])
