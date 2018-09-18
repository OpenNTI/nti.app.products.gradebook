#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.app.products.gradebook.grading import VIEW_CURRENT_GRADE

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contenttypes.courses.grading import find_grading_policy_for_course

from nti.contenttypes.courses.utils import is_enrolled

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IExternalMappingDecorator)
class _CurrentGradeLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, unused_result=None):
        result = self._is_authenticated and is_enrolled(context, self.remoteUser)
        if result:
            result = find_grading_policy_for_course(context) is not None
        return result

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context,
                    rel=VIEW_CURRENT_GRADE, 
                    elements=(VIEW_CURRENT_GRADE,))
        _links.append(link)
