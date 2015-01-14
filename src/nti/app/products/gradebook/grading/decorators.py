#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.app.products.courseware.utils import is_enrolled

from nti.dataserver.links import Link

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from . import find_grading_policy_for_course

LINKS = StandardExternalFields.LINKS

@interface.implementer(IExternalMappingDecorator)
class _CurrentGradeLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		result = self._is_authenticated and find_grading_policy_for_course(context) and \
				 is_enrolled(context, self.remoteUser)
		return result
	
	def _do_decorate_external(self, context, result):
		_links = result.setdefault(LINKS, [])
		link = Link(context, rel="CurrentGrade")
		_links.append(link)
