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

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import authorization as nauth
from nti.dataserver.links import Link
from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.externalization.interfaces import LocatedExternalList
from nti.externalization.externalization import LocatedExternalDict
from nti.externalization.externalization import StandardExternalFields

from ..interfaces import IGrade
from ..interfaces import IGradeBook
from ..interfaces import IExcusedGrade
from ..interfaces import ACT_VIEW_GRADES
from ..interfaces import NO_SUBMIT_PART_NAME
from ..interfaces import IUsernameSortSubstitutionPolicy

from ..utils import remove_from_container

from ..grades import PersistentGrade as Grade

LINKS = StandardExternalFields.LINKS
ITEMS = StandardExternalFields.ITEMS

@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
class GradeBookPathAdapter(Contained):

	__name__ = 'GradeBook'

	def __init__(self, context, request):
		self.context = IGradeBook(context)
		self.request = request
		self.__parent__ = context

@view_config(route_name='objects.generic.traversal',
			 permission=ACT_VIEW_GRADES,
			 renderer='rest',
			 context=GradeBookPathAdapter,
			 name='GradeBookSummary',
			 request_method='GET')
class GradeBookSummaryView(AbstractAuthenticatedView,
				  			BatchingUtilsMixin):
	"""
	Return the gradebook summary

	--overdue, assessments, etc

	--batch first before we do work

	Accepts the usual batch params as well as a sorting param.
	"""

	_DEFAULT_BATCH_SIZE = 50
	_DEFAULT_BATCH_START = 0

	def _get_sorted_by_usernames( self, result_dict, gradebook, sort_desc=False ):
		"Get the batched/sorted result set by usernames."
		gradebook_students = set()
		for part in gradebook.values():
			for entry in part.values():
				gradebook_students.update( entry.keys() )

		gradebook_students = sorted( gradebook_students, reverse=sort_desc )
		self._batch_items_iterable( result_dict, gradebook_students )

	def _get_sorted_by_final_grades( self, result_dict, final_grade_entry, sort_desc=False ):
		"Get the batched/sorted result set by final grade."
		sorted_grades = sorted( final_grade_entry.items(),
								key=lambda(_,v): v.value,
								reverse=sort_desc )
		sorted_usernames_by_grade = (x[0] for x in sorted_grades)
		self._batch_items_iterable( result_dict, sorted_usernames_by_grade )

	def _get_result_set(self, result_dict, gradebook, final_grade_entry):
		"Do the sorting of users to return in the summary."
		sort_on = self.request.params.get('sortOn')

		# Ascending is default
		sort_order = self.request.params.get('sortOrder')
		sort_descending = bool( sort_order and sort_order.lower() == 'descending' )

		# Username
		if sort_on and sort_on == 'FinalGrade':
			self._get_sorted_by_final_grades( result_dict, final_grade_entry, sort_descending )
		elif sort_on and sort_on == 'Alias':
			# TODO Alias
			pass
		else:
			# Default by username
			self._get_sorted_by_usernames( result_dict, gradebook, sort_descending )

		# Pop our items that we want to return.
		# We get our batch links for free.
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

	def _get_user_stats( self, gradebook, user, assignments, course ):
		"Return overdue/ungraded stats for user."
		overdue_count = 0
		ungraded_count = 0
		today = datetime.utcnow()
		user_histories = component.getMultiAdapter( ( course, user ),
												IUsersCourseAssignmentHistory )

		for assignment in assignments:
			grade = gradebook.getColumnForAssignmentId( assignment.ntiid )
			user_grade = grade.get( user.username )
			history_item = user_histories.get( assignment.ntiid )

			# Submission but no grade
			if history_item and user_grade is None:
				ungraded_count += 1

			# No submission and past due
			if 		history_item is None \
				and assignment.available_for_submission_ending \
				and today > assignment.available_for_submission_ending:
				overdue_count += 1

		return overdue_count, ungraded_count

	def _get_user_final_grade(self, entry, username):
		final_grade = entry.get( username )
		result = None
		if final_grade is not None:
			result = final_grade.value
		return result

	def _get_user_dict( self, username, gradebook, final_grade_entry, assignments, course ):
		"Returns a user's gradebook summary."
		user = User.get_user( username )
		final_grade = self._get_user_final_grade( final_grade_entry, username )
		overdue, ungraded = self._get_user_stats( gradebook, user, assignments, course )

		user = IFriendlyNamed( user )
		user_dict = {}
		user_dict['Class'] = 'UserGradeBookSummary'
		user_dict['Username'] = username
		user_dict['Alias'] = user.alias
		user_dict['FinalGrade'] = final_grade
		user_dict['OverdueAssignmentCount'] = overdue
		user_dict['UngradedAssignmentCount'] = ungraded
		return user_dict

	def __call__(self):
		# TODO Filtering
		#		-incomplete
		#		-overdue
		# TODO Sorting
		# TODO User links to assignment summaries
		# TODO Use assignment index?
		# TODO We could cache on the gradebook, but the
		# overdue/ungraded counts could change.
		gradebook = self.request.context.context
		course = self.context.__parent__

		# Get the usernames we want to return results for.
		# We want to do our batching first for speed.
		result_dict = LocatedExternalDict()
		final_grade_entry = self._get_final_grade_entry( gradebook )
		# We should have links here after batching.
		usernames = self._get_result_set( result_dict, gradebook, final_grade_entry )

		result_dict[ ITEMS ] = items = []
		result_dict['Class'] = 'GradeBookSummary'

		assignments = self._get_assignment_for_course( course )

		# Now build our data for each user
		for username in usernames:
			user_dict = self._get_user_dict( username, gradebook, final_grade_entry, assignments, course )
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

		# update last modified
		theObject.updateLastMod()

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

