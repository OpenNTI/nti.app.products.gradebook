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

from nti.app.base.abstract_views import AbstractAuthenticatedView
from nti.app.externalization.view_mixins import ModeledContentEditRequestUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import authorization as nauth

from nti.dataserver.users.interfaces import IUserProfile
import nameparser

from ..interfaces import IGrade
from ..interfaces import IGradeBook
from ..interfaces import ISubmittedAssignmentHistoryBase

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory('nti.app.products.gradebook')

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
		theObject.creator = self.getRemoteUser()

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
from nti.dataserver.users import User
from nti.app.products.courseware.interfaces import ICourseInstanceActivity
from ..grades import Grade

@view_config(route_name='objects.generic.traversal',
			 permission=nauth.ACT_UPDATE,
			 renderer='rest',
			 context='nti.app.products.gradebook.gradebook.GradeWithoutSubmission',
			 request_method='PUT')
class GradeWithoutSubmissionPutView(GradePutView):
	"Called to put to a grade that doesn't yet exist."

	#: We don't want extra catching of key errors
	_EXTRA_INPUT_ERRORS = ()

	def _do_call(self):
		# So we make one exist
		entry = self.request.context.__parent__
		username = self.request.context.__name__

		user = User.get_user(username)
		# canonicalize the username in the event case got mangled
		username = user.username
		assignmentId = entry.AssignmentId

		# We insert the history item, which the user himself
		# normally does but cannot in this case. This implicitly
		# creates the grade
		# TODO: This is very similar to what nti.app.assessment.adapters
		# does for the student, just with fewer constraints...
		# TODO: The handling for a previously deleted grade is
		# what the subscriber does...this whole thing should be simplified
		submission = AssignmentSubmission()
		submission.assignmentId = assignmentId
		submission.creator = user

		pending_assessment = QAssignmentSubmissionPendingAssessment( assignmentId=submission.assignmentId,
																	 parts=[] )
		course = ICourseInstance(entry)

		assignment_history = component.getMultiAdapter( (course, submission.creator),
														IUsersCourseAssignmentHistory )

		try:
			assignment_history.recordSubmission( submission, pending_assessment )
		except KeyError:
			# In case there is already a submission (but no grade)
			# we need to deal with creating the grade object ourself.
			# This code path hits if a grade is deleted
			grade = self.request.context = Grade()
			entry[username] = grade
		else:
			# We don't want this phony-submission showing up as course activity
			# See nti.app.assessment.subscribers
			activity = ICourseInstanceActivity(course)
			activity.remove(submission)

			# This inserted the 'real' grade. To actually
			# updated it with the given values, let the super
			# class do the work
			self.request.context = entry[username]

		return super(GradeWithoutSubmissionPutView,self)._do_call()

from ._submitted_assignment_history_views import SubmittedAssignmentHistoryGetView
SubmittedAssignmentHistoryGetView = SubmittedAssignmentHistoryGetView # Export

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
		del context.__parent__[context.__name__]

		return True


import csv
import collections
from nti.externalization.interfaces import LocatedExternalList
from cStringIO import StringIO
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from ..interfaces import NO_SUBMIT_PART_NAME

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
			enrollment = component.getMultiAdapter((course, user),
												   ICourseInstanceEnrollment)
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
						raise ValueError("Two entries in different part with same name, yikes")
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
		rows.append( ['Username', 'First Name', 'Last Name', 'Full Name']
					 # Assignment names could theoretically have non-ascii chars
					 + [_tx_string(x[0]) + ' Points Grade' for x in sorted_asg_names]
					 + ['Adjusted Final Grade Numerator', 'Adjusted Final Grade Denominator']
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
			realname = profile.realname or ''
			if realname and '@' not in realname and realname != username:
				human_name = nameparser.HumanName( realname )
				firstname = human_name.first or ''
				lastname = human_name.last or ''
			else:
				firstname = ''
				lastname = ''

			row = [_tx_string(x) for x in (username, firstname, lastname, realname)]
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
		self.request.response.body = buf.getvalue()
		self.request.response.content_disposition = str( 'attachment; filename="%s"' % filename )
		self.request.response.content_type = str( 'application/octet-stream' )

		return self.request.response
