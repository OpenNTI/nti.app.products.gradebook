#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.app.products.gradebook.utils.gradebook import save_in_container
from nti.app.products.gradebook.utils.gradebook import remove_from_container
from nti.app.products.gradebook.utils.gradebook import mark_btree_bucket_as_changed
from nti.app.products.gradebook.utils.gradebook import record_grade_without_submission
from nti.app.products.gradebook.utils.gradebook import set_grade_by_assignment_history_item

from nti.dataserver.interfaces import IUsernameSubstitutionPolicy

from nti.mimetype.mimetype import MIME_BASE

#: Gradebook Base MimeType
GRADEBOOK_MIME_BASE = MIME_BASE + '.gradebook'


class MetaGradeBookObject(type):

    def __new__(cls, name, bases, dct):
        cls = type.__new__(cls, name, bases, dct)
        ancestor = object
        for ancestor in cls.mro():
            if 'mimeType' in ancestor.__dict__:
                break
        if ancestor is not cls:
            clazzname = '.' + name.encode('ascii').lower()
            cls.mime_type = cls.mimeType = GRADEBOOK_MIME_BASE + clazzname
            cls.parameters = dict()
        return cls


def replace_username(username):
    substituter = component.queryUtility(IUsernameSubstitutionPolicy)
    if substituter is None:
        return username
    result = substituter.replace(username) or username
    return result
