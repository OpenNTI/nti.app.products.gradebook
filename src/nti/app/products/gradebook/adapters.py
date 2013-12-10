#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
gradebook adapters

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from pyramid.traversal import find_interface

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from . import interfaces as grade_interfaces

@interface.implementer(grade_interfaces.IGrades)
@component.adapter(grade_interfaces.IGradeBook)
def _GradeBook2Grades(gradebook):
	course = find_interface(gradebook, ICourseInstance)
	if course is None:
		__traceback_info__ = gradebook
		raise TypeError("Unable to find course")
	return grade_interfaces.IGrades(course)

@interface.implementer(grade_interfaces.IGradeBook)
@component.adapter(grade_interfaces.IGrades)
def _GradesToGradeBook(grades):
	course = find_interface(grades, ICourseInstance)
	if course is None:
		__traceback_info__ = grades
		raise TypeError("Unable to find course")
	return grade_interfaces.IGradeBook(course)

@interface.implementer(ICourseInstance)
@component.adapter(grade_interfaces.IGrade)
def _GradeToCourseInstance(grade):
	course = find_interface(grade, ICourseInstance)
	if course is None:
		__traceback_info__ = grade
		raise TypeError("Unable to find course")
	return course

@interface.implementer(grade_interfaces.IGradeBookEntry)
@component.adapter(grade_interfaces.IGrade)
def _GradeToGradeEntry(grade):
	course = find_interface(grade, ICourseInstance)
	gradebook = grade_interfaces.IGradeBook(course, None)
	if gradebook is not None:
		result = gradebook.get_entry_by_ntiid(grade.NTIID)
		if result is None:
			__traceback_info__ = grade
			raise TypeError("Unable to find grade entry")
		return result
	return None

@interface.implementer(grade_interfaces.IGradeBookEntry)
@component.adapter(IUsersCourseAssignmentHistoryItem)
def _AssignmentHistoryItem2GradeBookEntry(item):
	assignmentId = item.__name__  # by definition
	course = ICourseInstance(item, None)
	# get gradebook entry definition
	gradebook = grade_interfaces.IGradeBook(course, None)
	entry = gradebook.get_entry_by_assignment(assignmentId) \
			if gradebook is not None else None
	# None adaptation is allowed in case there is no gradebook defined
	return entry
