#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views and other functions related to grades and gradebook.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from datetime import datetime

import nameparser

from zope import component

from zope.cachedescriptors.property import Lazy

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItemSummary

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.app.products.gradebook.grading import VIEW_CURRENT_GRADE

from nti.app.products.gradebook.grading.utils import calculate_predicted_grade

from nti.app.products.gradebook.interfaces import ACT_VIEW_GRADES
from nti.app.products.gradebook.interfaces import NO_SUBMIT_PART_NAME

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IGradeBookEntry

from nti.app.products.gradebook.utils import replace_username

from nti.app.products.gradebook.views import _get_grade_parts

from nti.assessment.interfaces import IQAssignmentDateContext

from nti.contenttypes.courses.grading import find_grading_policy_for_course

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseAssignmentCatalog
from nti.contenttypes.courses.interfaces import get_course_assessment_predicate_for_user

from nti.dataserver.interfaces import IEnumerableEntityContainer

from nti.dataserver.users.users import User
from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.externalization.externalization import LocatedExternalDict
from nti.externalization.externalization import StandardExternalFields

from nti.links.links import Link

from nti.ntiids.ntiids import find_object_with_ntiid

LINKS = StandardExternalFields.LINKS
ITEMS = StandardExternalFields.ITEMS
CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE

def _get_history_item(course, user, assignment_id):
	history = component.getMultiAdapter((course, user),
										IUsersCourseAssignmentHistory)
	return history.get(assignment_id)

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

@view_config(route_name='objects.generic.traversal',
			 permission=ACT_VIEW_GRADES,
			 renderer='rest',
			 context=IGradeBook,
			 name='GradeBookSummary',
			 request_method='GET')
