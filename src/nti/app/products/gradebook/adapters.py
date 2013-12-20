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

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from . import interfaces as grade_interfaces

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
