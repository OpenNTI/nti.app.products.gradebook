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

from . import interfaces as grade_interfaces

@interface.implementer(grade_interfaces.IGrades)
@component.adapter(grade_interfaces.IGradeBook)
def gradebook_to_grades(gradebook):
	course = find_interface(gradebook, ICourseInstance)
	if course is None:
		__traceback_info__ = gradebook
		raise TypeError("Unable to find course")
	return grade_interfaces.IGrades(course)

@interface.implementer(grade_interfaces.IGradeBook)
@component.adapter(grade_interfaces.IGrades)
def grades_to_gradebook(grades):
	course = find_interface(grades, ICourseInstance)
	if course is None:
		__traceback_info__ = grades
		raise TypeError("Unable to find course")
	return grade_interfaces.IGradeBook(course)

@interface.implementer(ICourseInstance)
@component.adapter(grade_interfaces.IGrades)
def grade_to_course(grade):
	__traceback_info__ = grade
	grades = find_interface(grade, grade_interfaces.IGrades)
	if grades is None:
		raise TypeError("Unable to find grades")
	course = find_interface(grades, ICourseInstance)
	if grades is None:
		raise TypeError("Unable to find course")
	return course
