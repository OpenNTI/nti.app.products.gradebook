#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views and other functions related to grades and gradebook.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .. import MessageFactory

import nameparser

from collections import OrderedDict

from datetime import datetime

from zope import component
from zope import interface
from zope.container.contained import Contained

from zope.traversing.interfaces import IPathAdapter

from pyramid.view import view_config
from pyramid.interfaces import IRequest

from nti.app.assessment.interfaces import ICourseAssignmentCatalog
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory

from nti.app.base.abstract_views import AbstractAuthenticatedView
from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentEditRequestUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.assessment.interfaces import IQAssignmentDateContext

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ES_CREDIT

from nti.dataserver.links import Link
from nti.dataserver import authorization as nauth
from nti.dataserver.interfaces import IEnumerableEntityContainer
from nti.dataserver.interfaces import IUser
from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IFriendlyNamed
from nti.dataserver.users.users import User

from nti.externalization.interfaces import LocatedExternalList
from nti.externalization.externalization import LocatedExternalDict
from nti.externalization.externalization import StandardExternalFields

from nti.utils.property import Lazy

from ..interfaces import IGrade
from ..interfaces import IGradeBook
from ..interfaces import IExcusedGrade
from ..interfaces import ACT_VIEW_GRADES
from ..interfaces import NO_SUBMIT_PART_NAME

from ..utils import replace_username
from ..utils import remove_from_container

from ..grades import PersistentGrade as Grade

LINKS = StandardExternalFields.LINKS
ITEMS = StandardExternalFields.ITEMS
CLASS = StandardExternalFields.CLASS

@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def GradeBookPathAdapter( context, request ):
	result = IGradeBook(context)
	return result

