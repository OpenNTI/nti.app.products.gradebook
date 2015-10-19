#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory(__name__)

from zope import component

from nti.zope_catalog.interfaces import IMetadataCatalog

from .index import CATALOG_NAME

def get_grade_catalog():
	return component.queryUtility(IMetadataCatalog, name=CATALOG_NAME)
