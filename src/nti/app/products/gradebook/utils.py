# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

## META classes

from nti.mimetype.mimetype import MIME_BASE

GRADEBOOK_MIME_BASE = MIME_BASE + b'.gradebook'

class MetaGradeBookObject(type):

    def __new__(cls, name, bases, dct):
        t = type.__new__(cls, name, bases, dct)
        if not hasattr(cls, 'mimeType'):
            clazzname = getattr(cls, '__external_class_name__', name)
            clazzname = b'.' + clazzname.encode('ascii').lower()
            t.mime_type = t.mimeType = GRADEBOOK_MIME_BASE + clazzname
        t.parameters = dict()
        return t

## JSON Errors

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

## GradeBook

def mark_btree_bucket_as_changed(grade):
    # Now, because grades are not persistent objects,
    # the btree bucket containing this grade has to be
    # manually told that its contents have changed.
    # XXX: Note that this is very expensive,
    # waking up each bucket of the tree.
    column = grade.__parent__
    btree = column._SampleContainer__data
    bucket = btree._firstbucket
    found = False
    while bucket is not None:
        if bucket.has_key(grade.__name__):
            bucket._p_changed = True
            if bucket._p_jar is None: # The first bucket is stored special
                btree._p_changed = True
            found = True
            break
        bucket = bucket._next
    if not found:
        # before there are buckets, it might be inline data?
        btree._p_changed = True
    return found
