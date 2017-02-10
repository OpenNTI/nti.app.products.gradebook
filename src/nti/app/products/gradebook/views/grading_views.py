#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from requests.structures import CaseInsensitiveDict

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.products.gradebook import MessageFactory as _

from nti.app.products.gradebook.grading import VIEW_CURRENT_GRADE

from nti.app.products.gradebook.grading.utils import calculate_predicted_grade

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import ACT_VIEW_GRADES
from nti.app.products.gradebook.interfaces import FINAL_GRADE_NAME
from nti.app.products.gradebook.interfaces import NO_SUBMIT_PART_NAME

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.grading import find_grading_policy_for_course

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver import authorization as nauth

from nti.dataserver.users import User

from nti.externalization.interfaces import LocatedExternalDict


def is_none(value):
    result = False
    if value is None:
        result = True
    elif isinstance(value, six.string_types):
        value = value.strip()
        if value.endswith('-'):
            value = value[:-1]
        result = not bool(value)
    return result


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_config(context=ICourseInstanceEnrollment)
@view_defaults(route_name='objects.generic.traversal',
               permission=nauth.ACT_READ,
               name=VIEW_CURRENT_GRADE,
               renderer='rest',
               request_method='GET')
class CurrentGradeView(AbstractAuthenticatedView):
    """
    Fetch the current (predicted) grade for a user based on the
    course's `ICourseGradePolicy` (required). The caller must
    have `ACT_VIEW_GRADES` permission on the gradebook to view
    this for others.
    """

    def _get_user(self, params):
        username = params.get('user') or params.get('username')
        user = None
        if username:
            user = User.get_user(username)
            if user is None:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     u'message': _("User not found."),
                                     u'code': "UserNotFound",
                                 },
                                 None)
        else:
            user = self.remoteUser
        return user

    def __call__(self):
        course = ICourseInstance(self.request.context)
        if      not is_enrolled(course, self.remoteUser) \
            and not is_course_instructor(course, self.remoteUser):
            raise_json_error(self.request,
                             hexc.HTTPForbidden,
                             {
                                 u'message': _("Must be enrolled in course."),
                                 u'code': "MustBeEnrolledInCourse",
                             },
                             None)

        policy = find_grading_policy_for_course(course)
        if policy is None:
            raise_json_error(
                self.request,
                hexc.HTTPUnprocessableEntity,
                {
                    u'message': _("Course does not define a grading policy."),
                    u'code': "CourseDoesNotDefineGradingPolicy",
                },
                None)

        course = ICourseInstance(self.context)
        book = IGradeBook(course)
        params = CaseInsensitiveDict(self.request.params)
        user = self._get_user(params)
        if      user != self.remoteUser \
            and not has_permission(ACT_VIEW_GRADES, book):
            raise_json_error(self.request,
                             hexc.HTTPForbidden,
                             {
                                 u'message': _("Cannot view grades."),
                                 u'code': "CannotViewGrades",
                             },
                             None)

        # check for a final grade.
        result = LocatedExternalDict()
        try:
            part = book[NO_SUBMIT_PART_NAME]
            final_grade = part[FINAL_GRADE_NAME][user.username]
            final_grade = None if is_none(final_grade.value) else final_grade
            if final_grade is not None:
                result['FinalGrade'] = final_grade
        except KeyError:
            final_grade = None

        scheme = params.get('scheme') or u''
        predicted_grade = calculate_predicted_grade(user,
                                                    policy,
                                                    scheme)

        if predicted_grade is None and final_grade is None:
            raise hexc.HTTPNotFound()

        if predicted_grade is not None:
            result['PredictedGrade'] = predicted_grade

        return result
