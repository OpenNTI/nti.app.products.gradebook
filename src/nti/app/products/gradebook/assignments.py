#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.app.assessment.interfaces import ICourseAssignmentCatalog
from nti.ntiids import ntiids

from . import gradebook
from . import interfaces as grade_interfaces

def _assignment_comparator(a, b):
	a_end = a.available_for_submission_ending
	b_end = b.available_for_submission_ending
	if a_end and b_end:
		return -1 if a_end < b_end else 1

	a_begin = a.available_for_submission_beginning
	b_begin = b.available_for_submission_beginning
	if a_begin and b_begin:
		return -1 if a_begin < b_begin else 1

	return 0

def get_course_assignments(course, sort=True, reverse=False):
	assignments = list(ICourseAssignmentCatalog(course).iter_assignments())

	if sort:
		assignments = sorted(assignments, cmp=_assignment_comparator, reverse=reverse)
	return assignments

def create_assignment_part(course, weight=1.0):
	part_name = 'Assignments'
	book = grade_interfaces.IGradeBook(course)
	if not part_name in book:
		part = gradebook.GradeBookPart()
		part.displayName = part.Name = part_name
		part.order = 1
		# part.weight = weight
		book[part_name] = part
		return part
	else:
		return book[part_name]
get_create_assignment_part = create_assignment_part

def create_assignment_entry(course, assignmentId, displayName=None, order=1):
	book = grade_interfaces.IGradeBook(course)
	specific = ntiids.get_specific(assignmentId)
	specific = specific.replace(' ', '')
	entry = book.get_entry_by_assignment(assignmentId)
	if entry is None:
		displayName = displayName or specific
		part = get_create_assignment_part(course)
		entry = gradebook.GradeBookEntry(Name=specific,
										 displayName=displayName,
										 order=order,
										 assignmentId=assignmentId)
		part[specific] = entry
	return entry
get_create_assignment_entry = create_assignment_entry

def create_assignments_entries(course):
	# XXX: Note: assignments will be added and even removed
	# from the course dynamically.
	assignments = get_course_assignments(course)
	if not assignments:  # should not happen
		return 0

	# weight = 1.0 / float(len(assignments))  # same weight
	create_assignment_part(course)
	for idx, a in enumerate(assignments):
		n = idx + 1
		displayName = 'Assignment %s' % n
		create_assignment_entry(course, a.__name__, displayName, n)

	return len(assignments)
