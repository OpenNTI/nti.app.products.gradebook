#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
Gradebook event subscribers

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import lifecycleevent

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from pyramid.traversal import find_interface

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from nti.app.products.courseware.interfaces import ICourseInstanceAvailableEvent

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import users
from nti.dataserver import interfaces as nti_interfaces

from .grades import Grade
from . import assignments

from .interfaces import IGrade
from .interfaces import IGradeBook

def find_gradebook_in_lineage(obj):
	book = find_interface(obj, IGradeBook)
	if book is None:
		__traceback_info__ = obj
		raise TypeError("Unable to find gradebook")
	return book

@component.adapter(IGrade, IObjectModifiedEvent)
def _grade_modified(grade, event):
	course = ICourseInstance(grade)
	user = users.User.get_user(grade.username)
	book = IGradeBook(course)
	entry = book.get_entry_by_ntiid(grade.ntiid)
	if user and entry is not None and entry.AssignmentId:
		assignment_history = component.getMultiAdapter( (course, user),
													    IUsersCourseAssignmentHistory)
		if entry.AssignmentId in assignment_history:
			item = assignment_history[entry.assignmentId]
			lifecycleevent.modified(item)

def _find_entry_for_item(item):
	course = ICourseInstance(item)
	book = IGradeBook(course)

	assignmentId = item.Submission.assignmentId

	entry = book.getColumnForAssignmentId(assignmentId)
	if entry is None:
		# Typically during tests something is added
		_synchronize_gradebook_with_course_instance(course,None)
		entry = book.getColumnForAssignmentId(assignmentId)
	if entry is None:
		# Also typically during tests.
		# TODO: Fix those tests to properly register assignments
		# so this branch goes away
		logger.warning("Assignment %s not found in course %s", assignmentId, course)
		return

	return entry

@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectAddedEvent)
def _assignment_history_item_added(item, event):
	entry = _find_entry_for_item(item)
	if entry is not None:
		user = nti_interfaces.IUser(item)
		grade = Grade()
		entry[user.username] = grade

@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectRemovedEvent)
def _assignment_history_item_removed(item, event):
	entry = _find_entry_for_item(item)
	if entry is not None:
		user = nti_interfaces.IUser(item)
		try:
			del entry[user.username]
		except KeyError:
			# Hmm...
			pass

@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _synchronize_gradebook_with_course_instance(course, event):
	assignments.synchronize_gradebook(course)
