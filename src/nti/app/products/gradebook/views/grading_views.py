#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.products.gradebook import MessageFactory as _

from nti.app.products.gradebook.grades import Grade

from nti.app.products.gradebook.grading import VIEW_CURRENT_GRADE

from nti.app.products.gradebook.grading.utils import calculate_predicted_grade

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import ACT_VIEW_GRADES
from nti.app.products.gradebook.interfaces import FINAL_GRADE_NAME
from nti.app.products.gradebook.interfaces import NO_SUBMIT_PART_NAME

from nti.appserver.pyramid_authorization import has_permission

from nti.common.maps import CaseInsensitiveDict

from nti.contenttypes.courses.grading import find_grading_policy_for_course

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver import authorization as nauth

from nti.dataserver.users import User

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.externalization import to_external_object


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
            user = User.get_user( username )
            if user is None:
                raise hexc.HTTPUnprocessableEntity(_("User not found."))
        else:
            user = self.remoteUser
        return user

    def __call__(self):
        course = ICourseInstance(self.request.context)
        if      not is_enrolled(course, self.remoteUser) \
            and not is_course_instructor(course, self.remoteUser):
            raise hexc.HTTPForbidden(_("Must be enrolled in course."))

        policy = find_grading_policy_for_course(course)
        if policy is None:
            raise hexc.HTTPUnprocessableEntity(
                _("Course does not define a grading policy."))

        course = ICourseInstance(self.context)
        book = IGradeBook(course)
        params = CaseInsensitiveDict(self.request.params)
        user = self._get_user(params)
        if      user != self.remoteUser \
            and not has_permission(ACT_VIEW_GRADES, book):
                raise hexc.HTTPForbidden(_("Cannot view grades."))

        # check for a final grade.
        try:
            predicted = None
            is_predicted = False
            grade = book[NO_SUBMIT_PART_NAME][
                FINAL_GRADE_NAME][user.username]
            grade = None if is_none(grade.value) else grade
        except KeyError:
            grade = None

        if grade is None:
            is_predicted = True
            scheme = params.get('scheme') or u''
            predicted = calculate_predicted_grade(user,
												  policy,
												  scheme)
            if predicted is not None:
                grade = Grade()  # non persistent
                grade.value = predicted.Grade
                grade.username = user.username

        if grade is None:
            raise hexc.HTTPNotFound()

        result = LocatedExternalDict()
        result.update(to_external_object(grade))
        result['IsPredicted'] = is_predicted
        if predicted is not None:
            result['RawValue'] = predicted.RawValue
            result['Correctness'] = predicted.Correctness
        return result
