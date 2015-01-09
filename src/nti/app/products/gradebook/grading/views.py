#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .. import MessageFactory as _

from zope import component

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexec

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.utils import is_enrolled
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import authorization as nauth

from ..grades import Grade
from ..interfaces import IGradeScheme

from . import find_grading_policy_for_course

@view_config(context=ICourseInstance)
@view_config(context=ICourseInstanceEnrollment)
@view_defaults(route_name='objects.generic.traversal',
               permission=nauth.ACT_READ,
               name="CurrentGrade",
               renderer='rest',
               request_method='GET')
class CurrentGradeView(AbstractAuthenticatedView):
    
    def __call__(self):
        course = ICourseInstance(self.request.context)
        if not is_enrolled(course, self.remoteUser):
            raise hexec.HTTPForbidden(_("must be enrolled in course."))
        
        policy = find_grading_policy_for_course(course)
        if policy is None:
            raise hexec.HTTPUnprocessableEntity(_("Course does not define a grading policy."))

        scheme = self.request.params.get('scheme') or u''
        scheme = component.getUtility(IGradeScheme, name=scheme)
        
        correctness = policy.grade(self.remoteUser)

        value  = scheme.fromCorrectness(correctness)
        result = Grade(value=value)
        return result
