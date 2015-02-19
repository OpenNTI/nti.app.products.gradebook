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

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.externalization import to_external_object

from ..grades import PersistentGrade

from ..interfaces import IGradeBook
from ..interfaces import IGradeScheme
from ..interfaces import FINAL_GRADE_NAME
from ..interfaces import NO_SUBMIT_PART_NAME

from ..grading import VIEW_CURRENT_GRADE
from ..grading import find_grading_policy_for_course

@view_config(context=ICourseInstance)
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
		
		## check for a final grade.
		try:
			result = book[NO_SUBMIT_PART_NAME][FINAL_GRADE_NAME]
			return result
		except KeyError:
			pass
		
		presentation = policy.presentation
		scheme = self.request.params.get('scheme')
		if scheme:
			presentation = component.getUtility(IGradeScheme, name=scheme)
	
		correctness = policy.grade(self.remoteUser)
		
		grade = PersistentGrade()
		grade.username = self.remoteUser.username
		grade.value = presentation.fromCorrectness(correctness) \
					  if presentation is not None else int(correctness * 100)

		result = LocatedExternalDict()		
		result.update(to_external_object(grade))
		result['Correctness'] = correctness
		result['IsPredicted'] = True
		return result
