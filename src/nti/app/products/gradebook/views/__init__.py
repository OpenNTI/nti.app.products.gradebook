#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Functions related to grades and gradebook.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from datetime import datetime

import nameparser

from six import string_types

from zope import component
from zope import interface

from zope.traversing.interfaces import IPathAdapter

from pyramid.interfaces import IRequest

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItemSummary

from nti.app.products.gradebook.grading import calculate_predicted_grade

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.app.products.gradebook.utils import replace_username

from nti.assessment.interfaces import IQAssignmentDateContext

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import get_course_assessment_predicate_for_user

from nti.dataserver.users.users import User
from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.property.property import Lazy

def _get_history_item(course, user, assignment_id):
	history = component.getMultiAdapter((course, user), IUsersCourseAssignmentHistory)
	return history.get(assignment_id)

def _get_grade_parts(grade_value):
	"""
	Convert the webapp's "number - letter" scheme to a tuple.
	"""
	result = (grade_value,)
	if grade_value and isinstance(grade_value, string_types):
		try:
			values = grade_value.split()
			values[0] = float(values[0])
			result = tuple(values)
		except ValueError:
			pass
	return result

@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def GradeBookPathAdapter(context, request):
	result = IGradeBook(context)
	return result

class UserGradeSummary(object):
	"""
	A container for user grade summary info.  Most of these fields
	are lazy loaded so that these objects can be used in sorting, so
	that we initialize only the fields as needed.
	"""

	__class_name__ = 'UserGradeBookSummary'

	def __init__(self, username, grade_entry, course):
		self.user = User.get_user(username)
		self.grade_entry = grade_entry
		self.course = course

	@property
	def assignment_filter(self):
		return get_course_assessment_predicate_for_user(self.user,
														 self.course)

	@Lazy
	def alias(self):
		named_user = IFriendlyNamed(self.user)
		return named_user.alias

	@Lazy
	def last_name(self):
		username = self.user.username
		profile = IUserProfile(self.user)

		lastname = ''
		realname = profile.realname or ''
		if realname and '@' not in realname and realname != username:
			human_name = nameparser.HumanName(realname)
			lastname = human_name.last or ''
		return lastname

	@Lazy
	def username(self):
		"""
		The displayable, sortable username.
		"""
		username = self.user.username
		return replace_username(username)

	@Lazy
	def user_grade_entry(self):
		result = None
		if self.grade_entry is not None:
			result = self.grade_entry.get(self.user.username)
		return result

	@Lazy
	def grade_value(self):
		result = None
		if self.user_grade_entry is not None:
			result = self.user_grade_entry.value
		return result

	@Lazy
	def grade_tuple(self):
		"""
		A tuple of (grade_num, grade_other, submitted).
		"""
		if self.grade_value is not None:
			result = _get_grade_parts(self.grade_value)
		else:
			result = (None, None, bool(self.history_item))
		return result

	@Lazy
	def feedback_count(self):
		result = None
		if self.history_item is not None:
			result = self.history_item.FeedbackCount
		return result

	@Lazy
	def created_date(self):
		result = None
		if self.history_summary is not None:
			result = self.history_summary.createdTime
		return result

	@Lazy
	def history_item(self):
		# We always want to return this if possible, even
		# if we do not have a grade.
		result = None
		if self.grade_entry is not None:
			assignment_id = self.grade_entry.AssignmentId
			result = _get_history_item(self.course, self.user, assignment_id)
		return result

	@Lazy
	def history_summary(self):
		result = None
		history_item = self.history_item
		if history_item is not None:
			result = IUsersCourseAssignmentHistoryItemSummary(history_item, None)
		return result

class UserGradeBookSummary(UserGradeSummary):
	"""
	An overall gradebook summary for a user that includes
	aggregate stats.
	"""

	__class_name__ = 'UserGradeBookSummary'

	def __init__(self, username, course, assignments, gradebook, grade_entry, grade_policy):
		super(UserGradeBookSummary, self).__init__(username, grade_entry, course)
		self.assignments = assignments
		self.gradebook = gradebook
		self.grade_policy = grade_policy

	@Lazy
	def _user_stats(self):
		"""
		Return overdue/ungraded stats for user.
		"""
		assignments = (x for x in self.assignments if self.assignment_filter(x))
		user = self.user
		course = self.course

		overdue_count = 0
		ungraded_count = 0
		today = datetime.utcnow()
		user_histories = component.queryMultiAdapter((course, user),
													 IUsersCourseAssignmentHistory)

		if user_histories is not None:
			for assignment in assignments:
				grade = self.gradebook.getColumnForAssignmentId(assignment.ntiid)
				user_grade = grade.get(user.username) if grade is not None else None
				history_item = user_histories.get(assignment.ntiid)

				# Submission but no grade
				if 		history_item is not None \
					and (user_grade is None or user_grade.value is None):
					ungraded_count += 1

				# No submission and past due
				if history_item is None:
					context = IQAssignmentDateContext(course)
					due_date = context.of(assignment).available_for_submission_ending
					if due_date and today > due_date:
						overdue_count += 1

		return overdue_count, ungraded_count

	@Lazy
	def predicted_grade(self):
		result = None
		if self.grade_policy:
			result = calculate_predicted_grade(self.user, self.grade_policy)
		return result

	@Lazy
	def overdue_count(self):
		return self._user_stats[0]

	@Lazy
	def ungraded_count(self):
		return self._user_stats[1]
