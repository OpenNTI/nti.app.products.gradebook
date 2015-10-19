# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.lifecycleevent import added

from zope.location.location import locate

from ZODB.interfaces import IConnection

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory

from nti.app.products.courseware.interfaces import ICourseInstanceActivity

from nti.assessment.submission import AssignmentSubmission
from nti.assessment.assignment import QAssignmentSubmissionPendingAssessment

from nti.contenttypes.courses.interfaces import ICourseInstance

from ..grades import PersistentGrade

def mark_btree_bucket_as_changed(grade):
	# Now, because grades are not persistent objects,
	# the btree bucket containing this grade has to be
	# manually told that its contents have changed.
	# XXX: Note that this is very expensive,
	# waking up each bucket of the tree.
	column = grade.__parent__
	btree = column._SampleContainer__data
	bucket = btree._firstbucket
	found = False
	while bucket is not None:
		if bucket.has_key(grade.__name__):
			bucket._p_changed = True
			if bucket._p_jar is None:  # The first bucket is stored special
				btree._p_changed = True
			found = True
			break
		bucket = bucket._next
	if not found:
		# before there are buckets, it might be inline data?
		btree._p_changed = True
	return found

def save_in_container(container, key, value, event=False):
	if event:
		container[key] = value
	else:
		container._setitemf(key, value)
		locate(value, parent=container, name=key)
		IConnection(container).add(value)
		added(value, container, key)
		try:
			container.updateLastMod()
		except AttributeError:
			pass
		container._p_changed = True

def remove_from_container(container, key, event=False):
	if event:
		del container[key]
	else:
		# _delitemf calls ObjectEventRemoved
		container._delitemf(key)
		try:
			container.updateLastMod()
		except AttributeError:
			pass
		container._p_changed = True

def record_grade_without_submission(entry, user, assignmentId=None,
									clazz=PersistentGrade):
	# canonicalize the username in the event case got mangled
	username = user.username
	assignmentId = assignmentId or entry.AssignmentId

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

	grade = None
	course = ICourseInstance(entry)
	pending_assessment = QAssignmentSubmissionPendingAssessment(
												assignmentId=assignmentId,
												parts=[])

	assignment_history = component.getMultiAdapter((course, submission.creator),
													IUsersCourseAssignmentHistory)

	try:
		assignment_history.recordSubmission(submission, pending_assessment)
		# at this point a place holder grade is created we don't return it
		# to indicate to callers of this function that they need to get
		# the grade from the entry
	except KeyError:
		# In case there is already a submission (but no grade)
		# we need to deal with creating the grade object ourself.
		# This code path hits if a grade is deleted
		grade = clazz()
		save_in_container(entry, username, grade)
	else:
		# We don't want this phony-submission showing up as course activity
		# See nti.app.assessment.subscribers
		activity = ICourseInstanceActivity(course)
		activity.remove(submission)
	return grade
