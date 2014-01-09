#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views and other functions related to grades and gradebook.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface
from zope.traversing.interfaces import IPathAdapter

from pyramid.view import view_config
from pyramid.interfaces import IRequest
from pyramid import httpexceptions as hexc

from nti.appserver._view_utils import AbstractAuthenticatedView
from nti.appserver._view_utils import ModeledContentEditRequestUtilsMixin
from nti.appserver._view_utils import ModeledContentUploadRequestUtilsMixin

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import authorization as nauth

from .interfaces import IGrade
from .interfaces import IGradeBook
from .interfaces import ISubmittedAssignmentHistory

@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def GradeBookPathAdapter(context, request):
	result = IGradeBook(context)
	return result

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
		self._check_object_exists(theObject)
		self._check_object_unmodified_since(theObject)

		externalValue = self.readInput()
		self.updateContentObject(theObject, externalValue)
		theObject.updateLastMod()

		# Now, because grades are not persistent objects,
		# the btree bucket containing this grade has to be
		# manually told that its contents have changed.
		# XXX: Note that this is very expensive,
		# waking up each bucket of the tree.

		column = theObject.__parent__
		btree = column._SampleContainer__data
		bucket = btree._firstbucket
		found = False
		while bucket is not None:
			if bucket.has_key(theObject.__name__):
				bucket._p_changed = True
				if bucket._p_jar is None: # The first bucket is stored special
					btree._p_changed = True
				found = True
				break
			bucket = bucket._next
		if not found:
			# before there are buckets, it might be inline data?
			btree._p_changed = True

		return theObject


from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory
from nti.assessment.assignment import QAssignmentSubmissionPendingAssessment
from nti.assessment.submission import AssignmentSubmission
from nti.assessment.interfaces import IQAssignment
from nti.dataserver.users import User


@view_config(route_name='objects.generic.traversal',
			 permission=nauth.ACT_UPDATE,
			 renderer='rest',
			 context='.gradebook.NoSubmitGradeBookEntryGrade',
			 request_method='PUT')
class NoSubmitGradePutView(GradePutView):
	"Called to put to a grade that doesn't yet exist."

	def _do_call(self):
		# So we make one exist
		entry = self.request.context.__parent__
		username = self.request.context.__name__

		user = User.get_user(username)
		assignmentId = entry.AssignmentId

		# We insert the history item, which the user himself
		# normally does but cannot in this case. This implicitly
		# creates the grade3
		# TODO: This is very similar to what nti.app.assessment.adapters
		# does for the student, just with fewer constraints...
		submission = AssignmentSubmission()
		submission.assignmentId = assignmentId
		submission.creator = user

		assignment = component.getUtility(IQAssignment,
										  name=submission.assignmentId)
		course = ICourseInstance(assignment)

		assignment_history = component.getMultiAdapter( (course, submission.creator),
														IUsersCourseAssignmentHistory )

		pending_assessment = QAssignmentSubmissionPendingAssessment( assignmentId=submission.assignmentId,
																	 parts=[] )

		assignment_history.recordSubmission( submission, pending_assessment )

		# This inserted the real grade
		grade = entry[username]
		self.request.context = grade

		return super(NoSubmitGradePutView,self)._do_call()


from nti.externalization.interfaces import LocatedExternalDict
from nti.contenttypes.courses.interfaces import is_instructed_by_name

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=ISubmittedAssignmentHistory,
			 permission=nauth.ACT_READ)
class SubmittedAssignmentHistoryGetView(AbstractAuthenticatedView):

	def __call__(self):
		request = self.request
		context = request.context
		username = request.authenticated_userid
		course = ICourseInstance(context)

		if not is_instructed_by_name(course, username):
			raise hexc.HTTPForbidden()

		result = LocatedExternalDict()
		result['Items'] = dict(context)
		column = context.__parent__
		result.__parent__ = column
		result.__name__ = context.__name__

		return result

from nti.appserver.ugd_edit_views import UGDDeleteView
from zope.annotation import IAnnotations
from zope import lifecycleevent

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

import csv
import collections
from nti.externalization.interfaces import LocatedExternalList
from cStringIO import StringIO
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from .interfaces import NO_SUBMIT_PART_NAME

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

	.. note:: This is hardcoded to export in D2L compatible format.
		(https://php.radford.edu/~knowledge/lore/attachment.php?id=57)
		Dialects would be easily possible.
	"""


	def __call__(self):
		gradebook = self.request.context

		# We build a dictionary of {username: {Assignment: Grade} }
		# We keep track of known assignment names so we can sort appropriately

		usernames_to_assignment_dict = collections.defaultdict(dict)
		seen_asg_names = set()

		final_grade_entry = None

		for part in gradebook.values():
			for name, entry in part.items():
				if part.__name__ == NO_SUBMIT_PART_NAME and name == 'Final Grade':
					final_grade_entry = entry
					continue

				seen_asg_names.add(name)
				for username, grade in entry.items():
					user_dict = usernames_to_assignment_dict[username]
					if name in user_dict:
						raise ValueError("Two entries in different part with same name, yikes")
					user_dict[name] = grade

		sorted_asg_names = sorted(seen_asg_names)

		# Now we can build up the rows.
		rows = LocatedExternalList()
		rows.__name__ = self.request.view_name
		rows.__parent__ = self.request.context

		# First a header row
		rows.append( ['OrgDefinedId']
					 + [x + ' Points Grade' for x in sorted_asg_names]
					 + ['Adjusted Final Grade Numerator', 'Adjusted Final Grade Denominator']
					 + ['End-of-Line Indicator'] )

		# Now a row for each user and each assignment in the same order
		for username, user_dict in sorted(usernames_to_assignment_dict.items()):
			row = [username]
			for assignment in sorted_asg_names:
				grade = user_dict[assignment].value if assignment in user_dict else ""
				row.append(grade)

			final_grade = final_grade_entry.get(username) if final_grade_entry else None
			row.append(final_grade.value if final_grade else 0)
			row.append( 100 )

			# End-of-line
			row.append('#')

			rows.append(row)

		# Anyone enrolled but not submitted gets a blank row
		# at the bottom
		# TODO: Does LegacyEnrollmentStatus (ForCredit) play into this?
		# Grade format certainly does, we don't do it for non-enrolled students;
		# we may need to restrict it too in the general rows
		if False:
			enrollments = ICourseEnrollments(ICourseInstance(gradebook))
			for user in enrollments.iter_enrollments():
				if user.username not in usernames_to_assignment_dict:
					rows.append( [user.username] )

		# Convert to CSV
		# In the future, we might switch based on the accept header
		# and provide it as json or XLS alternately
		buf = StringIO()
		writer = csv.writer(buf)
		writer.writerows(rows)

		self.request.response.body = buf.getvalue()
		self.request.response.content_disposition = b'attachment; filename="contents.csv"'

		return self.request.response
