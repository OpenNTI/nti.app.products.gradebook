#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .. import MessageFactory as _

import six

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexec

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.utils import is_enrolled
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.common.maps import CaseInsensitiveDict

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.externalization import to_external_object

from ..grades import Grade

from ..interfaces import IGradeBook
from ..interfaces import FINAL_GRADE_NAME
from ..interfaces import NO_SUBMIT_PART_NAME

from ..grading import VIEW_CURRENT_GRADE
from ..grading import calculate_predicted_grade
from ..grading import find_grading_policy_for_course

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

	def __call__(self):
		course = ICourseInstance(self.request.context)
		if not is_enrolled(course, self.remoteUser):
			raise hexec.HTTPForbidden(_("must be enrolled in course."))

		policy = find_grading_policy_for_course(course)
		if policy is None:
			raise hexec.HTTPUnprocessableEntity(_("Course does not define a grading policy."))

		course = ICourseInstance(self.context)
		book = IGradeBook(course)
		if not book.has_grades(self.remoteUser.username):
			raise hexec.HTTPNotFound()

		params = CaseInsensitiveDict(self.request.params)

		# check for a final grade.
		try:
			predicted = None
			is_predicted = False
			grade = book[NO_SUBMIT_PART_NAME][FINAL_GRADE_NAME][self.remoteUser.username]
			grade = None if is_none(grade.value) else grade
		except KeyError:
			grade = None

		if grade is None:
			is_predicted = True
			scheme = params.get('scheme') or u''
			predicted = calculate_predicted_grade(self.remoteUser, policy, scheme)

			grade = Grade()  # non persistent
			grade.value = predicted.Grade
			grade.username = self.remoteUser.username

		result = LocatedExternalDict()
		result.update(to_external_object(grade))
		result['IsPredicted'] = is_predicted
		if predicted is not None:
			result['RawValue'] = predicted.RawValue
			result['Correctness'] = predicted.Correctness
		return result
