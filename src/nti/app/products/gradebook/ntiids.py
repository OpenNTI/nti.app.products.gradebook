#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NTIID resolvers

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.contenttypes.courses.interfaces import ICourseCatalog

from nti.ntiids.ntiids import get_specific
from nti.ntiids.interfaces import INTIIDResolver

from .interfaces import IGradeBook

def get_course(catalog, key):
	for course in catalog.iterCatalogEntries():
		if course.__name__ == key:
			return course
	return None

@interface.implementer(INTIIDResolver)
class _GradeBookResolver(object):

	def resolve(self, key):
		catalog = component.queryUtility(ICourseCatalog)
		if catalog is not None:
			name = get_specific(key)
			course = get_course(catalog, name)
			return IGradeBook(course, None)
		return None

@interface.implementer(INTIIDResolver)
class _GradeBookPartResolver(object):

	def resolve(self, key):
		catalog = component.queryUtility(ICourseCatalog)
		if catalog is not None:
			specific = get_specific(key)
			try:
				course, part = specific.split('.')[-2]
				course = get_course(catalog, course)
				gradebook = IGradeBook(course, None)
				if gradebook:
					return gradebook[part]
			except ValueError:
				logger.error("'%s' invalid gradebook part NTIID", key)
			except KeyError:
				logger.error("Cannot find gradebook part using '%s'", key)
		return None

@interface.implementer(INTIIDResolver)
class _GradeBookEntryResolver(object):

	def resolve(self, key):
		catalog = component.queryUtility(ICourseCatalog)
		if catalog is not None:
			specific = get_specific(key)
			try:
				course, part, entry = specific.split('.')[-3]
				course = get_course(catalog, course)
				gradebook = IGradeBook(course, None)
				if gradebook and part in gradebook:
					parts = gradebook[part]
					return parts[entry]
			except ValueError:
				logger.error("'%s' invalid gradebook entry NTIID", key)
			except KeyError:
				logger.error("Cannot find gradebook entry using '%s'", key)
		return None
