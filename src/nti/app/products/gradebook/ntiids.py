#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NTIID resolvers

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.app.products.courseware import interfaces as courseware_interfaces

from nti.ntiids.ntiids import get_specific
from nti.ntiids import interfaces as nid_interfaces

from . import interfaces as grades_interfaces

@interface.implementer(nid_interfaces.INTIIDResolver)
class _GradeBookResolver(object):

	@classmethod
	def get_course(self, catalog, key):
		for course in catalog:
			if course.__name__ == key:
				return course
		return None

	def resolve(self, key):
		catalog = component.queryUtility(courseware_interfaces.ICourseCatalog)
		if catalog:
			name = get_specific(key)
			course = self.get_course(catalog, name)
			return grades_interfaces.IGradeBook(course, None)
		return None


