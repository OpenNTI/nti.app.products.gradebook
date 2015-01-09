#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.dataserver.links import Link

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from ..decorators import _CourseInstanceGradebookLinkDecorator

LINKS = StandardExternalFields.LINKS

@interface.implementer(IExternalMappingDecorator)
class _CourseInstanceCurrentGradeLinkDecorator(_CourseInstanceGradebookLinkDecorator):

	def _do_decorate_external(self, course, result):
		_links = result.setdefault(LINKS, [])
		link = Link(self.course, rel="CurrentGrade")
		_links.append(link)