class GradeBookSummaryView(AbstractAuthenticatedView,
				  			BatchingUtilsMixin):
	"""
	Return the gradebook summary for students in the given course.

	batchSize
		The size of the batch.  Defaults to 50.

	batchStart
		The starting batch index.  Defaults to 0.

	batchContainingUsername
		String parameter giving the ``Username`` to build a batch
		around. Otherwise identical to ``batchContaining``.

	batchContainingUsernameFilterByScope
		Like ``batchContainingUsername``, but also returns the batched
		users belonging to the enrollment scope of the given user.

	sortOn
		The case insensitive field to sort on. Options are ``LastName``,
		``Alias``, ``Grade``, ``PredictedGrade``, ``Username``.  The default is by
		LastName.

	sortOrder
		The sort direction. Options are ``ascending`` and
		``descending``. If you do not specify, a value that makes
		the most sense for the ``sortOn`` parameter will be used
		by default.

	filter
		The case insensitive filter list.  This is a two part filter.
		Options are ``Ungraded``, ``Overdue``, and ``Actionable``.
		Actionable is a combination of the other two. The other filter
		occurs on the enrollment scope.  Options are ``Open``, ``All`` and
		``ForCredit``.  ForCredit is the default enrollment scope (due to BWC).

	search
		The username to search on. If not found, an empty set is returned.

	"""

	_DEFAULT_BATCH_SIZE = 50
	_DEFAULT_BATCH_START = 0

	def __init__(self, context, request):
		super(GradeBookSummaryView, self).__init__(request)
		self.request = request
		self.gradebook = context
		self.course = ICourseInstance(context)

	@Lazy
	def grade_policy(self):
		policy = find_grading_policy_for_course(self.course)
		return policy

	@Lazy
	def assignments(self):
		assignment_catalog = ICourseAssignmentCatalog(self.course)
		assignments = tuple(asg for asg in assignment_catalog.iter_assignments())
		return assignments

	@Lazy
	def final_grade_entry(self):
		for part in self.gradebook.values():
			for part_name, entry in part.items():
				if 		part.__name__ == NO_SUBMIT_PART_NAME \
					and part_name == 'Final Grade':
					return entry
		return None

	@Lazy
	def final_grade_assignment(self):
		result = None
		if self.final_grade_entry is not None:
			result = find_object_with_ntiid(self.final_grade_entry.AssignmentId)
		return result

	def _get_summary_for_student(self, username):
		return UserGradeBookSummary(username, self.course, self.assignments,
									self.gradebook, self.final_grade_entry,
									self.grade_policy)

	def _get_summaries_for_usernames(self, student_names):
		"""
		For the given names, return student summaries.
		"""
		students_iter = (self._get_summary_for_student(username)
						 for username in student_names
						 if User.get_user(username) is not None)
		return tuple(x for x in students_iter if x is not None)

	@Lazy
	def _instructors(self):
		instructor_usernames = {x.username.lower() for x in self.course.instructors}
		return instructor_usernames

	@Lazy
	def _all_students(self):
		enrollments = ICourseEnrollments(self.course)
		result = {x.lower() for x in enrollments.iter_principals()}
		return result - self._instructors

	@Lazy
	def _open_students(self):
		student_names = self._all_students - self._for_credit_students
		return student_names

	@Lazy
	def _for_credit_students(self):
		for_credit_scope = self.course.SharingScopes[ ES_CREDIT ]
		student_names = {x.lower() for x
						 in IEnumerableEntityContainer(for_credit_scope).iter_usernames()}
		return student_names & self._all_students - self._instructors

	def _get_enrollment_scoped_summaries(self, filter_by):
		"""
		Find the enrollment scoped user summaries.
		"""
		student_names = None

		# If they want to batch and filter by the scope of the given username.
		batch_username = self.request.params.get('batchContainingUsernameFilterByScope')
		if batch_username:
			batch_username = batch_username.lower()

			if batch_username in self._open_students:
				filter_scope_name = 'Open'
				student_names = self._open_students

		if student_names is None:
			# Filter by given scope, defaulting to ForCredit
			if 'open' in filter_by:
				filter_scope_name = 'Open'
				student_names = self._open_students
			elif 'all' in filter_by:
				filter_scope_name = 'All'
				student_names = self._all_students
			else:
				filter_scope_name = 'ForCredit'
				student_names = self._for_credit_students

		self.filter_scope_name = filter_scope_name
		user_summaries = self._get_summaries_for_usernames(student_names)
		return user_summaries

	def _do_get_user_summaries(self):
		"""
		Get the filtered user summaries of users we may want to return.
		"""
		# We expect a list of filters.
		# They can filter by counts or by enrollment scope (or both).
		filter_by = self.request.params.get('filter')
		filter_by = filter_by.split(',') if filter_by else ()
		filter_by = [x.lower() for x in filter_by]

		user_summaries = self._get_enrollment_scoped_summaries(filter_by)

		if 'ungraded' in filter_by:
			user_summaries = tuple(x for x in user_summaries if x.ungraded_count > 0)
		elif 'overdue' in filter_by:
			user_summaries = tuple(x for x in user_summaries if x.overdue_count > 0)
		elif 'actionable' in filter_by:
			user_summaries = tuple(x for x in user_summaries
								   if x.overdue_count > 0 or x.ungraded_count > 0)

		# Resolve
		user_summaries = [x for x in user_summaries]

		return user_summaries

	def _get_sorted_result_set(self, user_summaries, sort_key, sort_desc=False):
		"""
		Get the sorted result set.
		"""
		user_summaries = sorted(user_summaries, key=sort_key, reverse=sort_desc)
		return user_summaries

	def _get_sort_key(self, sort_on):
		# Sorting by last_name is default
		sort_key = lambda x: x.last_name.lower() if x.last_name else ''

		if sort_on:
			sort_on = sort_on.lower()
			if sort_on == 'grade':
				sort_key = lambda x: x.grade_tuple
			elif sort_on == 'alias':
				sort_key = lambda x: x.alias.lower() if x.alias else ''
			elif sort_on == 'username':
				sort_key = lambda x: x.username.lower() if x.username else ''
			elif sort_on == 'predictedgrade':
				sort_key = lambda x: getattr(x.predicted_grade, 'Correctness', None) or 0

		return sort_key

	def _check_batch_around(self, user_summaries):
		"""
		Return our batch around the given username.
		"""
		batch_username = self.request.params.get('batchContainingUsername')
		if not batch_username:
			batch_username = self.request.params.get('batchContainingUsernameFilterByScope')

		if batch_username:
			batch_username = batch_username.lower()
			batch_around_test = lambda x: x.user.username.lower() == batch_username
			# This toggles the batchStart params to our page.
			self._batch_on_item(user_summaries, batch_around_test, batch_containing=True)

	def _get_user_result_set(self, result_dict, user_summaries):
		"""
		Return a sorted/batched collection of user summaries to return.
		"""
		sort_on = self.request.params.get('sortOn')
		sort_key = self._get_sort_key(sort_on)

		# Ascending is default
		sort_order = self.request.params.get('sortOrder')
		sort_descending = bool(sort_order and sort_order.lower() == 'descending')

		result_set = self._get_sorted_result_set(user_summaries, sort_key, sort_descending)

		self._check_batch_around(result_set)
		self._batch_items_iterable(result_dict, result_set)

		# Pop our items that we want to return.
		# We have our batch links for free at this point.
		return result_dict.pop(ITEMS)

	def _get_available_final_grade_for_summary(self, summary):
		result = False
		if self.final_grade_assignment is not None:
			result = summary.assignment_filter(self.final_grade_assignment)
		return result

	def _get_user_dict(self, user_summary):
		"""
		Returns a user's gradebook summary.
		"""
		user_dict = LocatedExternalDict()
		user_dict[CLASS] = user_summary.__class_name__
		user_dict['User'] = user_summary.user
		user_dict['Alias'] = user_summary.alias
		user_dict['Username'] = user_summary.username
		user_dict['HistoryItemSummary'] = user_summary.history_summary
		user_dict['OverdueAssignmentCount'] = user_summary.overdue_count
		user_dict['UngradedAssignmentCount'] = user_summary.ungraded_count
		user_dict['AvailableFinalGrade'] = self._get_available_final_grade_for_summary(user_summary)
		user_dict[MIMETYPE] = 'application/vnd.nextthought.gradebook.usergradebooksummary'

		links = user_dict.setdefault(LINKS, [])
		# Only expose if our course has one
		if self.grade_policy:
			predicted = user_summary.predicted_grade
			if predicted is not None:
				user_dict['PredictedGrade'] = predicted
			links.append(Link(self.course,
						  	  rel=VIEW_CURRENT_GRADE,
						  	  elements=(VIEW_CURRENT_GRADE,),
						  	  params={'user': user_summary.username}))

		# Link to user's assignment histories
		links.append(Link(self.course,
						  rel='AssignmentHistory',
						  elements=('AssignmentHistories', user_summary.user.username)))
		return user_dict

	def _search_summaries(self, search_param, user_summaries):
		"""
		For the given search_param, return the results for those users
		if it matches last_name, alias, or displayable username.
		"""
		# The entity catalog could be used here, but we
		# have to make sure we can search via the substituted username (e.g. OU4x4).

		def matches(user_summary):
			result = (user_summary.alias
					  and search_param in user_summary.alias.lower()) \
				or	(user_summary.username
					 and search_param in user_summary.username.lower()) \
				or 	(user_summary.last_name
					 and search_param in user_summary.last_name.lower())
			return result

		results = [x for x in user_summaries if matches(x)]
		return results

	def _get_user_summaries(self, result_dict):
		"""
		Returns a list of user summaries.
		"""
		# 1. Filter
		# 2. Search
		# 3. Sort
		# 4. Batch
		search = self.request.params.get('search')
		search_param = search and search.lower()

		# Get our filtered intermediate set
		user_summaries = self._do_get_user_summaries()

		if search_param:
			user_summaries = self._search_summaries(search_param, user_summaries)

		result_dict['TotalItemCount'] = len(user_summaries)
		# Now our batched set
		# We should have links here after batching.
		results = self._get_user_result_set(result_dict, user_summaries)
		return results

	def __call__(self):
		# TODO: We could cache on the gradebook, but the
		# overdue/ungraded counts could change.
		result_dict = LocatedExternalDict()
		user_summaries = self._get_user_summaries(result_dict)

		result_dict[ITEMS] = items = []
		result_dict[CLASS] = 'GradeBookSummary'
		result_dict['EnrollmentScope'] = self.filter_scope_name
		result_dict[MIMETYPE] = 'application/vnd.nextthought.gradebook.gradebooksummary'

		any_final_grades = False
		# Now build our data for each user
		for user_summary in user_summaries:
			user_dict = self._get_user_dict(user_summary)
			items.append(user_dict)
			if not any_final_grades:
				any_final_grades = user_dict.get('AvailableFinalGrade')

		# For this result set, do any users have accessible final grades?
		result_dict['AvailableFinalGrade'] = any_final_grades
		return result_dict

