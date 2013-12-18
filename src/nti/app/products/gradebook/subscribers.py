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

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.app.products.courseware.interfaces import ICourseInstanceAvailableEvent


from nti.dataserver import users
from nti.dataserver import interfaces as nti_interfaces

from .grades import Grade
from . import assignments

from .interfaces import IGrade
from .interfaces import IGrades
from .interfaces import IGradeBook
from .interfaces import IGradeBookPart
from .interfaces import IGradeBookEntry

def find_gradebook_in_lineage(obj):
	book = find_interface(obj, IGradeBook)
	if book is None:
		__traceback_info__ = obj
		raise TypeError("Unable to find gradebook")
	return book

@component.adapter(IGradeBookPart, IObjectRemovedEvent)
def _gradebook_part_removed(part, event):
	book = find_gradebook_in_lineage(part)
	grades = IGrades(book)
	for entry in part.values():
		grades.remove_grades(entry.NTIID)

@component.adapter(IGradeBookEntry, IObjectRemovedEvent)
def _gradebook_entry_removed(entry, event):
	book = find_gradebook_in_lineage(entry)
	grades = IGrades(book)
	grades.remove_grades(entry.NTIID)

@component.adapter(IGrade, IObjectModifiedEvent)
def _grade_modified(grade, event):
	course = ICourseInstance(grade)
	user = users.User.get_user(grade.username)
	book = IGradeBook(course)
	entry = book.get_entry_by_ntiid(grade.ntiid)
	if user and entry is not None and entry.assignmentId:
		assignment_history = component.getMultiAdapter( (course, user),
													    IUsersCourseAssignmentHistory)
		if entry.assignmentId in assignment_history:
			item = assignment_history[entry.assignmentId]
			lifecycleevent.modified(item)

@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectAddedEvent)
def _assignment_history_item_added(item, event):
	course = ICourseInstance(item)
	user = nti_interfaces.IUser(item)

	assignmentId = item.Submission.assignmentId
	entry = assignments.get_create_assignment_entry(course, assignmentId)

	# register/add grade
	course_grades = IGrades(course)
	grade = Grade(NTIID=entry.NTIID, username=user.username)
	course_grades.add_grade(grade)

@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _synchronize_gradebook_with_course_instance(course, event):
	assignments.synchronize_gradebook(course)