class UserGradeBookSummary( object ):
	"""
	A container for user grade summary info.  Most of these fields
	are lazy loaded so that these objects can be used in sorting, so
	that we intialize only the fields we need.
	"""

	__class_name__ = 'UserGradeBookSummary'

	def __init__( self, username, course, assignments, gradebook, final_grade_entry ):
		self.user = User.get_user( username )
		self.course = course
		self.assignments = assignments
		self.gradebook = gradebook
		self.final_grade_entry = final_grade_entry

	@Lazy
	def alias(self):
		named_user = IFriendlyNamed( self.user )
		return named_user.alias

	@Lazy
	def last_name(self):
		username = self.user.username
		profile = IUserProfile( self.user )

		lastname = ''
		realname = profile.realname or ''
		if realname and '@' not in realname and realname != username:
			human_name = nameparser.HumanName( realname )
			lastname = human_name.last or ''

		return lastname

	@Lazy
	def username(self):
		username = self.user.username
		return replace_username( username )

	@Lazy
	def _user_stats( self ):
		"Return overdue/ungraded stats for user."
		gradebook = self.gradebook
		assignments = self.assignments
		user = self.user
		course = self.course

		overdue_count = 0
		ungraded_count = 0
		today = datetime.utcnow()
		user_histories = component.queryMultiAdapter( ( course, user ),
												IUsersCourseAssignmentHistory )

		if user_histories is not None:
			for assignment in assignments:
				grade = gradebook.getColumnForAssignmentId( assignment.ntiid )
				user_grade = grade.get( user.username )
				history_item = user_histories.get( assignment.ntiid )

				# Submission but no grade
				if 		history_item \
					and ( 	user_grade is None
						or 	user_grade.value is None ):
					ungraded_count += 1

				# No submission and past due
				if history_item is None:

					due_date = IQAssignmentDateContext(course).of( assignment ).available_for_submission_ending
					if due_date and today > due_date:
						overdue_count += 1

		return overdue_count, ungraded_count

	@Lazy
	def overdue_count(self):
		return self._user_stats[0]

	@Lazy
	def ungraded_count(self):
		return self._user_stats[1]

	@Lazy
	def final_grade(self):
		# Not sure why we would not have final grade entry
		result = None
		if self.final_grade_entry is not None:
			result = self.final_grade_entry.get( self.username )
		return result

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

	sortOn
		The case insensitive field to sort on. Options are ``LastName``,
		``Alias``, ``FinalGrade``, and ``Username``.  The default is by
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
		occurs on the enrollment scope.  Options are ``Open`` and
		``ForCredit``.  ForCredit is the default enrollment scope.

	search
		The username to search on, regardless of enrollment scope. If
		not found, an empty set is returned.

	"""

	_DEFAULT_BATCH_SIZE = 50
	_DEFAULT_BATCH_START = 0

	def _get_summary_for_student( self, username, course, assignments, gradebook, final_grade_entry ):
		return UserGradeBookSummary( username, course, assignments, gradebook, final_grade_entry )

	def _get_students( self, course, assignments, gradebook, final_grade_entry, scope_name ):
		"Return the set of student names we want results for, along with the total count of students."
		# We default to ForCredit. If we want public, subtract out the for credit students.
		for_credit_scope = course.SharingScopes[ ES_CREDIT ]
		student_names = {x.lower() for x in IEnumerableEntityContainer(for_credit_scope).iter_usernames()}

		if scope_name == 'Public':
			everyone = course.SharingScopes['Public']
			enrollment_usernames = {x.lower() for x in IEnumerableEntityContainer(everyone).iter_usernames()}
			student_names = enrollment_usernames - student_names

		students_iter = (self._get_summary_for_student( username, course, assignments, gradebook, final_grade_entry )
						for username in student_names
						if User.get_user( username ) is not None)
		return students_iter, len( student_names )

	def _do_get_user_summaries(self, course, assignments, gradebook, final_grade_entry):
		"Get the filtered user summaries of users we may want to return."
		# We expect a list of filters
		# They can filter by counts or by enrollment scope (or both).
		filter_by = self.request.params.get('filter')
		filter_by = filter_by.split( ',' ) if filter_by else ()
		filter_by = [x.lower() for x in filter_by]

		# ForCredit is default.
		scope_name = 'ForCredit'
		if 'open' in filter_by:
			scope_name = 'Public'

		user_summaries, total_possible_count = self._get_students( course, assignments, gradebook,
																final_grade_entry, scope_name )

		if 'ungraded' in filter_by:
			user_summaries = ( x for x in user_summaries if x.ungraded_count > 0 )
		elif 'overdue' in filter_by:
			user_summaries = ( x for x in user_summaries if x.overdue_count > 0 )
		elif 'actionable' in filter_by:
			user_summaries = ( x for x in user_summaries
								if x.overdue_count > 0 or x.ungraded_count > 0 )

		return user_summaries, total_possible_count

	def _get_sorted_result_set( self, user_summaries, sort_key, sort_desc=False ):
		"Get the batched/sorted result set."
		user_summaries = sorted( user_summaries, key=sort_key, reverse=sort_desc )
		return user_summaries

	def _get_user_result_set(self, result_dict, user_summaries):
		"Return a sorted/batched collection of user summaries to return."
		sort_on = self.request.params.get('sortOn')
		sort_on = sort_on and sort_on.lower()

		# Ascending is default
		sort_order = self.request.params.get('sortOrder')
		sort_descending = bool( sort_order and sort_order.lower() == 'descending' )

		if sort_on and sort_on == 'finalgrade':
			sort_key = lambda x: x.final_grade.value if x.final_grade else ''
		elif sort_on and sort_on == 'alias':
			sort_key = lambda x: x.alias.lower() if x.alias else ''
		elif sort_on and sort_on == 'username':
			sort_key = lambda x: x.username.lower() if x.username else ''
		else:
			# Sorting by last_name is default
			sort_key = lambda x: x.last_name.lower() if x.last_name else ''

		result_set = self._get_sorted_result_set( user_summaries, sort_key, sort_descending )
		self._batch_items_iterable( result_dict, result_set )

		# Pop our items that we want to return.
		# We have our batch links for free at this point.
		return result_dict.pop( ITEMS )

	def _get_assignment_for_course( self, course ):
		assignment_catalog = ICourseAssignmentCatalog( course )
		assignments = [asg for asg in assignment_catalog.iter_assignments()]
		return assignments

	def _get_final_grade_entry( self, gradebook ):
		for part in gradebook.values():
			for part_name, entry in part.items():
				if 		part.__name__ == NO_SUBMIT_PART_NAME \
					and part_name == 'Final Grade':
					return entry
		return None

	def _get_user_dict( self, user_summary, course ):
		"Returns a user's gradebook summary."
		user_dict = {}
		user_dict[CLASS] = user_summary.__class_name__
		user_dict['User'] = user_summary.user
		user_dict['Alias'] = user_summary.alias
		user_dict['FinalGrade'] = user_summary.final_grade
		user_dict['OverdueAssignmentCount'] = user_summary.overdue_count
		user_dict['UngradedAssignmentCount'] = user_summary.ungraded_count

		# Link to user's assignment histories
		links = user_dict.setdefault( LINKS, [] )
		links.append( Link( course,
							rel='AssignmentHistory',
							elements=('AssignmentHistories', user_summary.username)) )
		return user_dict

	def _get_user_summaries( self, result_dict, course, assignments, gradebook, final_grade_entry ):
		"Returns a list of user summaries.  Search supercedes all filters/sorting params."
		search = self.request.params.get('search')
		username = search and search.lower()

		if username:
			if User.get_user( username ) is not None:
				summary = self._get_summary_for_student( username, course, assignments, gradebook, final_grade_entry )
				results = (summary,)
			else:
				results = ()
		else:
			# Get our intermediate set
			user_summaries, student_count = self._do_get_user_summaries( course, assignments,
																		gradebook, final_grade_entry )
			result_dict['TotalItemCount'] = student_count
			# Now our batched set
			# We should have links here after batching.
			results = self._get_user_result_set( result_dict, user_summaries )
		return results

	def __call__(self):
		# TODO Use assignment grade index?
		# TODO We could cache on the gradebook, but the
		# overdue/ungraded counts could change.
		gradebook = self.request.context
		course = self.context.__parent__
		final_grade_entry = self._get_final_grade_entry( gradebook )
		assignments = self._get_assignment_for_course( course )

		result_dict = LocatedExternalDict()
		user_summaries = self._get_user_summaries( result_dict, course, assignments, gradebook, final_grade_entry )

		result_dict[ITEMS] = items = []
		result_dict[CLASS] = 'GradeBookSummary'
		result_dict['ItemCount'] = len( user_summaries ) if user_summaries is not None else 0

		# Now build our data for each user
		for user_summary in user_summaries:
			user_dict = self._get_user_dict( user_summary, course )
			items.append( user_dict )

		return result_dict

@view_config(route_name='objects.generic.traversal',
			 permission=nauth.ACT_UPDATE,
			 renderer='rest',
			 context=IGrade,
			 request_method='PUT')
class GradePutView(AbstractAuthenticatedView,
				   ModeledContentUploadRequestUtilsMixin,
				   ModeledContentEditRequestUtilsMixin):

	content_predicate = IGrade.providedBy

	def _do_call(self):
		theObject = self.request.context
		theObject.creator = self.getRemoteUser()

		# perform checks
		self._check_object_exists(theObject)
		self._check_object_unmodified_since(theObject)

		# update from external
		externalValue = self.readInput()
		self.updateContentObject(theObject, externalValue)

		logger.info("'%s' updated grade '%s' for user '%s'",
					self.getRemoteUser(),
					theObject.AssignmentId,
					theObject.Username)

		return theObject

@view_config(route_name='objects.generic.traversal',
			 permission=nauth.ACT_UPDATE,
			 renderer='rest',
			 context=IGrade,
			 name="excuse",
			 request_method='POST')
class ExcuseGradeView(AbstractAuthenticatedView,
				 	  ModeledContentUploadRequestUtilsMixin,
				   	  ModeledContentEditRequestUtilsMixin):

	content_predicate = IGrade.providedBy

	def _do_call(self):
		theObject = self.request.context
		self._check_object_exists(theObject)
		self._check_object_unmodified_since(theObject)

		if not IExcusedGrade.providedBy(theObject):
			interface.alsoProvides(theObject, IExcusedGrade)
			theObject.updateLastMod()
		return theObject

@view_config(route_name='objects.generic.traversal',
			 permission=nauth.ACT_UPDATE,
			 renderer='rest',
			 context=IGrade,
			 name="unexcuse",
			 request_method='POST')
class UnexcuseGradeView(AbstractAuthenticatedView,
				 	    ModeledContentUploadRequestUtilsMixin,
				   	    ModeledContentEditRequestUtilsMixin):

	content_predicate = IGrade.providedBy

	def _do_call(self):
		theObject = self.request.context
		self._check_object_exists(theObject)
		self._check_object_unmodified_since(theObject)

		if IExcusedGrade.providedBy(theObject):
			interface.noLongerProvides(theObject, IExcusedGrade)
			theObject.updateLastMod()
		return theObject

from nti.dataserver.users import User

from ..utils import record_grade_without_submission

@view_config(route_name='objects.generic.traversal',
			 permission=nauth.ACT_UPDATE,
			 renderer='rest',
			 context='nti.app.products.gradebook.gradebook.GradeWithoutSubmission',
			 request_method='PUT')
class GradeWithoutSubmissionPutView(GradePutView):
	"""
	Called to put to a grade that doesn't yet exist.
	"""

	#: We don't want extra catching of key errors
	_EXTRA_INPUT_ERRORS = ()

	def _do_call(self):
		# So we make one exist
		entry = self.request.context.__parent__
		username = self.request.context.__name__
		user = User.get_user(username)
		assignmentId = entry.AssignmentId

		grade = record_grade_without_submission(entry, user, assignmentId)
		if grade is not None:
			## place holder grade was inserted
			self.request.context = grade
		else:
			# This inserted the 'real' grade. To actually
			# updated it with the given values, let the super
			# class do the work
			self.request.context = entry[username]

		result = super(GradeWithoutSubmissionPutView,self)._do_call()
		return result

from zope import lifecycleevent
from zope.annotation import IAnnotations

from nti.appserver.ugd_edit_views import UGDDeleteView

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='DELETE',
			 context=IGradeBook,
			 permission=nauth.ACT_DELETE)
class GradebookDeleteView(UGDDeleteView):
	"""
	Admins can delete an entire gradebook. This is mostly
	for migration purposes from old databases.
	"""

	def _do_delete_object(self, context):
		# We happen to know that it is stored as
		# an annotation.
		annots = IAnnotations(context.__parent__)
		del annots[context.__name__]
		lifecycleevent.removed(context)
		return True

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='DELETE',
			 context=IGrade,
			 permission=nauth.ACT_DELETE)
class GradeDeleteView(UGDDeleteView):
	"""
	Instructors can delete an individual grade.
	"""

	def _do_delete_object(self, context):
		# delete the grade from its container (column, GradeBookEntry)
		# One would think that if we got here it's because
		# there is actually a grade recorded so `del` would be
		# safe; one would be wrong. That's because of
		# ..gradebook.GradeBookEntryWithoutSubmissionTraversable which
		# dummies up a grade for anyone that asks. So if we can't find
		# it, follow the contract and let a 404 error be raised
		try:
			remove_from_container(context.__parent__, context.__name__)
		except KeyError:
			return None
		else:
			return True
