#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
gradebook adapters

.. $Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory

from .interfaces import IGrade
from .interfaces import IGradeBook
from .interfaces import IGradeBookEntry

from nti.dataserver.interfaces import IUser

from .grades import Grade

@interface.implementer(IGradeBookEntry)
@component.adapter(IGrade)
def _GradeToGradeEntry(grade):
	return grade.__parent__

@interface.implementer(IGradeBookEntry)
@component.adapter(IUsersCourseAssignmentHistoryItem)
def _AssignmentHistoryItem2GradeBookEntry(item):
	assignmentId = item.__name__  # by definition
	course = ICourseInstance(item, None)
	# get gradebook entry definition
	gradebook = IGradeBook(course)
	entry = gradebook.getColumnForAssignmentId(assignmentId)
	return entry

from nti.dataserver.traversal import find_interface

@interface.implementer(ICourseInstance)
def _as_course(context):
	"Registered as an adapter for things we expect to be a descendant of a course"
	try:
		return find_interface(context, ICourseInstance)
	except TypeError:
		logger.warn( "incorrect lineage for grade object %s, should be tests only",
					 context,
					 exc_info=True)
		return None

def _no_pickle(*args):
	raise TypeError("This object cannot be pickled")

@interface.implementer(IGrade)
def grade_for_history_item(item):
	"Registered as an adapter for both history item and summary"
	course = ICourseInstance(item)
	user = IUser(item) # Can we do this with just the item? item.creator?
	book = IGradeBook(course)
	assignmentId = item.Submission.assignmentId

	entry = book.getColumnForAssignmentId(assignmentId)
	if entry is not None:
		grade = entry.get(user.username)
		if grade is None:
			# Always dummy up a grade (at the right location in
			# the hierarchy) so that we have an 'edit' link if
			# necessary
			grade = Grade()
			grade.createdTime = 0
			grade.lastModified = 0
			grade.__getstate__ = _no_pickle
			grade.__parent__ = entry
			grade.__name__ = user.username

		return grade
	return None

@interface.implementer(IUsersCourseAssignmentHistoryItem)
@component.adapter(IGrade)
def history_item_for_grade(grade):
	course = ICourseInstance(grade)
	user = IUser(grade)

	history = component.getMultiAdapter( (course, user),
										 IUsersCourseAssignmentHistory)

	assg_id = grade.__parent__.AssignmentId
	try:
		return history[assg_id]
	except KeyError:
		raise TypeError("No history for grade")

from nti.dataserver.users import User

@interface.implementer(IUser)
@component.adapter(IGrade)
def grade_to_user(grade):
	return User.get_user(grade.__name__)
