#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

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

## rexport for BWC

from .errors import _json_error_map
from .errors import raise_json_error
from .errors import raise_field_error

from .gradebook import mark_btree_bucket_as_changed
from .gradebook import record_grade_without_submission
