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
