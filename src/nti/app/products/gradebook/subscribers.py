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

from nti.assessment import interfaces as asm_interfaces

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import users
from nti.dataserver import interfaces as nti_interfaces

from . import grades
from . import gradebook
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

	book = grade_interfaces.IGradeBook(course)
	if not book:
		create_assignments_entries(course)
	# allow a None adaptation which in case there is no book defined
	# we'd see this in testing
	entry = grade_interfaces.IGradeBookEntry(item, None)
	if entry is None:  # pragma no cover
		return
	
	# register/add grade
	course_grades = grade_interfaces.IGrades(course)
	grade = grades.Grade(ntiid=entry.NTIID, username=user.username)
	course_grades.add_grade(grade)

def create_assignments_entries(course):
	# get assignments
	assignments = []
	content_package = getattr(course, 'legacy_content_package', None)
	def _recur(unit):
		items = asm_interfaces.IQAssessmentItemContainer(unit, ())
		for item in items:
			if asm_interfaces.IQAssignment.providedBy(item):
				assignments.append(item)
		for child in unit.children:
			_recur(child)
	if content_package is not None:
		_recur(content_package)

	if not assignments:  # should not happen
		return
	weight = 1.0 / float(len(assignments))  # same weight
	
	book = grade_interfaces.IGradeBook(course)

	part_name = 'Assignments'
	part = gradebook.GradeBookEntry(Name=part_name, displayName=part_name, 
									order=1, weight=1.0)
	book[part_name] = part
	
	for idx, a in enumerate(assignments):
		n = idx+1
		name = 'assignment%s' % n
		display = 'Assignment %s' % n
		entry = gradebook.GradeBookEntry(
							Name=name, displayName=display, weight=weight, order=n,
							assignmentId=getattr(a, 'NTIID', getattr(a, 'ntiid', None)))
	
		part[name] = entry