@view_config(route_name='objects.generic.traversal',
			 permission=ACT_VIEW_GRADES,
			 renderer='rest',
			 context=IGradeBookEntry,
			 name='Summary',
			 request_method='GET')
class AssignmentSummaryView(GradeBookSummaryView):
	"""
	Return the assignment summary for students in the given assignment.

	batchSize
		The size of the batch.  Defaults to 50.

	batchStart
		The starting batch index.  Defaults to 0.

	sortOn
		The case insensitive field to sort on. Options are ``LastName``,
		``Alias``, ``Grade``, ``Username``, ``FeedbackCount``, and ``DateSubmitted``.
		The default is by LastName.

	sortOrder
		The sort direction. Options are ``ascending`` and
		``descending``. If you do not specify, a value that makes
		the most sense for the ``sortOn`` parameter will be used
		by default.

	filter
		The case insensitive filter on the enrollment scope.  Options
		are ``Open`` and ``ForCredit``.  ForCredit is the default enrollment scope.

	search
		The username to search on, regardless of enrollment scope. If
		not found, an empty set is returned.

	"""

	def __init__(self, context, request):
		super(AssignmentSummaryView, self).__init__(context.__parent__, request)
		self.request = request
		self.grade_entry = context
		self.course = ICourseInstance(context)

	@property
	def assignment(self):
		return find_object_with_ntiid(self.grade_entry.AssignmentId)

	def _get_summary_for_student(self, username):
		# We filter out any students without access to this assignment here.
		result = UserGradeSummary(username, self.grade_entry, self.course)
		assignment = self.assignment
		if assignment is None or not result.assignment_filter(self.assignment):
			result = None
		return result

	def _get_sort_key(self, sort_on):
		sort_key = None
		if sort_on:
			sort_on = sort_on.lower()
			if sort_on == 'feedbackcount':
				sort_key = lambda x: x.feedback_count if x.feedback_count else ''
			elif sort_on == 'datesubmitted':
				sort_key = lambda x: x.created_date if x.created_date else ''

		if sort_key is None:
			# Super class handles name and grade sorting, as well as the default.
			sort_key = super(AssignmentSummaryView, self)._get_sort_key(sort_on)
		return sort_key

	def _get_user_dict(self, user_summary):
		"""
		Returns a user's assignment summary.
		"""
		user_dict = LocatedExternalDict()
		user_dict[CLASS] = user_summary.__class_name__
		user_dict['User'] = user_summary.user
		user_dict['Alias'] = user_summary.alias
		user_dict['Username'] = user_summary.username
		user_dict['HistoryItemSummary'] = user_summary.history_summary
		user_dict[MIMETYPE] = 'application/vnd.nextthought.gradebook.userassignmentsummary'
		return user_dict

	def __call__(self):
		result_dict = LocatedExternalDict()
		user_summaries = self._get_user_summaries(result_dict)

		result_dict[ITEMS] = items = []
		result_dict[CLASS] = 'GradeBookByAssignmentSummary'
		result_dict['EnrollmentScope'] = self.filter_scope_name
		result_dict[MIMETYPE] = 'application/vnd.nextthought.gradebook.gradebookbyassignmentsummary'

		# Now build our data for each user
		for user_summary in user_summaries:
			user_dict = self._get_user_dict(user_summary)
			items.append(user_dict)
		return result_dict
