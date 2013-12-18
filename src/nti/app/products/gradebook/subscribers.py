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
from zope.lifecycleevent import interfaces as lce_interfaces

from pyramid.traversal import find_interface

from nti.app.assessment import interfaces as appa_interfaces

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import users
from nti.dataserver import interfaces as nti_interfaces

from . import grades
from . import assignments
from . import interfaces as grade_interfaces

def find_gradebook_in_lineage(obj):
	book = find_interface(obj, grade_interfaces.IGradeBook)
	if book is None:
		__traceback_info__ = obj
		raise TypeError("Unable to find gradebook")
	return book

@component.adapter(grade_interfaces.IGradeBookPart, lce_interfaces.IObjectRemovedEvent)
def _gradebook_part_removed(part, event):
	book = find_gradebook_in_lineage(part)
	grades = grade_interfaces.IGrades(book)
	for entry in part.values():
		grades.remove_grades(entry.NTIID)

@component.adapter(grade_interfaces.IGradeBookEntry, lce_interfaces.IObjectRemovedEvent)
def _gradebook_entry_removed(entry, event):
	book = find_gradebook_in_lineage(entry)
	grades = grade_interfaces.IGrades(book)
	grades.remove_grades(entry.NTIID)

@component.adapter(grade_interfaces.IGrade, lce_interfaces.IObjectModifiedEvent)
def _grade_modified(grade, event):
	course = ICourseInstance(grade)
	user = users.User.get_user(grade.username)
	book = grade_interfaces.IGradeBook(course)
	entry = book.get_entry_by_ntiid(grade.ntiid)
	if user and entry is not None and entry.assignmentId:
		assignment_history = component.getMultiAdapter(
										(course, user),
										appa_interfaces.IUsersCourseAssignmentHistory)
		if entry.assignmentId in assignment_history:
			item = assignment_history[entry.assignmentId]
			lifecycleevent.modified(item)

@component.adapter(appa_interfaces.IUsersCourseAssignmentHistoryItem,
				   lce_interfaces.IObjectAddedEvent)
def _assignment_history_item_added(item, event):
	course = ICourseInstance(item)
	user = nti_interfaces.IUser(item)

	assignmentId = item.Submission.assignmentId
	entry = assignments.get_create_assignment_entry(course, assignmentId)

	# register/add grade
	course_grades = grade_interfaces.IGrades(course)
	grade = grades.Grade(NTIID=entry.NTIID, username=user.username)
	course_grades.add_grade(grade)
