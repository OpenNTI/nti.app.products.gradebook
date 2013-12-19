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
	return grade.__parent__


@interface.implementer(grade_interfaces.IGradeBookEntry)
@component.adapter(IUsersCourseAssignmentHistoryItem)
def _AssignmentHistoryItem2GradeBookEntry(item):
	assignmentId = item.__name__  # by definition
	course = ICourseInstance(item, None)
	# get gradebook entry definition
	gradebook = grade_interfaces.IGradeBook(course)
	entry = gradebook.getColumnForAssignmentId(assignmentId)

	return entry