from .submitted_assignment_history_views import SubmittedAssignmentHistoryGetView
SubmittedAssignmentHistoryGetView = SubmittedAssignmentHistoryGetView # Export

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

import csv
import collections
from cStringIO import StringIO

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

def _replace(username):
	substituter = component.queryUtility(IUsernameSortSubstitutionPolicy)
	if substituter is None:
		return username
	result = substituter.replace(username) or username
	return result

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=IGradeBook,
			 permission=nauth.ACT_READ,
			 name='contents.csv')
class GradebookDownloadView(AbstractAuthenticatedView):
	"""
	Provides a downloadable table of all the assignments
	present in the gradebook. There is a column
	for each assignment and a row for each user.

	A query param `LegacyEnrollmentStatus` can be set to
	either 'ForCredit' or 'Open' to restrict the results to that
	subset of students.

	.. note:: This is hardcoded to export in D2L compatible format.
		(https://php.radford.edu/~knowledge/lore/attachment.php?id=57)
		Dialects would be easily possible.
	"""

	def _make_enrollment_predicate(self):
		status_filter = self.request.GET.get('LegacyEnrollmentStatus')
		if not status_filter:
			return lambda course, user: True

		def f(course,user):
			# TODO: Replace this with nti.contenttypes.courses.interfaces.ICourseInstanceEnrollmentRecord
			enrollment = component.queryMultiAdapter((course, user),
												   ICourseInstanceEnrollment)
			if enrollment is None:
				# We have a submitted assignment for a user no longer enrolled.
				return False
			return enrollment.LegacyEnrollmentStatus == status_filter # Let this blow up when this goes away
		return f

	def __call__(self):
		gradebook = self.request.context
		course = ICourseInstance(gradebook)
		predicate = self._make_enrollment_predicate()

		# We build a dictionary of {username: {Assignment: Grade} }
		# We keep track of known assignment names so we can sort appropriately;
		# it is keyed by the column name (as that's the only thing guaranteed
		# to be unique) and the value is the display name
		usernames_to_assignment_dict = collections.defaultdict(dict)
		seen_asg_names = dict()

		final_grade_entry = None

		for part in gradebook.values():
			for name, entry in part.items():
				if part.__name__ == NO_SUBMIT_PART_NAME and name == 'Final Grade':
					final_grade_entry = entry
					continue

				seen_asg_names[name] = entry.displayName or 'Unknown'
				for username, grade in entry.items():
					user_dict = usernames_to_assignment_dict[username]
					if name in user_dict:
						raise ValueError("Two entries in different part with same name")
					user_dict[name] = grade

		# Now, sort the *display* names, maintaining the
		# association to the actual part name
		sorted_asg_names = sorted((v, k) for k, v in seen_asg_names.items())

		# Now we can build up the rows.
		rows = LocatedExternalList()
		rows.__name__ = self.request.view_name
		rows.__parent__ = self.request.context

		def _tx_string(s):
			# At least in python 2, the CSV writer only works
			# correctly with str objects, implicitly encoding
			# otherwise
			if isinstance(s, unicode):
				s = s.encode('utf-8')
			return s

		# First a header row.
		# Note that we are allowed to use multiple columns to identify
		# students
		rows.append( ['Username', 'External ID', 'First Name', 'Last Name', 'Full Name']
					 # Assignment names could theoretically have non-ascii chars
					 + [_tx_string(x[0]) + ' Points Grade' for x in sorted_asg_names]
					 + ['Adjusted Final Grade Numerator',
					 	'Adjusted Final Grade Denominator']
					 + ['End-of-Line Indicator'] )

		# Now a row for each user and each assignment in the same order.
		# Note that the webapp tends to send string values even when the user
		# typed a number: "75 -". For export purposes, if we can reverse that to a number,
		# we want it to be a number.
		def _tx_grade(value):
			if not isinstance(value, basestring):
				return value
			if value.endswith(' -'):
				try:
					return int(value[:-2])
				except ValueError:
					try:
						return float(value[:-2])
					except ValueError:
						return _tx_string(value)

		for username, user_dict in sorted(usernames_to_assignment_dict.items()):
			user = User.get_user(username)
			if not user or not predicate(course,user):
				continue

			profile = IUserProfile(user)
			external_id = _replace(username)

			realname = profile.realname or ''
			if realname and '@' not in realname and realname != username:
				human_name = nameparser.HumanName( realname )
				firstname = human_name.first or ''
				lastname = human_name.last or ''
			else:
				firstname = ''
				lastname = ''

			data = (username, external_id, firstname, lastname, realname)
			row = [_tx_string(x) for x in data]
			for _, assignment in sorted_asg_names:
				grade = user_dict[assignment].value if assignment in user_dict else ""
				row.append(_tx_grade(grade))

			final_grade = final_grade_entry.get(username) if final_grade_entry else None
			row.append(_tx_grade(final_grade.value) if final_grade else 0)
			row.append( 100 )

			# End-of-line
			row.append('#')
			rows.append(row)

		# Anyone enrolled but not submitted gets a blank row
		# at the bottom...except that breaks the D2L model

		# Convert to CSV
		# In the future, we might switch based on the accept header
		# and provide it as json or XLS alternately
		buf = StringIO()
		writer = csv.writer(buf)
		writer.writerows(rows)

		filename = course.__name__ + '-grades.csv'
		content_disposition = str( 'attachment; filename="%s"' % filename )
		self.request.response.body = buf.getvalue()
		self.request.response.content_disposition = content_disposition
		self.request.response.content_type = str( 'application/octet-stream' )
		return self.request.response
